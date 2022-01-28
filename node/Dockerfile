FROM python:3
COPY requirements.txt /
RUN pip install -r requirements.txt

ADD main.py /
ADD node.py /
ADD middleware/communication.py /middleware/communication.py
ADD engine.py /
ADD dash_wrapper.py /




CMD [ "python", "./main.py" ]
