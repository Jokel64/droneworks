import sys

from logger import lg, get_log
import time

from node import DWNode
from flask import Flask, request

from engine import C3d

node = DWNode()

app = Flask(__name__)

port=3300

@app.route("/", methods=["POST"])
def index_post():
    if request.form["kill"]:
        lg.error("Not yet implemented.")
    else:
        x = float(request.form["x"])
        y = float(request.form["y"])
        z = float(request.form["z"])
        node.flight_controller.go_to_point(C3d(x, y, z))
    return index_get()

@app.route("/", methods=["GET"])
def index_get():
    entries = ""
    for key, val in vars(node).items():
        try:
            if key == "node_list":
                buf = ""
                for k, v in sorted(val.items(), key=lambda item: item[1]['peer'].ip):
                    peer = v['peer']
                    last_alive_sec_ago = time.time() - peer.last_alive
                    offline = not peer.is_online()
                    isleader = node.middleware.is_uid_leader(peer.uid)
                    textcolor = 'grey'
                    if isleader:
                        textcolor = 'green'
                    elif offline:
                        textcolor = 'red'
                    buf += f"<span style=\"color:{textcolor}\">IP: <a href=\"http://{peer.ip}:{port}\">{peer.ip}</a> | Last Alive " \
                           f"{'{:05.2f}'.format(last_alive_sec_ago)}s ago | Leader: {isleader} | UUID: {peer.uid} {'[OFFLINE]' if offline else ''}</span><br>"
                val = buf
            entries += f"<tr><td>{key}</td><td>{val}</td></tr>"
        except:
            entries += "<tr><td>Error</td><td>Error</td></tr>"

    return f"""<!DOCTYPE html><html><head><meta http-equiv="refresh" content="5"><style>offline ? ''
table, form {{font-family: arial, sans-serif;border-collapse: collapse;width: 100%;}}
td, th {{border: 1px solid #dddddd;text-align: left;padding: 8px;}}
tr:nth-child(even) {{background-color: #dddddd;}}
</style></head><body style="font-family: monospace;"><h2>{node.readable_name} [{node.middleware.ip}]</h2><table><tr><th>Key</th><th>Value</th>
  </tr>{entries}</table><form method="POST"><br><b>Go to destination manually</b><br>X:<input type="number" name="x" value=0> 
  Y:<input type="number" name="y" value=0> Z:<input type="number" name="z" value=0> 
  <input type="submit" name="new_dest" value="Go"></form>
  <h2>Kill this node</h2>
  <form method="POST"><input type="submit" name="kill" value="Kill me pls"></form>
  <div style="margin-top: 15px"><h2>Log</h2><span>{get_log()}</span></div></body></html>"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
