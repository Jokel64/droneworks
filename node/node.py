"""
Contains the main Object that holds all functionality.
"""

from middleware.Middleware import Middleware, Message, DefaultMessageTypes, getCurrentIpAddress
from middleware.MiddelwareEvents import MiddlewareEvents
import threading
from middleware.Logger import lg

from engine import World, FlightController, C3d
import random
from dash_wrapper import t_dash_interface, set_leader_content, set_slave_content
from middleware.MiddelwareEvents import MiddlewareEvents

from middleware.Configuration import UNCAST_PORT
from middleware.IPCommunication import DefaultHeaders

import shape_logic

class NodeState:
    INIT = 'init'

class CustomMessageTypes:
    NEW_POSITION = "NEW_POSITION"

class DWNode:
    def __init__(self, world_kwargs=None):
        self.State = NodeState.INIT
        self.node_list = dict()
        self.event_engine = MiddlewareEvents()

        # Engine
        x = random.uniform(-10, 10)
        y = random.uniform(-10, 10)
        z = random.uniform(-10, 10)

        self.world = None
        if world_kwargs is None:
            self.world = World(max_drone_force=C3d(1.5, 1.5, 1.5), weight=0.2, start_position=C3d(x, y, z))
            self.flight_controller = FlightController(world_ref=self.world, start_destination=C3d(x, y, z))
        else:
            self.world = World(**world_kwargs)
            self.flight_controller = FlightController(world_ref=self.world, start_destination=C3d(0, 0, 0))

        self.dash_thread = None
        self.world.run_simulation()
        self.flight_controller.run_controller()

        self.middleware = Middleware(self.event_engine, self.cb_multicast_message_received_handler, self.cb_uncast_message_received, self.cb_heartbeat_payload)
        self.readable_name = self.middleware.readable_name

        # Shapes
        self.available_shapes = shape_logic.get_available_shapes()
        self.selected_shape = None

        self.event_engine.register_event(MiddlewareEvents.SELF_ELECTED_AS_LEADER, self.handler_self_elected_as_leader)
        self.event_engine.register_event(MiddlewareEvents.LOST_LEADER_STATUS, self.handler_lost_leader_status)

        self.dash_thread = threading.Thread(target=t_dash_interface, args=(getCurrentIpAddress(), self.node_list, self.cb_new_shape_selected, self.available_shapes, ))
        self.dash_thread.start()

        print(f"Node init complete. Readable Name: {self.readable_name}, IP: {self.middleware.ip}")



    def handler_self_elected_as_leader(self):
        lg.info("Starting Dash interface as leader.")
        set_leader_content()

    def handler_lost_leader_status(self):
        lg.info("Starting Dash interface as slave.")
        set_slave_content()

    def cb_new_shape_selected(self, shape):
        lg.info(f"New shape selected: {shape}")
        self.selected_shape = shape
        ss = shape_logic.ShapeStep(svg_path=f'shapes/{shape}', height_level=2)
        pos = ss.get_positions(len(self.node_list))
        for key, i in zip(self.node_list, range(len(self.node_list))):
            peer = self.node_list[key]["peer"]
            lg.info(f"Sending {peer.ip} to destination {str(pos[i])}")
            self.middleware.mc_sender.send_message_unicast(peer.ip, UNCAST_PORT, {'dest': pos[i].__dict__},
                                                           {DefaultHeaders.TYPE: CustomMessageTypes.NEW_POSITION})


    def cb_heartbeat_payload(self):
        return {"pos": self.world.position.__dict__,
         "vel": str(self.world.velocity), "acc": str(self.world.acceleration)}

    def cb_uncast_message_received(self, msg:Message):
        if msg.get_header(DefaultHeaders.TYPE) == CustomMessageTypes.NEW_POSITION:
            lg.info(f"Received new destination from leader: {msg.body['dest']}")
            new_point = C3d(msg.body['dest'])
            self.flight_controller.go_to_point(new_point)
        else:
            lg.warn(f"Got unhandeled unicast msg: {msg.header}")

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
