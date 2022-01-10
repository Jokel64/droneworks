FROM python:3
ADD main.py /
ADD node.py /
ADD middleware/communication.py /middleware/communication.py
ADD engine.py /


RUN pip install schedule
RUN pip install names
RUN pip install flask
RUN pip install numpy



CMD [ "python", "./main.py" ]
