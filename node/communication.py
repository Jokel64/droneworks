import threading
import socket
import struct
import json
from logger import lg

import time
import uuid
import names


encoding = 'utf-8'

MCAST_GRP = '224.1.1.1'

MCAST_PORT = 5007
UNCAST_PORT = 5008
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

class MiddlewareEvents:
    SELF_ELECTED_AS_LEADER = "SELF_ELECTED_AS_LEADER"
    NO_VALID_LEADER = "NO_VALID_LEADER"
    NEW_VALID_LEADER_ASSIGNED = "NEW_VALID_LEADER_ASSIGNED"

    def __init__(self):
        self._registered_events = dict()

    def register_event(self, event_type, handler):
        if event_type not in vars(MiddlewareEvents):
            Exception(f"Event type {event_type} unknown.")
        if event_type not in self._registered_events:
            self._registered_events[event_type] = list()
        self._registered_events[event_type].append(handler)

    def emit_event(self, event_type):
        if event_type in self._registered_events:
            for handler in self._registered_events[event_type]:
                handler()


global_events = MiddlewareEvents()

"""
Main class
"""
class Middleware:
    def __init__(self, cb_mcast_message_received, cb_uncast_message_received, cb_heartbeat_payload=None, heartbeat_rate_s=1, leader_control_rate_s=0.01):
        # Error checks
        if heartbeat_rate_s >= node_offline_timeout_s:
            ValueError("Heartbeat rate must be faster than the node offline_timeout")

        # Settings
        self.heartbeat_rate_s = heartbeat_rate_s
        self.leader_control_rate_s = leader_control_rate_s

        # Other Properties
        self.uid = str(uuid.uuid1())
        self.readable_name = names.get_full_name()
        self.peer_list = dict()

        # External callback methods (API)
        self.ext_cb_heartbeat_payload = cb_heartbeat_payload
        self.ext_cb_mcast_message_received = cb_mcast_message_received
        self.ext_cb_uncast_message_received = cb_uncast_message_received

        # Network Interfaces
        self.mc_sender = MWSender(MCAST_GRP, MCAST_PORT, UNCAST_PORT, None, self.uid)
        self.mc_rec = MulticastReceiver(MCAST_GRP, MCAST_PORT, getCurrentIpAddress(), UNCAST_PORT,
                                        self.cb_mcast_message_received, self.cb_uncast_message_received)

        # Threads
        self.heartbeat_thread = threading.Thread(target=self._t_heartbeat, args=(self.ext_cb_heartbeat_payload,), kwargs={})
        self.leader_thread = threading.Thread(target=self._t_leader_supervisor)

        # Helper Classes
        self.leader_subsystem = LeaderSubsystem(sender=self.mc_sender, peer_list=self.peer_list, uid=self.uid, cb_leader_found=self.cb_leader_found)

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

    def get_own_ip(self):
        h_name = socket.gethostname()
        return socket.gethostbyname(h_name)

    def get_own_hostname(self):
        return socket.gethostname()

    def cb_uncast_message_received(self, msg: Message):
        # Handle Leader answers internally
        if msg.get_header(DefaultHeaders.TYPE) is not None:
            if msg.get_header(DefaultHeaders.TYPE) == DefaultMessageTypes.LEADER_ANSWER_MESSAGE:
                self.leader_subsystem.leader_answer_message_received_handler(msg)
                return
            elif msg.get_header(DefaultHeaders.TYPE) == DefaultMessageTypes.LEADER_ELECTION_MESSAGE:
                self.leader_subsystem.leader_election_message_received_handler(msg)
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
            lg.error("Broadcast used for election message instead of unicast!")
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
            self.mc_sender.send_message_multicast(message_body, {DefaultHeaders.TYPE: DefaultMessageTypes.HEARTBEAT})
            time.sleep(self.heartbeat_rate_s)

    """
    This thread checks whether a leader is present in the network and initiates the election process if not.
    It also throws out every node from the node_list that has had a timeout.
    """

    def _t_leader_supervisor(self):
        time.sleep(2)
        while True:
            start_election = False

            if not self.leader_subsystem.leader_uid:
                start_election = True
                lg.info(f"Leader UID [{self.leader_subsystem.leader_uid}] not set in subsystem.")
            elif self.get_leader() is None:
                start_election = True
                lg.info("Self.get_leader() returned none.")
            elif not self.get_leader().is_online():
                start_election = True
                lg.info("Leader is no longer online.")
            elif self.leader_subsystem.leader_election_necessary:
                lg.info("Leader subsystem deemed election necessary.")
                start_election = True
            if start_election:
                lg.info("Init leader election process.")
                self.leader_subsystem.leader_election_alg()
            time.sleep(self.leader_control_rate_s)


