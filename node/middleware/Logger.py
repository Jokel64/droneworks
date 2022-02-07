import logging
import io

lg = logging.getLogger('basic_logger')
lg.setLevel(logging.INFO)
log_capture_string = io.StringIO()
_ch = logging.StreamHandler(log_capture_string)
formatter = logging.Formatter('%(relativeCreated)6d %(levelname)s %(message)s')
_ch.setFormatter(formatter)

lg.addHandler(_ch)

def get_log():
    return log_capture_string.getvalue().replace("\n", "<br>")