import queue
import time
import threading

from IPCommunication import IPSender
from Messaging import Message, DefaultMessageTypes, DefaultHeaders
from Logger import lg

'''
This Classes provide reliable FIFO ordered multicast using piggiback acks and negative acks when messages are missing.
'''


class RMulticast:
    def __init__(self, delivery_cb, ip_sender: IPSender):
        # 𝑆𝑝, which is the number of messages 𝑝 has sent to the group
        self.sequence_number = 0


        # A vector of sequence numbers, one for each participant in the group. 𝑅𝑞, which is a sequence
        # number of the latest message that 𝑝𝑝 has delivered from a participant
        self.latest_deliveries = dict()

        self.hold_back_queue = []
        self.sendt_messages = dict()

        self.delivery_callback = delivery_cb

        # Here Messages already sent are stored in case a resend is required
        self.send_messages = dict()

        self.ip_sender = ip_sender

    def send(self, message: Message):
        # Increment Sq by one
        self.sequence_number += 1

        #lg.info(f"sending new message with seq: {self.sequence_number}")

        # Attach seq and acknowledgements to message
        message.seq = self.sequence_number
        message.acks = self.latest_deliveries

        # store the message in case someone needs a retransmission
        self.sendt_messages[self.sequence_number] = message
        self.ip_sender.send_message_multicast(message)  # Send Message

    def receive(self, msg: Message):
        #lg.info(f'recived multicast msg with sqe: {msg.seq}')
        process_id_sender = msg.header[DefaultHeaders.UID]
        R_q = self.get_sequence_number_for_process(process_id_sender, msg.seq)

        if msg.seq == R_q + 1: # msg is in order
            lg.info(f'msg in order delivering to application: {msg.seq}')
            self.latest_deliveries[process_id_sender] += 1
            self.deliver_items_from_hb(process_id_sender, R_q+2)
            self.deliverToApplication(msg)

        # This is a specialcase : if a drone looses connection it requests only the 3 missing messages
        if msg.seq > R_q + 3:
            lg.info(f"We are missing more than 3 messages only set the last 3 as missing")
            self.latest_deliveries[process_id_sender] = msg.seq + 3

        if msg.seq > R_q + 1: # we have not received one or more messages
            lg.info(f'we have not recived one or more messages')

            self.send_negative_ack_for_seq(msg, R_q+1)
            self.hold_back_queue.append(msg)

        if msg.seq <= R_q: # we have received a duplicate
            lg.info(f"message{msg.seq} is duplicate dropping")

        #for uid, ack_seq in msg.acks.items():
        #    if ack_seq > self.get_sequence_number_for_process(uid):
        #        lg.info(f"we did not receive at least one message from {process_id_sender}")
        #        #self.send_negative_ack_for_seq(msg, self.get_sequence_number_for_process(uid)+1)
    '''
    This Method delivers a correct in order message to the application
    '''
    def deliverToApplication(self, msg: Message):
        self.delivery_callback(msg)

    '''
    This function returns the latest seq from the message m from process p_uid which was delivered to the application
    '''
    def get_sequence_number_for_process(self, uid, seq=0):
        if uid in self.latest_deliveries:
            seq_out = self.latest_deliveries[uid]
        else: # This happens if no seq is found e.g when node joined the group -> set seq to seq received -1
            if seq - 1 == 0: # Edge Case: Two drones join simultaniosly -> cannot get msg with id 0
                self.latest_deliveries[uid] = 1
                seq_out = 1
            else:
                self.latest_deliveries[uid] = seq - 1
                seq_out = seq - 1
        return seq_out

    '''
    This Method sends a negative ack message to P_uid and requests message with id seq
    '''
    def send_negative_ack_for_seq(self, msg: Message, seq):
        lg.info(f"sending negative ack for message with seq:{seq}")
        self.ip_sender.send_message_unicast(msg.header[DefaultHeaders.ORIGIN_IP],
                                            msg.header[DefaultHeaders.UNICAST_PORT],seq,
                                            {DefaultHeaders.TYPE: DefaultMessageTypes.NEGATIVE_ACK})

    def recived_neg_ack_message(self, msg : Message):
        lg.info(f"received negative ack for message with seq:{msg.body}")
        if msg.body in self.sendt_messages:
            msg_to_resend = self.sendt_messages[msg.body]
            msg_to_resend.seq = msg.body
            msg_to_resend.acks = self.latest_deliveries
            self.ip_sender.send_message_multicast(msg_to_resend)

    def deliver_items_from_hb(self, uid, seq):
        for msg in self.hold_back_queue:
            if msg.seq == seq and msg.header[DefaultHeaders.UID] == uid:
                lg.info(f"delivering from holdbackqueue <------------------------------------------- {msg.seq}")
                self.latest_deliveries[uid] += 1
                self.deliverToApplication(msg)
                self.hold_back_queue.remove(msg)
                self.deliver_items_from_hb(uid, seq+1)

