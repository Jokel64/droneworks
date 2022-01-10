"""
Contains the main Object that holds all functionality.
"""

from middleware.communication import MulticastSender, MulticastReceiver, MCAST_GRP, MCAST_PORT,\
    DynamicDiscoveryHandler, getCurrentIpAddress, MessageTypes
import time
import threading
import uuid
import logging as lg
import names

from engine import World, FlightController, C3d
import random

lg.basicConfig(level=lg.INFO, format='%(relativeCreated)6d %(threadName)s %(message)s')

class DWNode:
    def __init__(self, heartbeat_rate_s=1, leader_control_rate_s=2, node_offline_timeout_s=3, world_kwargs=None):
        # Error checks
        if heartbeat_rate_s >= node_offline_timeout_s:
            ValueError("Heartbeat rate must be faster than the node offline_timeout")

        # Settings
        self.heartbeat_rate_s = heartbeat_rate_s
        self.leader_control_rate_s = leader_control_rate_s
        self.node_offline_timeout_s = node_offline_timeout_s

        # Other Properties
        self.uuid = uuid.uuid4()
        self.readable_name = names.get_full_name()
        self.node_list = dict()
        self.is_leader = False
        self.leader_uuid = None

        # Engine
        x = random.uniform(-10, 10)
        y = random.uniform(-10, 10)
        z = random.uniform(-10, 10)
        if world_kwargs is None:
            self.world = World(max_drone_force=C3d(1.5, 1.5, 1.5), weight=0.2, start_position=C3d(x, y, z))
            self.flight_controller = FlightController(world_ref=self.world, start_destination=C3d(x, y, z))
        else:
            self.world = World(**world_kwargs)
            self.flight_controller = FlightController(world_ref=self.world, start_destination=C3d(0, 0, 0))

        # Empty Initializations
        self.ip = None

        # Network Interfaces
        self.mc_sender = MulticastSender(MCAST_GRP, MCAST_PORT)
        self.mc_rec = MulticastReceiver(MCAST_GRP, MCAST_PORT, None)
        self.ddh = DynamicDiscoveryHandler(self.mc_sender)

        # Threads
        self.heartbeat_thread = threading.Thread(target=self._t_heartbeat)
        self.leader_thread = threading.Thread(target=self._t_leader_control_and_node_garbage_collection)

        # Start Threads
        self.heartbeat_thread.start()
        self.leader_thread.start()
        self.mc_rec.startReceiving(self.cb_multicast_message_received_handler)

        self.world.run_simulation()
        self.flight_controller.run_controller()

    """
    This thread sends out the heartbeat at the rate of self.heartbeat_rate_s
    """
    def _t_heartbeat(self):
        while True:
            self.ip = getCurrentIpAddress()
            self.ddh.BrodcastIdAndAddress(self.uuid, getCurrentIpAddress())
            time.sleep(self.heartbeat_rate_s)
            False

    """
    This thread checks whether a leader is present in the network and initiates the election process if not.
    It also throws out every node from the node_list that has had a timeout.
    """
    def _t_leader_control_and_node_garbage_collection(self):
        while True:
            leader_found = False
            for node in self.node_list:
                if not self.node_still_online(node):
                    del self.node_list[node]

                if self.node_list[node]["leader"]:
                    self.leader_uuid = node
                    leader_found = True
                    break

            # No leader found
            if not leader_found:
                lg.info("No leader found. Init leader election process.")
                self._init_leader_election()

            time.sleep(self.leader_control_rate_s)

    def _init_leader_election(self):
        time.sleep(10)
        pass

    def node_still_online(self, node_uuid):
        return time.time() - self.node_list[node_uuid]["last_alive"] < self.node_offline_timeout_s

    def cb_multicast_message_received_handler(self, msg_received):
        #print(f"Message arrived: Type:{msg_recived.messageType}, Body:{msg_recived.messageBody}")
        if msg_received.messageType == MessageTypes.heartbeat:
            split = msg_received.messageBody.split(",")
            id = split[0]
            ip = split[1]
            self.node_list[id] = dict()
            self.node_list[id]["ip"] = ip
            self.node_list[id]["last_alive"] = time.time()
            self.node_list[id]["uuid"] = id
            self.node_list[id]["leader"] = False
        else:
            lg.error(f'Message Type "{msg_received.messageType}" unknown.')
