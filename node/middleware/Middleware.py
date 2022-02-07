import uuid
import names
import threading
import time

from Logger import lg
from Configuration import node_offline_timeout_s, MCAST_PORT, MCAST_GRP, UNCAST_PORT
from Messaging import Message, DefaultMessageTypes, DefaultHeaders
from Utils import getCurrentIpAddress, getNextFreePort
from IPCommunication import IPSender, IPReceiver
from ReliableMulticast import RMulticast
from LeaderElection import LeaderSubsystem
from Peer import Peer


"""
Main class
"""
class Middleware:
    def __init__(self, cb_mcast_message_received, cb_uncast_message_received, cb_heartbeat_payload=None, heartbeat_rate_s=1, leader_control_rate_s=0.01):
        # Error checks
        if heartbeat_rate_s >= node_offline_timeout_s:
            ValueError("Heartbeat rate must be faster than the node offline_timeout")

        self.unicast_port = getNextFreePort()

        # Settings
        self.heartbeat_rate_s = heartbeat_rate_s
        self.leader_control_rate_s = leader_control_rate_s

        # Other Properties
        self.uid = str(uuid.uuid4())
        self.readable_name = names.get_full_name()
        self.peer_list = dict()

        # External callback methods (API)
        self.ext_cb_heartbeat_payload = cb_heartbeat_payload
        self.ext_cb_mcast_message_received = cb_mcast_message_received
        self.ext_cb_uncast_message_received = cb_uncast_message_received

        # Empty Initializations
        self.ip = getCurrentIpAddress()



        # Network Interfaces


        self.mc_sender = IPSender(MCAST_GRP, MCAST_PORT,self.unicast_port, None, self.uid)
        self.r_multicast = RMulticast(self.cb_mcast_message_received, self.mc_sender)
        self.mc_rec = IPReceiver(MCAST_GRP, MCAST_PORT, getCurrentIpAddress(), self.unicast_port,
                                        self.r_multicast.receive, self.cb_uncast_message_received)




        # Threads
        self.heartbeat_thread = threading.Thread(target=self._t_heartbeat, args=(self.ext_cb_heartbeat_payload,), kwargs={})
        self.leader_thread = threading.Thread(target=self._t_leader_supervisor)

        # Helper Classes
        self.leader_subsystem = LeaderSubsystem(sender=self.mc_sender, uid=self.uid,
                                                cb_leader_found=self.cb_leader_found, rmcast=self.r_multicast)

        # Start Threads
        self.heartbeat_thread.start()
        self.leader_thread.start()

    def __str__(self):
        entries = "<table>"
        for k, v in vars(self).items():
            ve = f"{v}".replace("<", " ").replace(">", " ")
            entries += f"<tr><td>{k}</td><td>{ve}</td></tr>"
        return entries + "</table>"

    def is_uid_leader(self, uid: str):
        return uid == self.leader_subsystem.leader_uid

    def get_leader(self):
        if self.leader_subsystem.leader_uid in self.peer_list:
            return self.peer_list[self.leader_subsystem.leader_uid]
        else:
            return None

    def cb_leader_found(self):
        pass

    def cb_uncast_message_received(self, msg: Message):
        # Handle Leader answers internally
        if msg.get_header(DefaultHeaders.TYPE) is not None and msg.get_header(DefaultHeaders.TYPE) == DefaultMessageTypes.LEADER_ANSWER_MESSAGE:
            self.leader_subsystem.leader_answer_message_received_handler(msg)
            return

        if msg.get_header(DefaultHeaders.TYPE) is not None and msg.get_header(DefaultHeaders.TYPE) == DefaultMessageTypes.NEGATIVE_ACK:
            self.r_multicast.recived_neg_ack_message(msg)
            return

        # If nothing above is applicable route to external controller
        try:
            self.ext_cb_uncast_message_received(msg)
        except Exception as e:
            lg.error(f'Unicast message received callback function failed: {e}')

    def cb_mcast_message_received(self, msg: Message):
        # Update peer list
        uid = msg.get_header(DefaultHeaders.UID)
        if self.peer_list.get(uid) == None:
            self.peer_list[uid] = Peer(**msg.header)
            lg.info(f"Found new peer with uid {msg.get_header(DefaultHeaders.UID)} and IP {msg.get_header(DefaultHeaders.ORIGIN_IP)}")
        else:
            # todo Auch updaten, wenn die Nachricht kein HB war?
            self.peer_list[uid].update(**msg.header)

        # Distribute Messages if middleware related
        if msg.header[DefaultHeaders.TYPE] == DefaultMessageTypes.LEADER_ELECTION_MESSAGE:
            self.leader_subsystem.leader_election_message_received_handler(msg)
            return
        elif msg.header[DefaultHeaders.TYPE] == DefaultMessageTypes.LEADER_COORDINATOR_MESSAGE:
            self.leader_subsystem.leader_coordinator_message_received_handler(msg)
            return
        elif msg.header[DefaultHeaders.TYPE] == DefaultMessageTypes.LEADER_ANSWER_MESSAGE:
            lg.error("Broadcast used for Leader answer instead of unicast!")
            return

        # If nothing above is applicable route to external controller
        try:
            self.ext_cb_mcast_message_received(msg)
        except Exception as e:
            lg.error(f'Multicast message received callback function failed: {e}')

    """
    This thread sends out the heartbeat at the rate of self.heartbeat_rate_s
    """
    def _t_heartbeat(self, cb_heartbeat_payload):
        while True:
            if cb_heartbeat_payload is not None:
                try:
                    message_body = cb_heartbeat_payload()
                except Exception as e:
                    lg.error(f'heartbeat payload callback function failed: {e}')
                    message_body = {"body": "error at cb function"}

            else:
                message_body = {"body": "not specified"}

            msg = Message({DefaultHeaders.TYPE: DefaultMessageTypes.HEARTBEAT}, message_body)
            self.r_multicast.send(msg)
            time.sleep(self.heartbeat_rate_s)

    """
    This thread checks whether a leader is present in the network and initiates the election process if not.
    It also throws out every node from the node_list that has had a timeout.
    """

    def _t_leader_supervisor(self):
        while True:
            if not self.leader_subsystem.leader_uid or self.get_leader() is None or not self.get_leader().is_online() \
                    or self.leader_subsystem.leader_election_neccessary:
                lg.info("No leader found by supervisor. Init leader election process.")
                self.leader_subsystem.leader_election_alg()
            # todo control rate...
            time.sleep(self.leader_control_rate_s)