"""
This Class wraps some basic Receive Functionalities around the basic OS-Socket Library
"""
class MulticastReceiver:
        def __init__(self, Multicast_Address, Multicast_Port, unicast_address, unicast_port, cb_mc, cb_uncast):
            self.MCAST_ADDR = Multicast_Address
            self.MCAST_PORT = Multicast_Port
            self.UNCAST_ADDR = unicast_address
            self.UNCAST_PORT = unicast_port
            self.stopReceiving = False

            # Init MCast socket
            self.mcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.mcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.mcast_sock.bind(('', self.MCAST_PORT))
            mreq = struct.pack("=4sl", socket.inet_aton(self.MCAST_ADDR), socket.INADDR_ANY)
            self.mcast_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            # Init Uncast socket
            self.uncast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.uncast_sock.bind((self.UNCAST_ADDR, self.UNCAST_PORT))

            # Start Threads
            mcast_thread = threading.Thread(target=self._t_run_mcast_receiver_loop, args=(cb_mc,), kwargs={})
            mcast_thread.start()
            uncast_thread = threading.Thread(target=self._t_run_uncast_receiver_loop, args=(cb_uncast,), kwargs={})
            uncast_thread.start()

            lg.debug("Reactor Running")

        def _t_run_mcast_receiver_loop(self, cb):
            while (not self.stopReceiving):
                msg_received = self.mcast_sock.recv(10240)
                msg_received = str(msg_received, encoding)
                #msg_received = json.loads(msg_received, object_hook=lambda d: SimpleNamespace(**d))
                msg_received = json.loads(msg_received)
                msg_received = Message(**msg_received)
                cb(msg_received)

        def _t_run_uncast_receiver_loop(self, cb):
            while (not self.stopReceiving):
                msg_received = self.uncast_sock.recv(10240)
                msg_received = str(msg_received, encoding)
                #msg_received = json.loads(msg_received, object_hook=lambda d: SimpleNamespace(**d))
                msg_received = json.loads(msg_received)
                msg_received = Message(**msg_received)
                cb(msg_received)

        def shutdownReceiver(self):
            self.stopReceiving = True


class DefaultHeaders:
    DESTINATION_IP = 'destination_ip'
    ORIGIN_IP = 'origin_ip'
    UID = 'uid'
    TYPE = 'type'

class MWSender:
    def __init__(self, multicast_addr, mcast_port, uncast_port, additional_default_headers, uid):
        self.multicast_addr = multicast_addr
        self.mcast_port = mcast_port
        self.uncast_port = uncast_port
        self.mcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.mcast_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        self.uncast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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
        try:
            self.mcast_sock.sendto(msg_str.encode(), (self.multicast_addr, self.mcast_port))
        except OSError as e:
            lg.error(f"Error sending multicast Message: {e}")
        lg.debug(f"Message send mc: {msg_str}")

    def send_message_unicast(self, destination_ip, message_body, custom_headers):
        if custom_headers is None:
            custom_headers = {}

        msg = Message(self._generate_default_header(destination_ip) | custom_headers, message_body)
        msg_str = json.dumps(msg.__dict__)
        try:
            self.uncast_sock.sendto(msg_str.encode(), (destination_ip, self.uncast_port))
        except OSError as e:
            lg.error(f"Error sending unicast Message: {e}")
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
    def __init__(self, sender: MWSender, peer_list, uid: str, cb_leader_found, voting_timeout=2):
        self.VOTING_TIMEOUT = voting_timeout
        self.mw_sender = sender
        self.peer_list = peer_list
        self.own_uid = uid
        self.leader_uid = ''
        self.cb_leader_found = cb_leader_found
        self.received_leader_answer_message = False
        self.leader_election_necessary = False

    def participating_in_election(self):
        pass

    def _broadcast_election_message(self):
        for uid in self.peer_list:
            if not self._other_looses_election(uid) and not uid==self.own_uid:
                self.mw_sender.send_message_unicast(self.peer_list[uid].ip, None, {DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_ELECTION_MESSAGE})
                lg.info(f"Sent election message to {self.peer_list[uid].ip} [{self.peer_list[uid].uid}]")
        lg.info("Election message broadcasting completed.")

    def _other_looses_election(self, other_id):
        other_time = uuid.UUID(other_id).time
        this_time = uuid.UUID(self.own_uid).time

        if other_time == this_time:
            return self.own_uid < other_id
        else:
            return this_time < other_time

    def leader_election_message_received_handler(self, msg: Message):
        if self._other_looses_election(msg.get_header(DefaultHeaders.UID)):
            self.mw_sender.send_message_unicast(msg.get_header(DefaultHeaders.ORIGIN_IP), None, {DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_ANSWER_MESSAGE})
            lg.info(f"Won election and send leader answer to {msg.get_header(DefaultHeaders.ORIGIN_IP)} [{msg.get_header(DefaultHeaders.UID)}]. New election process necessary.")
            self.leader_election_necessary = True
        else:
            lg.info(f"Lost election to {msg.get_header(DefaultHeaders.ORIGIN_IP)} [{msg.get_header(DefaultHeaders.UID)}]")

    def leader_answer_message_received_handler(self, msg: Message):
        self.received_leader_answer_message = True
        lg.info(f"Answer by {msg.get_header(DefaultHeaders.ORIGIN_IP)} [{msg.get_header(DefaultHeaders.UID)}]")

        pass

    def leader_coordinator_message_received_handler(self, msg: Message):
        other_uid = msg.get_header(DefaultHeaders.UID)
        if not self._other_looses_election(other_uid):
            self.leader_uid = other_uid
            if other_uid == self.own_uid:
                lg.info(f"Accepted self as leader.")
            else:
                lg.info(f"Accepted leader {msg.get_header(DefaultHeaders.ORIGIN_IP)} [{other_uid}].")
        else:
            lg.warn(f"Leader {msg.get_header(DefaultHeaders.ORIGIN_IP)} [{other_uid}] illegitimately announced!")
            self.leader_election_necessary = True

    """
    This thread is started if no leader is known.
    """
    def leader_election_alg(self):
        self.leader_election_necessary = False
        self.received_leader_answer_message = False
        self._broadcast_election_message()
        time.sleep(self.VOTING_TIMEOUT)
        if self.received_leader_answer_message:
            lg.info("Election completed as slave.")
        else:
            lg.info("Election completed as leader.")
            self.mw_sender.send_message_multicast(None, {DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_COORDINATOR_MESSAGE})



"""
This function returns the IP Address of the current System 
"""
def getCurrentIpAddress():
    h_name = socket.gethostname()
    IP_addres = socket.gethostbyname(h_name)
    return IP_addres





