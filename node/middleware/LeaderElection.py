import uuid
import time

from Logger import lg
from Messaging import Message, DefaultHeaders, DefaultMessageTypes
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
class LeaderSubsystem:
    def __init__(self, rmcast: RMulticast, sender: IPSender, uid: str, cb_leader_found, voting_timeout=2):
        self.VOTING_TIMEOUT = voting_timeout
        self.mw_sender = sender
        self.r_multicast = rmcast
        self.own_uid = uid
        self.is_leader = False
        self.received_leader_answer_message = False
        self.leader_uid = ''
        self.cb_leader_found = cb_leader_found
        self.leader_election_neccessary = False
        self.lost_an_election = False

    def participating_in_election(self):
        return self.thread.isAlive()

    def _broadcast_election_message(self):
        lg.info("Broadcasting election message.")
        self.r_multicast.send(Message({DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_ELECTION_MESSAGE}, None))

    def _reset_leader_state(self):
        self.is_leader = False
        self.leader_uid = ""
        self.received_leader_answer_message = False
        self.lost_an_election = False
        self.leader_election_neccessary = False


    def _other_looses_election(self, other_id):
        other_uid = uuid.UUID(other_id)
        this_uid = uuid.UUID(self.own_uid)

        return this_uid < other_uid

    def leader_election_message_received_handler(self, msg: Message):
        if msg.get_header(DefaultHeaders.ORIGIN_IP) == getCurrentIpAddress():
            return
        lg.info(f"Received election message by {msg.get_header(DefaultHeaders.ORIGIN_IP)}")

        other_uid = msg.get_header(DefaultHeaders.UID)
        other_ip = msg.get_header(DefaultHeaders.ORIGIN_IP)
        other_port = msg.get_header(DefaultHeaders.UNICAST_PORT)

        if self._other_looses_election(other_uid):
            lg.info(f"Won election against {msg.get_header(DefaultHeaders.ORIGIN_IP)}")
            self.mw_sender.send_message_unicast(other_ip,other_port, None,
                                                {DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_ANSWER_MESSAGE})
        else:
            self.lost_an_election = True
            lg.info(f"Lost election against {msg.get_header(DefaultHeaders.ORIGIN_IP)}")


    def leader_answer_message_received_handler(self, msg: Message):
        lg.info(f"Received leader answer message by {msg.get_header(DefaultHeaders.ORIGIN_IP)}")
        self.received_leader_answer_message = True
        pass

    def leader_coordinator_message_received_handler(self, msg: Message):
        other_uid = msg.get_header(DefaultHeaders.UID)

        if other_uid == self.own_uid:
            self.is_leader = True
            self.leader_uid = self.own_uid
            lg.info(f"Accepted self as new Coordinator.")
            global_events.emit_event(MiddlewareEvents.SELF_ELECTED_AS_LEADER)

        elif not self._other_looses_election(other_uid):
            self.leader_uid = other_uid
            self.is_leader = False
            try:
                self.cb_leader_found()
            except Exception as e:
                lg.error(f"Leader found callback threw an error: {e}")
            lg.info(f"Accepted new Coordinator [{msg.get_header(DefaultHeaders.ORIGIN_IP)}]")
        else:
            lg.error(f"Coordinator [{msg.get_header(DefaultHeaders.ORIGIN_IP)}] illegitimately announced!")
            self.leader_election_neccessary = True

    """
    This thread is started if no leader is known.
    """
    def leader_election_alg(self):
        lg.info("Leader election started.")
        self._reset_leader_state()
        self._broadcast_election_message()
        time.sleep(self.VOTING_TIMEOUT)

        if self.received_leader_answer_message or self.lost_an_election:
            lg.info("Leader election completed as slave.")
        else:
            self.r_multicast.send(Message({DefaultHeaders.TYPE: DefaultMessageTypes.LEADER_COORDINATOR_MESSAGE}, None))
            lg.info("Leader election completed as leader.")


        time.sleep(0.5)
        self.leader_election_neccessary = False