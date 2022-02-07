from Logger import lg


class MiddlewareEvents:
    SELF_ELECTED_AS_LEADER = "SELF_ELECTED_AS_LEADER"
    NO_VALID_LEADER = "NO_VALID_LEADER"
    NEW_VALID_LEADER_ASSIGNED = "NEW_VALID_LEADER_ASSIGNED"
    LOST_LEADER_STATUS = "LOST_LEADER_STATUS"

    def __init__(self):
        self._registered_events = dict()

    def register_event(self, event_type, handler):
        if event_type not in vars(MiddlewareEvents):
            Exception(f"Event type {event_type} unknown.")
        if event_type not in self._registered_events:
            self._registered_events[event_type] = list()
        self._registered_events[event_type].append(handler)

    def emit_event(self, event_type):
        lg.info(f"EventList in Emit: {self._registered_events}")

        if event_type in self._registered_events:
            for handler in self._registered_events[event_type]:
                try:
                    lg.info("Executing event handler.")
                    handler()
                except Exception as e:
                    lg.error(f"Error executing handler {handler}: {e}")
