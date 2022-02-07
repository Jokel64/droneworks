FROM python:3
COPY requirements.txt /
RUN pip install -r requirements.txt

ADD main.py /
ADD node.py /
ADD middleware/ /middleware/
ADD engine.py /
ADD shape_logic.py /
ADD dash_wrapper.py /
ADD shapes/ /shapes/





CMD [ "python", "./main.py" ]
