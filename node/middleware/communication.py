import threading
import socket
import struct
import json
import logging as lg

import schedule
import time
import uuid
import names

from types import SimpleNamespace

encoding = 'utf-8'

MCAST_GRP = '224.1.1.1'

MCAST_PORT = 5007
node_offline_timeout_s = 3

"""
Information about a peer
"""
class Peer:
    def __init__(self, uid, origin_ip, is_leader=False, **kwargs):
        self.uid = uid
        self.ip = origin_ip
        self.is_leader = is_leader
        self.last_alive = time.time()

    def __str__(self):
        buf = ""
        if self.is_leader:
            buf += "[leader] "
        if self.is_online():
            buf += "[online]"
        else:
            buf += "[offline]"
        return buf

    def is_online(self):
        return time.time() - self.last_alive < node_offline_timeout_s

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
        self.is_leader = False
        self.leader_peer = None

        # External callback methods (API)
        self.ext_cb_heartbeat_payload = cb_heartbeat_payload
        self.ext_cb_message_received = cb_message_received

        # Helper Classes
        self.leader_election_helper = LeaderElection(mw=self)

        # Empty Initializations
        self.ip = getCurrentIpAddress()

        # Network Interfaces
        self.mc_sender = MWSender(MCAST_GRP, MCAST_PORT, None, self.uid)
        self.mc_rec = MulticastReceiver(MCAST_GRP, MCAST_PORT, self.cb_message_received)

        # Threads
        self.heartbeat_thread = threading.Thread(target=self._t_heartbeat, args=(self.ext_cb_heartbeat_payload,), kwargs={})
        self.leader_thread = threading.Thread(target=self._t_leader_control_and_node_garbage_collection)

        # Start Threads
        self.heartbeat_thread.start()
        self.leader_thread.start()

    def __str__(self):
        entries = "<table>"
        for k, v in vars(self).items():
            ve = f"{v}".replace("<", " ").replace(">", " ")
            entries += f"<tr><td>{k}</td><td>{ve}</td></tr>"
        return entries + "</table>"

    def cb_message_received(self, msg):
        uid = msg.header['uid']

        if self.peer_list.get(uid) == None:
            self.peer_list[uid] = Peer(**msg.header)

        #If the peer already exists we only need to update the important values
        old_peer = self.peer_list[uid]
        peer_to_merge = Peer(**msg.header)

        old_peer.last_alive = peer_to_merge.last_alive
        old_peer.ip = peer_to_merge.ip

        self.peer_list[uid] = old_peer

        # Distribute Messages if middleware related
        if msg.header['type'] == DefaultMessageTypes.LEADER_ELECTION_BRODCAST:
            self.leader_election_helper.leaderElectionMessageRecived(msg)
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
            self.mc_sender.send_message_multicast(message_body, {'type': DefaultMessageTypes.HEARTBEAT})
            time.sleep(self.heartbeat_rate_s)

    """
    This thread checks whether a leader is present in the network and initiates the election process if not.
    It also throws out every node from the node_list that has had a timeout.
    """

    def _t_leader_control_and_node_garbage_collection(self):
        while True:
            leader_found = False
            for uid, peer in self.peer_list.items():
                if peer.is_leader and peer.is_online():
                    self.leader_peer = peer
                    leader_found = True
                    break

            # No leader found
            if not leader_found:
                self.leader_peer = None
                lg.info("No leader found. Init leader election process.")
                self._init_leader_election()

            time.sleep(self.leader_control_rate_s)

    def _init_leader_election(self):
        self.leader_election_helper.brodcastImLeaderMessage()
        pass

"""
This Class provides basic leader election by using the bully algorithm
"""
class LeaderElection:
    def __init__(self, mw : Middleware):
        self.middelware = mw
        self.electionInProgress = False
        self.lastElectionMessageRecived = time.time()

    def setNewLeader(self,id):
        for uid, peer in self.middelware.peer_list.items():
            if uid == id:
                peer.is_leader = True
            else:
                peer.is_leader = False

    def brodcastImLeaderMessage(self):
        lg.info("Brodcasting election message")
        self.middelware.mc_sender.send_message_multicast(None, {'type': DefaultMessageTypes.LEADER_ELECTION_BRODCAST})
        self.electionInProgress = True

    def leaderElectionMessageRecived(self, msg):
        lg.info("recived election message")
        self.electionInProgress = True
        id = msg.header['uid']

        hisID = uuid.UUID(id)
        myID = uuid.UUID(self.middelware.uid)

        if myID <= hisID:
            self.setNewLeader(id)
            lg.info("My id is smaller or equal so he won")
        else:
            lg.info("My id is bigger so I'm trying to reelect")
            self.brodcastImLeaderMessage()



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

class Message:
    def __init__(self, header, body):
        self.header = header
        self.body = body

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
        return self.additional_default_headers | {'origin_ip': getCurrentIpAddress(), 'destination_ip': destination_ip,
                                                  'uid': self.uid}

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
    LEADER_ELECTION_BRODCAST = "Im_Leader_Now"


"""
This function returns the IP Address of the current System 
"""
def getCurrentIpAddress():
    h_name = socket.gethostname()
    IP_addres = socket.gethostbyname(h_name)
    return IP_addres





