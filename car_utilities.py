import time
import debugpy

from constants import (
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    DIRECTION_BACKWARD,
    DIRECTION_FORWARD,
)


def move_car(arduino, direction):
    if arduino is not None:
        try:
            if direction == DIRECTION_LEFT:
                arduino.write(("H,255,0".encode("utf-8")))
            elif direction == DIRECTION_RIGHT:
                arduino.write(("H,0,-255".encode("utf-8")))
            elif direction == DIRECTION_FORWARD:
                arduino.write(("H,255,255".encode("utf-8")))
            elif direction == DIRECTION_BACKWARD:
                arduino.write(("H,-255,-255".encode("utf-8")))
            else:
                arduino.write(("H,0,0".encode("utf-8")))
            print(f"Sent command: {direction}")
        except Exception as e:
            print(f"Error sending direction: {e}")
