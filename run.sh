#!/bin/sh

CONFIG_PATH=./data/options.json

config() { if [ -f "$CONFIG_PATH" ]; then jq -r ".$1 // empty" $CONFIG_PATH; fi }

export DEVICE=${DEVICE:-"$(config device)"}
export MQTT_SERVER=${MQTT_SERVER:-"$(config mqtt_server)"}
export MQTT_USER=${MQTT_USER:-"$(config mqtt_user)"}
export MQTT_PASS=${MQTT_PASS:-"$(config mqtt_pass)"}
export MQTT_CLIENT_ID=${MQTT_CLIENT_ID:-"$(config mqtt_client_id)"}
export MQTT_TOPIC=${MQTT_TOPIC:-"$(config mqtt_topic)"}
export SLEEP_INTERVAL=${SLEEP_INTERVAL:-"$(config sleep_interval)"}

echo ""
echo "Running monitor.py with the following settings:"
echo "  DEVICE: $DEVICE"
echo "  MQTT_SERVER: $MQTT_SERVER"
echo "  MQTT_USER: $MQTT_USER"
echo "  MQTT_PASS: $MQTT_PASS"
echo "  MQTT_CLIENT_ID: $MQTT_CLIENT_ID"
echo "  MQTT_TOPIC: $MQTT_TOPIC"
echo "  SLEEP_INTERVAL: $SLEEP_INTERVAL"
echo ""

trap 'kill -s INT $mainpid' SIGINT
trap 'kill -s TERM $mainpid' SIGTERM

# Run monitor.py. Using a background process with `wait` allows signal traps to have immediate effect.
./monitor.py &
mainpid=$!
while kill -0 $mainpid &> /dev/null; do
    wait $mainpid
done
wait $mainpid
exit $?
