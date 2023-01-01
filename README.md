### This is a [hassio](https://hass.io) addon to monitor [pylontech batteries](https://en.pylontech.com.cn/pro_detail.aspx?id=121&cid=23).

<img src="https://en.pylontech.com.cn/A_UpLoad/upload_pic/20211209/20211209123155_9976.jpg" width="300" />

The battery is connected by RS232 and data is published as JSON to an MQTT broker. It publishes the data to the following topic:

- 'power/pylon' for the data from the master battery and slaves

You can then configure the sensors in Home Assistant like this:

```
sensors:
  - platform: mqtt
    name: "Battery1 SOC"
    state_topic: "power/pylon"
    unit_of_measurement: '%'
    value_template: "{{ value_json[0].Coulomb }}"
```

See the function [get_power](./monitor.py#:~:text=def%20get_power) in [monitor.py](./monitor.py) for the values published on `power/pylon`.

### Install

Add https://github.com/bennieswart/home-assistant-addons to the addon store repositories and you will get a `Pylontech Battery` listed there.
Note that this assumes the battery is `/dev/ttyUSB`. If you have other USB to Serial devices connected this might be wrong.

### Manual build and run

```
# Build the docker image
docker build --build-arg BUILD_FROM=alpine -t pylon-monitor .

# Run the container
# You will need to edit options.json or add the proper environment variables
docker run                                     \
    -dit                                       \
    --name pylon-monitor                       \
    --device /dev/ttyUSB0                      \
    -v $(pwd)/options.json:/data/options.json  \
    -e MQTT_CLIENT_ID=pylon0                   \
    --restart unless-stopped                   \
    pylon-monitor
```

### Connection

You will need a pylontech console cable (RS232) to connect the master battery to your monitoring device's USB port.
This code only supports RS232 communication and will not work with RS485.

### Known working configurations

- Four Pylontech US3000C running on Raspberry Pi 4.
