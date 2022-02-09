import time

from Logger import lg
from Messaging import DefaultMessageTypes, DefaultHeaders
from Configuration import node_offline_timeout_s

"""
Information about a peer
"""
class Peer:
    def __init__(self, uid, origin_ip, port, readable_name="Not specified", **kwargs):
        self.uid = uid
        self.ip = origin_ip
        self.last_alive = time.time()
        self.heartbeats_received = 0
        self.port = port
        self.readable_name = readable_name

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