import logging
import uuid

from middleware.communication import CommunicationController, MulticastReceiver, MulticastSender

from restapi import RestApi
from flask import Flask
from flask_cors import CORS
from engine import World, FlightController, C3d
from time import sleep

app = Flask(__name__)

world = World(max_drone_force=C3d(1.5, 1.5, 1.5), weight=0.2, start_position=C3d(0, 0, 0))
fc = FlightController(world_ref=world, start_destination=C3d(0, 0, 0))

RestApi.register(app, route_base='/')
# enable CORS
CORS(app, resources={r'/*': {'origins': '*'}})

# Sets all references the rest api needs access to. A bit hacky.
RestApi.set_super_references(world=world, fc=fc)


world.run_simulation()

fc.run_controller()
fc.go_to_point(C3d(0, 0, 0))

#Communication Implementation
com_controller = CommunicationController(uuid.uuid4(), fc)