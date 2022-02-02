import threading
import socket
import struct
import json
import logging as lg

import time
import uuid
import names


encoding = 'utf-8'

MCAST_GRP = '224.1.1.1'

MCAST_PORT = 5007
node_offline_timeout_s = 3

"""
Information about a peer
"""
class Peer:
    def __init__(self, uid, origin_ip, **kwargs):
        self.uid = uid
        self.ip = origin_ip
        self.last_alive = time.time()
        self.heartbeats_received = 0

    def __str__(self):
        buf = ""
        if self.is_leader:
            buf += "[leader] "
        if self.is_online():
            buf += "[online]"
        else:
            buf += "[offline]"
        return buf

    def update(self, origin_ip, **kwargs):
        self.last_alive = time.time()

        if self.ip != origin_ip:
            lg.info(f"The IP of node {self.uid} changed from {self.ip} to {origin_ip}.")
            self.ip = origin_ip

        if DefaultHeaders.TYPE in kwargs and kwargs.get(DefaultHeaders.TYPE) == DefaultMessageTypes.HEARTBEAT:
            self.heartbeats_received += 1

    def is_online(self):
        return time.time() - self.last_alive < node_offline_timeout_s

class Message:
    def __init__(self, header, body):
        self.header = header
        self.body = body

    def get_header(self, header_key):
        if header_key in self.header:
            return self.header[header_key]
        else:
            return None

"""
Main class
"""
class Middleware:
    def __init__(self, cb_message_received, cb_heartbeat_payload=None, heartbeat_rate_s=1, leader_control_rate_s=2):
        # Error checks
        if heartbeat_rate_s >= node_offline_timeout_s:
            ValueError("Heartbeat rate must be faster than the node offline_timeout")

        # Settings
        self.heartbeat_rate_s = heartbeat_rate_s
        self.leader_control_rate_s = leader_control_rate_s

        # Other Properties
        self.uid = str(uuid.uuid4())
        self.readable_name = names.get_full_name()
        self.peer_list = dict()
        self.leader_peer = None

        # External callback methods (API)
        self.ext_cb_heartbeat_payload = cb_heartbeat_payload
        self.ext_cb_message_received = cb_message_received

        # Empty Initializations
        self.ip = getCurrentIpAddress()

        # Network Interfaces
        self.mc_sender = MWSender(MCAST_GRP, MCAST_PORT, None, self.uid)
        self.mc_rec = MulticastReceiver(MCAST_GRP, MCAST_PORT, self.cb_message_received)

        # Threads
        self.heartbeat_thread = threading.Thread(target=self._t_heartbeat, args=(self.ext_cb_heartbeat_payload,), kwargs={})
        self.leader_thread = threading.Thread(target=self._t_leader_supervisor)

        # Helper Classes
        self.leader_subsystem = LeaderSubsystem(sender=self.mc_sender, uid=self.uid, cb_leader_found=self.cb_leader_found)

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

    def cb_leader_found(self):
        pass

    def cb_message_received(self, msg: Message):
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
            self.leader_subsystem.leader_answer_message_received_handler(msg)
            return

        # If nothing above is applicable route to external controller
        try:
            self.ext_cb_message_received(msg)
        except Exception as e:
            lg.error(f'message received callback function failed: {e}')

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
            self.mc_sender.send_message_multicast(message_body, {DefaultHeaders.TYPE: DefaultMessageTypes.HEARTBEAT})
            time.sleep(self.heartbeat_rate_s)

    """
    This thread checks whether a leader is present in the network and initiates the election process if not.
    It also throws out every node from the node_list that has had a timeout.
    """

    def _t_leader_supervisor(self):
        while True:
            if (not self.leader_subsystem.leader_known or not self.leader_subsystem.leader_uid)\
                    and not self.leader_subsystem.election_in_progress:
                lg.info("No leader found by supervisor. Init leader election process.")
                self.leader_subsystem.start_leader_election()

            time.sleep(self.leader_control_rate_s)


"""
This Class wraps some basic Receive Functionalities around the basic OS-Socket Library
"""
class MulticastReceiver:
        def __init__(self, Multicast_Address, Multicast_Port, cb_message_received):
            self.Address = Multicast_Address
            self.Port = Multicast_Port
            self.stopReceiving = False
            self._start_receiving(cb_message_received)

        def _initialize_communication(self):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('', self.Port))
            mreq = struct.pack("=4sl", socket.inet_aton("224.1.1.1"), socket.INADDR_ANY)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        def _t_run_receiver_loop(self, cb):
            while (not self.stopReceiving):
                msg_received = self.sock.recv(10240)
                msg_received = str(msg_received, encoding)
                #msg_received = json.loads(msg_received, object_hook=lambda d: SimpleNamespace(**d))
                msg_received = json.loads(msg_received)
                msg_received = Message(**msg_received)
                cb(msg_received)


        def _start_receiving(self, cb):
            self._initialize_communication()
            thread = threading.Thread(target=self._t_run_receiver_loop, args=(cb,), kwargs={})
            thread.start()
            lg.debug("Reactor Running")

        def shutdownReceiver(self):
            self.stopReceiving = True


