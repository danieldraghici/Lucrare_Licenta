import time
import debugpy
from constants import (
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    DIRECTION_FORWARD,
    DIRECTION_BACKWARD,
    DIRECTION_STOP,
)
from server import pipeline_server

def send_error_with_mode(arduino, error, direction):
    if arduino is not None:
        try:
            mode_map = {
                DIRECTION_FORWARD: "F",
                DIRECTION_LEFT: "L", 
                DIRECTION_RIGHT: "R",
                DIRECTION_STOP: "S",
                DIRECTION_BACKWARD: "B"
            }
            
            mode_char = mode_map.get(direction, "F")
            command = f"E,{error:.2f},{mode_char}\n"
            print(f"Sending PID command - Error: {error:.2f}, Mode: {mode_char}")
            arduino.write(command.encode("utf-8"))
            arduino.flush()
        except Exception as e:
            print(f"Error sending PID command: {e}")

def send_direct_command(arduino, left_speed, right_speed):
    if arduino is not None:
        try:
            left_speed = max(-255, min(255, int(left_speed)))
            right_speed = max(-255, min(255, int(right_speed)))
            command = f"H,{left_speed},{right_speed}\n"
            print(f"Sending direct command - Left Speed: {left_speed}, Right Speed: {right_speed}")
            arduino.write(command.encode("utf-8"))
            arduino.flush()
        except Exception as e:
            print(f"Error sending motor command: {e}")

def set_pid_parameters(arduino, kp, ki, kd):
    if arduino is not None:
        try:
            command = f"P,{kp},{ki},{kd}\n"
            print(f"Setting PID parameters: Kp={kp}, Ki={ki}, Kd={kd}")
            arduino.write(command.encode("utf-8"))
            arduino.flush()
        except Exception as e:
            print(f"Error setting PID parameters: {e}")

def set_base_speed(arduino, speed):
    if arduino is not None:
        try:
            command = f"S,{speed}\n"
            print(f"Setting base speed: {speed}")
            arduino.write(command.encode("utf-8"))
            arduino.flush()
        except Exception as e:
            print(f"Error setting base speed: {e}")

def set_mode_bias(arduino, bias):
    if arduino is not None:
        try:
            command = f"B,{bias}\n"
            print(f"Setting mode bias: {bias}")
            arduino.write(command.encode("utf-8"))
            arduino.flush()
        except Exception as e:
            print(f"Error setting mode bias: {e}")

def stop_car(arduino):
    if arduino is not None:
        try:
            command = "X\n"
            arduino.write(command.encode("utf-8"))
            arduino.flush()
        except Exception as e:
            print(f"Error stopping car: {e}")

def reset_pid(arduino):
    if arduino is not None:
        try:
            command = "R\n"
            arduino.write(command.encode("utf-8"))
            arduino.flush()
        except Exception as e:
            print(f"Error resetting PID: {e}")

def move_car_with_flush(arduino, user_data, direction, speed):
    if arduino is not None:
        try:
            error = 0
            if hasattr(user_data, 'current_error') and user_data.current_error is not None:
                error = user_data.current_error
            if direction == DIRECTION_STOP:
                error = 0
            send_error_with_mode(arduino, error, direction)
        except Exception as e:
            print(f"Error in move_car_with_flush: {e}")