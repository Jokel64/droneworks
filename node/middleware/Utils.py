import socket

from Configuration import UNCAST_PORT

"""
This function returns the IP Address of the current System
"""
def getCurrentIpAddress():
    h_name = socket.gethostname()
    return socket.gethostbyname(h_name)

    #todo fix the problem when multiple networks exist
    #return "127.0.0.1"

def getNextFreePort():
    # Init Uncast socket

    return UNCAST_PORT

    #To disable the dynamic port allocation rmove line 18

    portSearch = UNCAST_PORT

    while portSearch <= UNCAST_PORT+100:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((getCurrentIpAddress(), portSearch))
            sock.close()
            return portSearch
        except:
            portSearch += 1

    return None