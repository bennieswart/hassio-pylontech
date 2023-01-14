#!/usr/bin/env python3

import argparse
import time
import json
import os
import paho.mqtt.client as mqtt


MARK_BEGIN = b"\n\r@\r\r\n"
MARK_END = b"\r\n\rCommand completed successfully\r\n\r$$\r\n\rpylon>"

MAX_PROBE_TRIES = 3

def probe(file):
    try:
        os.write(file, b"\n")
        time.sleep(0.01)
        os.read(file, 256)
        return True
    except Exception:
        time.sleep(0.5)

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

        tries = 0
        while True:
            if tries > MAX_PROBE_TRIES:
                raise RuntimeError("Probing failed")
            tries += 1
            if probe(file):
                break

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
        lines = [[f.strip() for f in l.split(" ") if f.strip()] for l in response.split("\n")]
        if lines[0] != ["Power", "Volt", "Curr", "Tempr", "Tlow", "Thigh", "Vlow", "Vhigh", "Base.St", "Volt.St", "Curr.St", "Temp.St", "Coulomb", "Time", "B.V.St", "B.T.St", "MosTempr", "M.T.St"]:
            raise AssertionError("Table columns different than expected")

        stateidx = lines[0].index("Base.St")
        lines = [l for l in lines if l[stateidx] != "Absent"]

        timeidx = lines[0].index("Time")
        for l in lines[1:]:
            l[timeidx] = l[timeidx] + " " + l.pop(timeidx + 1)

        for l in lines:
            if len(l) != len(lines[0]):
                raise AssertionError("Table row has incorrect number of items")

        items = [dict(zip(lines[0], l)) for l in lines[1:]]
        for l in items:
            l["Power"] = int(l["Power"])
            l["Volt"] = int(l["Volt"])
            l["Curr"] = int(l["Curr"])
            l["Tempr"] = int(l["Tempr"])
            l["Tlow"] = int(l["Tlow"])
            l["Thigh"] = int(l["Thigh"])
            l["Vlow"] = int(l["Vlow"])
            l["Vhigh"] = int(l["Vhigh"])
            l["Coulomb"] = int(l["Coulomb"][:-1])
            l["MosTempr"] = int(l["MosTempr"])

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
