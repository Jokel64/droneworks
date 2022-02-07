import uuid
import time

from Logger import lg
from Messaging import Message, DefaultHeaders, DefaultMessageTypes
from IPCommunication import IPReceiver
from Utils import getCurrentIpAddress
from MiddelwareEvents import MiddlewareEvents, global_events
from IPCommunication import IPSender
from ReliableMulticast import RMulticast

"""
This Class provides basic leader election by using the bully algorithm

Abbreviations of default bully alg:
    - smaller UID
    - broadcast instead of unicast to higher uids for robustness
"""
"""
This Class provides basic leader election by using the bully algorithm

Abbreviations of default bully alg:
    - smaller UID
    - broadcast instead of unicast to higher uids for robustness
"""
class LeaderSubsystem:
    def __init__(self, sender: IPSender, r_mcast: RMulticast, peer_list, uid: str, cb_leader_found, voting_timeout=2):
        self.VOTING_TIMEOUT = voting_timeout
        self.mw_sender = sender
        self.r_mcast = r_mcast
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
                self.mw_sender.send_message_unicast(self.peer_list[uid].ip,self.peer_list[uid].port, None, {DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_ELECTION_MESSAGE})
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
            self.mw_sender.send_message_unicast(msg.get_header(DefaultHeaders.ORIGIN_IP),msg.get_header(DefaultHeaders.UNICAST_PORT), None, {DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_ANSWER_MESSAGE})
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
            self.r_mcast.send(Message({DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_COORDINATOR_MESSAGE},None))
