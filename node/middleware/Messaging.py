class Message:
    def __init__(self, header, body, seq=0, acks={}):
        self.header = header
        self.body = body
        self.seq = seq
        self.acks = acks

    def get_header(self, header_key):
        if header_key in self.header:
            return self.header[header_key]
        else:
            return None


class DefaultMessageTypes:
    HEARTBEAT = "heartbeat"
    LEADER_ELECTION_MESSAGE = "LEADER_ELECTION_MESSAGE"
    LEADER_ANSWER_MESSAGE = "LEADER_ANSWER_MESSAGE"
    LEADER_COORDINATOR_MESSAGE = "LEADER_COORDINATOR_MESSAGE"
    NEGATIVE_ACK = "NEGATIVE_ACK"


class DefaultHeaders:
    DESTINATION_IP = 'destination_ip'
    ORIGIN_IP = 'origin_ip'
    UNICAST_PORT = 'port'
    UID = 'uid'
    TYPE = 'type'
    READABLE_NAME = 'readable_name'
