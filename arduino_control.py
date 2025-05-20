import time
import debugpy
from constants import (
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    DIRECTION_FORWARD,
    DIRECTION_BACKWARD,
)
from pid import PIDController
from server import pipeline_server
            
def move_car_with_flush(arduino, user_data, direction, speed, modifier=0, max_speed=150, min_speed=90):
    """Send command with PID-controlled differential turning"""
    if arduino is not None:
        try:
            base_speed = max(min(speed, max_speed), min_speed)
            left_speed = base_speed
            right_speed = base_speed

            if direction in (DIRECTION_LEFT, DIRECTION_RIGHT):
                differential = abs(modifier)
                differential = min(differential, base_speed * pipeline_server.modifier)
                
                if direction == DIRECTION_LEFT:
                    left_speed = base_speed + differential
                    right_speed = base_speed - differential
                else:
                    left_speed = base_speed - differential
                    right_speed = base_speed + differential
                left_speed = max(min(left_speed, max_speed), min_speed)
                right_speed = max(min(right_speed, max_speed), min_speed)

            command = f"H,{left_speed},{right_speed}\n"
            
            if direction == "S":
                command = "H,0,0\n"
                user_data.pid.reset()
            print("Sending command:", command,pipeline_server.modifier,pipeline_server.height_modifier)
            arduino.write(command.encode("utf-8"))
            arduino.flush()

        except Exception as e:
            print("Error sending direction:", e)
