import os, sys
import socket
import uuid

projectDirectory = os.getcwd()
sys.path.append(projectDirectory+'/middleware')


from middleware.Logger import lg, get_log
from middleware.Utils import getCurrentIpAddress
import time

from node import DWNode
from flask import Flask, request

from engine import C3d
import middleware.Configuration as Config


node = DWNode()

app = Flask(__name__)

port=3300


def getNextFreePort():
    # Init Uncast socket

    portSearch = port

    while portSearch <= port+100:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', portSearch))
            sock.close()
            return portSearch
        except:
            portSearch += 1
    return None


@app.route("/", methods=["POST"])
def index_post():
    if "kill" in request.form:
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
                    #dirty way for new port calcualtion
                    info_port = port +  (peer.port - 5008)

                    buf += f"<span style=\"color:{textcolor}\">IP: <a href=\"http://{peer.ip}:{info_port}\")>{peer.ip}</a> Port:({peer.port})| Last Alive " \
                           f"{'{:05.2f}'.format(last_alive_sec_ago)}s ago | Leader: {isleader} | UUID: {peer.uid} [{uuid.UUID(peer.uid).time}] {'[OFFLINE]' if offline else ''}</span><br>"
                val = buf
            entries += f"<tr><td>{key}</td><td>{val}</td></tr>"
        except:
            entries += "<tr><td>Error</td><td>Error</td></tr>"
        #<meta http-equiv="refresh" content="5">
    return f"""<!DOCTYPE html><html><head><style>offline ? ''
table, form {{font-family: arial, sans-serif;border-collapse: collapse;width: 100%;}}
td, th {{border: 1px solid #dddddd;text-align: left;padding: 8px;}}
tr:nth-child(even) {{background-color: #dddddd;}}
</style></head><body style="font-family: monospace;"><h2>{node.readable_name} [{getCurrentIpAddress()}]</h2><table><tr><th>Key</th><th>Value</th>
  </tr>{entries}</table><form method="POST"><br><b>Go to destination manually</b><br>X:<input type="number" name="x" value=0> 
  Y:<input type="number" name="y" value=0> Z:<input type="number" name="z" value=0> 
  <input type="submit" name="new_dest" value="Go"></form>
  <h2>Kill this node</h2>
  <form method="POST"><input type="submit" name="kill" value="Kill me pls"></form>
  <div style="margin-top: 15px"><h2>Log</h2><span>{get_log()}</span></div></body></html>"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=getNextFreePort())