class DefaultHeaders:
    DESTINATION_IP = 'destination_ip'
    ORIGIN_IP = 'origin_ip'
    UID = 'uid'
    TYPE = 'type'

class MWSender:
    def __init__(self, multicast_addr, port, additional_default_headers, uid):
        self.multicast_addr = multicast_addr
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        if additional_default_headers is None:
            self.additional_default_headers = {}
        else:
            self.additional_default_headers = additional_default_headers
        self.uid = uid

    def _generate_default_header(self, destination_ip):
        return self.additional_default_headers | {DefaultHeaders.ORIGIN_IP: getCurrentIpAddress(), DefaultHeaders.DESTINATION_IP: destination_ip,
                                                  DefaultHeaders.UID: self.uid}

    def send_message_multicast(self, message_body, custom_headers):
        if custom_headers is None:
            custom_headers = {}

        msg = Message(header=custom_headers | self._generate_default_header(self.multicast_addr), body=message_body)
        msg_str = json.dumps(msg.__dict__)

        self.sock.sendto(msg_str.encode(), (self.multicast_addr, self.port))
        lg.debug(f"Message send mc: {msg_str}")

    def send_message_unicast(self, destination_ip, message_body, custom_headers):
        if custom_headers is None:
            custom_headers = {}

        msg = Message(self._generate_default_header(destination_ip) | custom_headers, message_body)
        msg_str = json.dumps(msg.__dict__)
        self.sock.sendto(msg_str.encode(), (self.multicast_addr, self.port))
        lg.debug(f"Message send uc: {msg_str}")


class DefaultMessageTypes:
    HEARTBEAT = "heartbeat"
    LEADER_ELECTION_MESSAGE = "LEADER_ELECTION_MESSAGE"
    LEADER_ANSWER_MESSAGE = "LEADER_ANSWER_MESSAGE"
    LEADER_COORDINATOR_MESSAGE = "LEADER_COORDINATOR_MESSAGE"


"""
This Class provides basic leader election by using the bully algorithm

Abbreviations of default bully alg:
    - smaller UID
    - broadcast instead of unicast to higher uids for robustness
"""
class LeaderSubsystem:
    def __init__(self, sender: MWSender, uid: str, cb_leader_found, voting_timeout=2):
        self.VOTING_TIMEOUT = voting_timeout
        self.mw_sender = sender
        self.own_uid = uid
        self.election_in_progress = False
        self.is_leader = False
        self.leader_known = False
        self.received_leader_answer_message = False
        self.thread = threading.Thread(target=self.t_leader_election)
        self.leader_uid = ''
        self._thread_completed = False
        self.cb_leader_found = cb_leader_found

    def start_leader_election(self):
        if self._thread_completed:
            self.thread = threading.Thread(target=self.t_leader_election)
        if not self.thread.is_alive():
            self.thread.start()

    def participating_in_election(self):
        return self.thread.isAlive()

    def _broadcast_election_message(self):
        lg.info("Broadcasting election message.")
        self.received_leader_answer_message = False
        self.mw_sender.send_message_multicast(None, {DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_ELECTION_MESSAGE})

    def _reset_leader_state(self):
        self.is_leader = False
        self.leader_uid = ""
        self.election_in_progress = True
        self.received_leader_answer_message = False
        self.leader_known = False

    def _other_looses_election(self, other_id):
        other_uid = uuid.UUID(other_id)
        this_uid = uuid.UUID(self.own_uid)

        return this_uid < other_uid

    def leader_election_message_received_handler(self, msg: Message):
        lg.info("received election message")
        self._reset_leader_state()

        other_uid = msg.get_header(DefaultHeaders.UID)
        other_ip = msg.get_header(DefaultHeaders.ORIGIN_IP)

        if self._other_looses_election(other_uid):
            self.mw_sender.send_message_unicast(other_ip, None,
                                                {DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_ANSWER_MESSAGE})
            self.start_leader_election()

    def leader_answer_message_received_handler(self, msg: Message):
        self.received_leader_answer_message = True
        pass

    def leader_coordinator_message_received_handler(self, msg: Message):
        other_uid = msg.get_header(DefaultHeaders.UID)
        if not self._other_looses_election(other_uid):
            self.leader_uid = other_uid
            self.election_in_progress = False
            self.is_leader = False
            self.leader_known = True
            try:
                self.cb_leader_found()
            except Exception as e:
                lg.error(f"Leader found callback threw an error: {e}")
        else:
            lg.error("Coordinator illegitimately announced!")
            self.start_leader_election()

    """
    This thread is started if no leader is known.
    """
    def t_leader_election(self):
        lg.info("Leader election started.")
        self._reset_leader_state()
        self._broadcast_election_message()
        time.sleep(self.VOTING_TIMEOUT)

        if not self.received_leader_answer_message:
            self.is_leader = True
            self.leader_known = True
            self.election_in_progress = False
            self.mw_sender.send_message_multicast(None, {DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_COORDINATOR_MESSAGE})
            lg.info("Leader election completed as leader.")
        else:
            lg.info("Leader election lost.")
        self._thread_completed = True


"""
This function returns the IP Address of the current System 
"""
def getCurrentIpAddress():
    h_name = socket.gethostname()
    IP_addres = socket.gethostbyname(h_name)
    return IP_addres





