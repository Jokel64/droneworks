import threading
import socket
import struct
import json
import logging

import schedule
import time

from types import SimpleNamespace

encoding = 'utf-8'

MCAST_GRP = '224.1.1.1'

MCAST_PORT = 5007

heartbeat_in_seconds = 10


"""
This Class wraps some basic Receive Functionalities around the basic OS-Socket Library
"""
class MulticastReceiver:
        def __init__(self, Multicast_Address, Multicast_Port, CommunicationController):
            self.Address = Multicast_Address
            self.Port = Multicast_Port
            self.CommunicationController = CommunicationController
            self.stopReceiving = False

        def initializeCommunication(self):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('', self.Port))
            mreq = struct.pack("=4sl", socket.inet_aton("224.1.1.1"), socket.INADDR_ANY)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        def runReceiverLoop(self, cb):
            while (not self.stopReceiving):
                msg_recived = self.sock.recv(10240)
                msg_recived = str(msg_recived,encoding)
                msg_recived = json.loads(msg_recived, object_hook=lambda d: SimpleNamespace(**d))
                cb(msg_recived)


        def startReceiving(self, cb):
            self.initializeCommunication()
            thread = threading.Thread(target=self.runReceiverLoop, args=(cb, ), kwargs={})
            thread.start()
            logging.debug("Reactor Running")

        def shutdownReceiver(self):
            self.stopReceiving = True


class MulticastSender:
    def __init__(self, MulticastAddr, Port):
        self.Addr = MulticastAddr
        self.Port = Port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    def sendMessage(self, message):
        messageString = json.dumps(message.__dict__)
        self.sock.sendto(messageString.encode(), (self.Addr, self.Port))
        logging.debug(f"Message send: {messageString}")


"""
This function returns the IP Address of the current System 
"""
def getCurrentIpAddress():
    h_name = socket.gethostname()
    IP_addres = socket.gethostbyname(h_name)
    return IP_addres

class Message:
    def __int__(self, messageType, messageBody):
        self.messageType = messageType
        self.messageBody = messageBody


class MessageTypes:
    heartbeat = "hb"


"""
This Class contains all logic regarding dynamic discovery of hosts.
*
"""
class DynamicDiscoveryHandler:
    def __init__(self, MulticastSender):
        self.IpLookupList = {1:'192.168.2.1', 2:'123.123.123.123'}
        self.MulticastSender = MulticastSender

    def getIpAddressForID(self, ID):
        message = Message()
        message.messageType = MessageTypes.heartbeat
        message.messageBody = ID
        self.MulticastSender.sendMessage(message)

    def startBrodcastIdAndAddress(self, ID, Address):
        schedule.every(heartbeat_in_seconds).seconds.do(lambda: self.BrodcastIdAndAddress(ID,Address))
        schedule.run_pending()
        while True:
            # Checks whether a scheduled task
            # is pending to run or not
            schedule.run_pending()
            time.sleep(1)

    def BrodcastIdAndAddress(self, ID, Address):
        message = Message()
        message.messageType = MessageTypes.heartbeat                       # 1=> DiscoveryBrodcast
        message.messageBody = f"{ID},{Address}"
        self.MulticastSender.sendMessage(message)


def RunScheduler():
    while True:
        # Checks whether a scheduled task
        # is pending to run or not
        schedule.run_pending()
        time.sleep(0.1)

"""
This Class reacts to all communication and redirects information to the other components
"""
class CommunicationController:
    def __init__(self,id, flightController):
        self.id = id
        self.flightController = flightController
        self.multicast_reciver = MulticastReceiver(MCAST_GRP, MCAST_PORT, self)
        self.multicast_reciver.startReceiving()
        self.multicast_sender = MulticastSender(MCAST_GRP, MCAST_PORT)
        self.dynamicDiscoveryHandler = DynamicDiscoveryHandler(self.multicast_sender)
        self.dynamicDiscoveryHandler.startBrodcastIdAndAddress(self.id,getCurrentIpAddress())

        threading.Thread(target=RunScheduler).run()

    def incomingMessage(self, message):
        if(message.messageType == "0"):
            print("Brdcast Received")
        if(message.messageType == "1"):
            print("Ask Received")




