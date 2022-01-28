import logging
import time

from node import DWNode
from flask import Flask, request

from engine import C3d

node = DWNode()

app = Flask(__name__)

port=3300



@app.route("/", methods=["POST"])
def index_post():
    x = float(request.form["x"])
    y = float(request.form["y"])
    z = float(request.form["z"])
    node.flight_controller.go_to_point(C3d(x, y, z))
    return index_get()

@app.route("/", methods=["GET"])
def index_get():
    entries = ""
    for key, val in vars(node).items():
        if key == "node_list":
            buf = ""
            for k, v in val.items():
                peer = v['peer']
                last_alive_sec_ago = time.time() - peer.last_alive
                offline = not peer.is_online()
                buf += f"<span style=\"{'color: red' if offline else ''}\">IP: <a href=\"http://{peer.ip}:{port}\">{peer.ip}</a> | Last Alive " \
                       f"{round(last_alive_sec_ago, ndigits=5)}s ago | Leader: {peer.is_leader} | UUID: {peer.uid} {'[OFFLINE]' if offline else ''}</span><br>"
            val = buf
        entries += f"<tr><td>{key}</td><td>{val}</td></tr>"

    return f"""<!DOCTYPE html><html><head><style>offline ? ''
table, form {{font-family: arial, sans-serif;border-collapse: collapse;width: 100%;}}
td, th {{border: 1px solid #dddddd;text-align: left;padding: 8px;}}
tr:nth-child(even) {{background-color: #dddddd;}}
</style></head><body><h2>{node.readable_name} [{node.middleware.ip}]</h2><table><tr><th>Key</th><th>Value</th>
  </tr>{entries}</table><form method="POST"><br><b>Go to destination manually</b><br>X:<input type="number" name="x" value=0> 
  Y:<input type="number" name="y" value=0> Z:<input type="number" name="z" value=0> 
  <input type="submit" name="new_dest" value="Go"></form></body></html>"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
