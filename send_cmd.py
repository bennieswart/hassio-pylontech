#!/usr/bin/env python3

import argparse

from monitor import serial_command

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a command to the battery and read the response")
    parser.add_argument("device", help="Battery IO device")
    parser.add_argument("command", help="Command to send")
    args = parser.parse_args()

    response = serial_command(args.device, args.command)
    print(f"Response length: {len(response)}")
    print(response)
