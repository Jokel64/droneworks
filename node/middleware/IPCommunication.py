import socket
import threading
import struct
import json
import time

from Configuration import encoding
from Messaging import Message, DefaultHeaders, DefaultMessageTypes
from Utils import getCurrentIpAddress
from Logger import lg



class IPSender:
    def __init__(self, multicast_addr, mcast_port, uncast_port, additional_default_headers, uid, cb_lost_connection):
        self.multicast_addr = multicast_addr
        self.mcast_port = mcast_port
        self.uncast_port = uncast_port
        self.mcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.mcast_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        self.uncast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.leave_out_intervall = 5
        self.leave_out_counter = 0

        if additional_default_headers is None:
            self.additional_default_headers = {}
        else:
            self.additional_default_headers = additional_default_headers
        self.uid = uid

        self.cb_lost_connection = cb_lost_connection

    def _generate_default_header(self, destination_ip):
        return self.additional_default_headers | {DefaultHeaders.ORIGIN_IP: getCurrentIpAddress(), DefaultHeaders.UNICAST_PORT: self.uncast_port , DefaultHeaders.DESTINATION_IP: destination_ip,
                                                  DefaultHeaders.UID: self.uid}

    def send_message_multicast(self, message: Message):
        #if self.leave_out_intervall <= self.leave_out_counter:
        #    self.leave_out_counter = 0
        #    return

        self.leave_out_counter += 1

        if message.header is None:
            message.header = {}

        message.header = message.header | self._generate_default_header(self.multicast_addr)
        msg_str = json.dumps(message.__dict__)
        try:
            self.mcast_sock.sendto(msg_str.encode(), (self.multicast_addr, self.mcast_port))
        except OSError as e:
            lg.error(f"Error sending multicast Message: {e}. Starting new socket.")
            self.cb_lost_connection()

        lg.debug(f"Message send mc: {msg_str}")


    def send_message_unicast(self, destination_ip, destination_port,message_body, custom_headers):
        if custom_headers is None:
            custom_headers = {}

        msg = Message(self._generate_default_header(destination_ip) | custom_headers, message_body)
        msg_str = json.dumps(msg.__dict__)
        try:
            self.uncast_sock.sendto(msg_str.encode(), (destination_ip, destination_port))
        except OSError as e:
            lg.error(f"Error sending unicast Message: {e}")
        lg.debug(f"Message send uc: {msg_str}")


"""
This Class wraps some basic Receive Functionalities around the basic OS-Socket Library
"""
class IPReceiver:
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
            self.uncast_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.uncast_sock.bind((self.UNCAST_ADDR, self.UNCAST_PORT))

            # Start Threads
            mcast_thread = threading.Thread(target=self._t_run_mcast_receiver_loop, args=(cb_mc,), kwargs={})
            mcast_thread.start()
            uncast_thread = threading.Thread(target=self._t_run_uncast_receiver_loop, args=(cb_uncast,), kwargs={})
            uncast_thread.start()

            lg.debug("Reactor Running")

        def reset_connection(self):
            self.mcast_sock.close()
            self.mcast_sock.bind(('', self.MCAST_PORT))

        def _t_run_mcast_receiver_loop(self, cb):
            while (not self.stopReceiving):
                try:
                    msg_received = self.mcast_sock.recv(10240)
                except Exception as e:
                    lg.error(f"Couldn't receive multicast message: {e}")

                msg_received = str(msg_received, encoding)
                msg_received = json.loads(msg_received)
                msg_received = Message(**msg_received)
                cb(msg_received)

        def _t_run_uncast_receiver_loop(self, cb):
            while (not self.stopReceiving):
                msg_received = self.uncast_sock.recv(10240)
                msg_received = str(msg_received, encoding)
                msg_received = json.loads(msg_received)
                msg_received = Message(**msg_received)
                cb(msg_received)

        def shutdownReceiver(self):
            self.stopReceiving = True