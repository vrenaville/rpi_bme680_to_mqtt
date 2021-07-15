#!/usr/bin/env python3
# -*- coding: utf-8 -*-

mqtt_host = 'tracking.v6.rocks'
import paho.mqtt.client as paho
import bme680
import time
import fcntl
import json
import os
import logging
topic = 'envcontrol/rpi/rpi'
DST_MQTT_HOST = os.getenv("DST_MQTT_HOST")
DST_MQTT_USER = os.getenv("DST_MQTT_USER")
DST_MQTT_PASS = os.getenv("DST_MQTT_PASS")
VERSION = "v1.0"

def on_disconnect(mqtt, userdata, rc):
    print("Disconnected from MQTT server with code: %s" % rc)
    while rc != 0:
        try:
            time.sleep(1)
            rc = mqtt.reconnect()
        except:
            pass
        print("Reconnected to MQTT server.")

def build_json(user,date,subtopic,value):
    env_data = json.dumps({
        "date": date,
        "user": user,
        subtopic: value,
    })
    logging.info("publishing data to temperature via mqtt to topic %s", subtopic)
    return env_data


if __name__ == '__main__':

    logging.info("Start")
    mqtt = paho.Client()
    mqtt.username_pw_set(DST_MQTT_USER,DST_MQTT_PASS)
    mqtt.tls_set()
    mqtt.connect(DST_MQTT_HOST, 8883, 60)
    mqtt.on_disconnect = on_disconnect
    mqtt.loop_start()


    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S %Z'
    )

    try:
        while True:
            try:
                logging.info("Init")
                sensor = bme680.BME680(0x77)
                sensor.set_humidity_oversample(bme680.OS_2X)
                sensor.set_pressure_oversample(bme680.OS_4X)
                sensor.set_temperature_oversample(bme680.OS_8X)
                sensor.set_filter(bme680.FILTER_SIZE_3)
                sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

                sensor.set_gas_heater_temperature(320)
                sensor.set_gas_heater_duration(150)
                sensor.select_gas_heater_profile(0)

                start_time = time.time()
                burn_in_time = 300
                burn_in_data = []
                gas_baseline = None

                # Set the humidity baseline to 50%, typical for my room
                hum_baseline = 50

                # This sets the balance between humidity and gas reading in the
                # calculation of air_quality_score (25:75, humidity:gas)
                hum_weighting = 0.25

                while True:
                    logging.info("Get data")
                    if sensor.get_sensor_data():
                        now = time.time()
                        timestamp = int(now)
                        env_data = build_json('rpi',timestamp,'humidity',sensor.data.humidity)
                        mqtt.publish(topic + '/humidity', payload=env_data, retain=True)
                        env_data = build_json('rpi',timestamp,'barometer',sensor.data.pressure)
                        mqtt.publish(topic + '/barometer', payload=env_data, retain=True)
                        env_data = build_json('rpi',timestamp,'temperature',sensor.data.temperature)
                        mqtt.publish(topic + '/temperature', payload=env_data, retain=True)

                        if now - start_time < burn_in_time:
                            if sensor.data.heat_stable:
                                gas = sensor.data.gas_resistance
                                burn_in_data.append(gas)
                            logging.info("{}ºC\t{} %rH\t{} hPa".format(sensor.data.temperature, sensor.data.humidity, sensor.data.pressure))
                            time.sleep(1)

                        elif gas_baseline is None:
                            gas_baseline = sum(burn_in_data[-50:]) / 50.0
                            logging.info("{}ºC\t{} %rH\t{} hPa".format(sensor.data.temperature, sensor.data.humidity, sensor.data.pressure))
                            time.sleep(1)

                        else:
                            if sensor.data.heat_stable:
                                gas = float(sensor.data.gas_resistance)
                                gas_offset = gas_baseline - sensor.data.gas_resistance
                                hum = sensor.data.humidity
                                hum_offset = sensor.data.humidity - hum_baseline

                                if hum_offset > 0:
                                    hum_score = (100 - hum_baseline - hum_offset) / (100 - hum_baseline) * (hum_weighting * 100)
                                else:
                                    hum_score = (hum_baseline + hum_offset) / hum_baseline * (hum_weighting * 100)
                                if gas_offset > 0:
                                    gas_score = (gas / gas_baseline) * (100 - (hum_weighting * 100))
                                else:
                                    gas_score = 100 - (hum_weighting * 100)

                                aq_score = hum_score + gas_score
                                env_data = build_json('rpi',timestamp,'gas',gas)
                                mqtt.publish(topic + '/gas', payload=env_data, retain=True)
                                env_data = build_json('rpi',timestamp,'iaq',aq_score)
                                mqtt.publish(topic + '/iaq', payload=env_data, retain=True)
                                logging.info("{}ºC\t{} %rH\t{} hPa\t{} Ohms\t{}%".format(sensor.data.temperature, sensor.data.humidity, sensor.data.pressure, gas, aq_score))

                            time.sleep(10)
                    else:
                        logging.info("No data yet.")
            except IOError as e:
                logging.info("IOError: "+str(e))
                time.sleep(3)

    except KeyboardInterrupt:
        pass


