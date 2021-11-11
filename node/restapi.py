from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
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

if __name__ == '__main__':
    app.run()
