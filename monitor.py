#!/usr/bin/env python3

import argparse
import time
import json
import os
import re

import paho.mqtt.client as mqtt


MARK_BEGIN = b"\n\r@\r\r\n"
MARK_END = b"\r\n\rCommand completed successfully\r\n\r$$\r\n\rpylon>"


def mqtt_connect(*, server, username, password, client_id):
    client = mqtt.Client(client_id=client_id)
    client.username_pw_set(username, password)
    client.connect(server)
    return client


def serial_command(device, command, *, retries=1):
    print(f"Sending command {command}")
    command_bytes = command.encode()
    try:
        try:
            file = os.open(device, os.O_RDWR | os.O_NONBLOCK)
        except Exception as e:
            raise RuntimeError(f"Error opening device {device}") from e

        os.write(file, command_bytes + b"\n")

        response = b""
        timeout_counter = 0
        while MARK_END not in response:
            if timeout_counter > 1000:
                raise RuntimeError("Read operation timed out")
            timeout_counter += 1
            try:
                response += os.read(file, 256)
            except Exception:
                time.sleep(0.02)

        response = response.rstrip()
        if not (response.startswith(command.encode() + MARK_BEGIN) and response.endswith(MARK_END)):
            raise Exception("Response frame corrupt")
        response = response[len(command) + len(MARK_BEGIN):-len(MARK_END)]
        return response.decode()
    except Exception as e:
        if retries:
            print(f"Error sending command {command}, {retries} retries remaining")
            time.sleep(0.1)
            os.write(file, b"\n") # Try to clear prompt and recover
            return serial_command(device, command, retries=retries-1)
        raise RuntimeError(f"Error sending command {command}")
    finally:
        try:
            os.close(file)
        except Exception:
            pass


def get_power(device):
    response = serial_command(device, "pwr")
    try:
        lines = response.split("\n")

        colstart = [0]
        for m in re.findall(r"([^ ]+ +)", lines[0].rstrip()):
            colstart.append(colstart[-1] + len(m))

        def getcell(line, cellno):
            linelen = len(line)
            offset1 = min(linelen, colstart[cellno])
            if offset1 and line[offset1-1] != " ":
                offset1 -= 1
            offset2 = min(linelen, colstart[cellno+1] if cellno+1 < len(colstart) else len(line))
            if line[offset2-1] != " ":
                offset2 -= 1
            return line[offset1:offset2].strip()

        headers = [getcell(lines[0], i) for i in range(len(colstart))]

        items = []
        for line in lines[1:]:
            values = [getcell(line, i) for i in range(len(colstart))]
            item = dict(zip(headers, values))
            if item["Base.St"] == "Absent":
                continue

            for k in ("Power", "Volt", "Curr", "Tempr", "Tlow", "Thigh", "Vlow", "Vhigh", "MosTempr"):
                try:
                    item[k] = int(item[k])
                except Exception:
                    pass
            try:
                item["Coulomb"] = int(item["Coulomb"][:-1])
            except Exception:
                pass
            items.append(item)

        return items
    except Exception as e:
        raise RuntimeError(f"Error parsing power ({response})") from e


def send_data(client, topic, data):
    try:
        client.publish(topic, data, 0, True)
    except Exception as e:
        raise RuntimeError("Error sending data to mqtt server") from e


def main(
    *,
    device,
    mqtt_server,
    mqtt_user,
    mqtt_pass,
    mqtt_client_id,
    mqtt_topic,
    sleep_iteration=0,
):
    client = mqtt_connect(
        server=mqtt_server,
        username=mqtt_user,
        password=mqtt_pass,
        client_id=mqtt_client_id,
    )

    print(f"Reading from battery\n")

    while True:
        start = time.time()

        data = json.dumps(get_power(device))
        print("power", data, "\n")
        send_data(client, mqtt_topic, data)

        time.sleep(max(0, sleep_iteration - (time.time() - start)))


if __name__ == "__main__":
    def env(var, val=None):
        return {"default": os.environ.get(var)} if os.environ.get(var) else \
               {"default": val} if val is not None else \
               {"required": True}
    parser = argparse.ArgumentParser(description="""
        Monitor battery parameters and send them to an MQTT server.
        Arguments can also be set using their corresponding environment variables.
    """)
    parser.add_argument("--device", **env("DEVICE"), help="Battery IO device")
    parser.add_argument("--mqtt-server", **env("MQTT_SERVER"), help="MQTT server address")
    parser.add_argument("--mqtt-user", **env("MQTT_USER"), help="MQTT username")
    parser.add_argument("--mqtt-pass", **env("MQTT_PASS"), help="MQTT password")
    parser.add_argument("--mqtt-client-id", **env("MQTT_CLIENT_ID"), help="MQTT client id")
    parser.add_argument("--mqtt-topic", **env("MQTT_TOPIC"), help="MQTT topic for data")
    parser.add_argument("--sleep-iteration", type=float, **env("SLEEP_ITERATION", 5), help="Seconds between iteration starts")
    args = parser.parse_args()

    main(
        device=args.device,
        mqtt_server=args.mqtt_server,
        mqtt_user=args.mqtt_user,
        mqtt_pass=args.mqtt_pass,
        mqtt_client_id=args.mqtt_client_id,
        mqtt_topic=args.mqtt_topic,
        sleep_iteration=args.sleep_iteration,
    )
