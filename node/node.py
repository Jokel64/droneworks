"""
Contains the main Object that holds all functionality.
"""

from middleware.communication import Middleware, Message, Peer, DefaultMessageTypes
import time
import threading
import logging as lg

from engine import World, FlightController, C3d
import random
from dash_wrapper import t_dash_interface, set_node_list

lg.basicConfig(level=lg.INFO, format='%(relativeCreated)6d %(threadName)s %(message)s')


class NodeState:
    INIT = 'init'


class DWNode:
    def __init__(self, world_kwargs=None):
        self.State = NodeState.INIT
        self.middleware = Middleware(self.cb_multicast_message_received_handler, self.cb_heartbeat_payload)
        self.readable_name = self.middleware.readable_name
        self.node_list = dict()

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

        self.dash_thread = threading.Thread(target=t_dash_interface)
        self.dash_thread.start()

        self.world.run_simulation()
        self.flight_controller.run_controller()

    def cb_heartbeat_payload(self):
        return {"pos": str(self.world.position),
         "vel": str(self.world.velocity), "acc": str(self.world.acceleration)}

    def cb_multicast_message_received_handler(self, msg_received: Message):

        if msg_received.header['type'] == DefaultMessageTypes.HEARTBEAT:
            uid = msg_received.header['uid']
            self.node_list[uid] = dict()
            self.node_list[uid]["pos"] = msg_received.body['pos']
            self.node_list[uid]["vel"] = msg_received.body['vel']
            self.node_list[uid]["acc"] = msg_received.body['acc']
            self.node_list[uid]["peer"] = self.middleware.peer_list[uid]
        else:
            lg.error(f'Message rec "{msg_received.body}".')
