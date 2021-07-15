FROM python:3.8

RUN mkdir /app

WORKDIR /app

COPY requirements.txt /app/

RUN apt-get update -y && \
    apt-get install -y libmosquitto-dev libffi-dev gcc make && \
    pip3 install -r requirements.txt && \
    apt-get purge -y gcc make && \
    rm -rf /root/.cache/ && \
    rm -rf /var/lib/apt /var/lib/dpkg

COPY *.py /app/

CMD [ "python", "/app/bme680_mqtt.py"]
