FROM python:3
ADD main.py /
ADD node.py /
ADD middleware/communication.py /middleware/communication.py
ADD engine.py /
ADD dash_wrapper.py /


RUN pip install schedule
RUN pip install names
RUN pip install flask
RUN pip install numpy
RUN pip install dash
RUN pip install plotly
RUN pip install pandas
RUN pip install dash-bootstrap-components

CMD [ "python", "./main.py" ]
