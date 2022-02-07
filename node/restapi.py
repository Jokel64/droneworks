from flask_classful import FlaskView, route
from flask import request
from engine import World, FlightController, C3d
import json


class RestApi(FlaskView):
    def __init__(self):
        self.world = 2

    @classmethod
    def set_super_references(cls, world: World, fc: FlightController):
        cls.world = world
        cls.fc = fc

    def index(self):
        # http://localhost:5000/
        return f"<h1>Position: {self.__class__.world.position}</h1>"

    #Crappy Code lol
    @route('/command/', methods=['POST', 'GET'])
    def command(self):
        self.__class__.fc.go_to_point(C3d(int(json.loads(request.data)['x']), int(json.loads(request.data)['y']), int(json.loads(request.data)['z'])))
        return f"data:{request.data}"


# unused code (trash, but maybe not)
"""
app.config.from_object(__name__)

# enable CORS
CORS(app, resources={r'/*': {'origins': '*'}})

@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/ping', methods=['GET'])
def ping_pong():
    return jsonify('flask pong!')

@app.route('/drone_pos', methods=['GET'])
def get_drone_pos():
    pos_list = []
    for i in range(5):
        pos_list.append(i)
    return jsonify(pos_list)
"""

if __name__ == '__main__':
    pass
    #app.run()
