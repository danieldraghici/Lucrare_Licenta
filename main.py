import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
import cv2
from gi.repository import Gst
from statistics import mean
from og_streamer import CustomGStreamerDetectionApp
from constants import DIRECTION_STOP
import user_app_callback
import debugpy
from server import pipeline_server
from arduino_control import move_car_with_flush, set_pid_parameters
from image_processing import process_frame
from constants import MANUAL_MODE
import hailo
from utilities import get_frame_info
from hailo_apps_infra.hailo_rpi_common import get_numpy_from_buffer
import time
import socketio
sign_sio = socketio.Client()

@sign_sio.event
def connect():
    print("Sign detection SocketIO client connected")

@sign_sio.event
def disconnect():
    print("Sign detection SocketIO client disconnected")

def send_sign_detection(sign_name):
    """Send sign detection via SocketIO"""
    try:
        if sign_sio.connected:
            sign_sio.emit('sign_detected', {'sign': sign_name})
            print(f"Sent sign detection via SocketIO: {sign_name}")
        else:
            print("SocketIO client not connected, attempting to connect...")
            sign_sio.connect('http://localhost:5000')
            if sign_sio.connected:
                sign_sio.emit('sign_detected', {'sign': sign_name})
                print(f"Sent sign detection via SocketIO after reconnect: {sign_name}")
    except Exception as e:
        print(f"Failed to send sign detection via SocketIO: {e}")
def app_callback(pad, info,user_data):
    user_data.frame_counter += 1
    current_pid = (pipeline_server.Kp, pipeline_server.Ki, pipeline_server.Kd)
    if not hasattr(user_data, 'last_pid_params') or user_data.last_pid_params != current_pid:
        print(f"Updating Arduino PID: Kp={pipeline_server.Kp}, Ki={pipeline_server.Ki}, Kd={pipeline_server.Kd}")
        set_pid_parameters(user_data.arduino, pipeline_server.Kp, pipeline_server.Ki, pipeline_server.Kd)
        user_data.last_pid_params = current_pid
    
    user_data.pid.set_parameters(Kp=pipeline_server.Kp, Ki=pipeline_server.Ki, Kd=pipeline_server.Kd)
    frame_buffer, frame_format, frame_width, frame_height = get_frame_info(pad, info)
    if not all([frame_buffer, frame_format, frame_width, frame_height]):
        return Gst.PadProbeReturn.OK
    current_frame = get_numpy_from_buffer(frame_buffer, frame_format, frame_width, frame_height)
    roi = hailo.get_roi_from_buffer(frame_buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    with user_data.lock:
        user_data.detections = detections
    
    if pipeline_server.get_control_state() == "stop" or not hasattr(current_frame, 'shape'):
        return Gst.PadProbeReturn.OK
    elif pipeline_server.get_control_state() == "start" and pipeline_server.get_control_mode() == MANUAL_MODE:
        move_car_with_flush(user_data.arduino,user_data,
                            pipeline_server.manual_direction,
                            pipeline_server.manual_speed)
        return Gst.PadProbeReturn.OK
    if not pipeline_server.allow_auto_movement:
        if user_data.previous_movement_state:
            print("Stopping car")
            move_car_with_flush(user_data.arduino,user_data, DIRECTION_STOP, 0)
            user_data.previous_movement_state=False
        return Gst.PadProbeReturn.OK
    speed=pipeline_server.car_speed
    user_data.previous_movement_state=True
    try:
        direction, current_frame, _, _ = process_frame(current_frame, detections, user_data,send_sign_callback=send_sign_detection)
        if direction != user_data.last_direction:
            print(f"detected direction change: {direction}")
            move_car_with_flush(user_data.arduino,user_data, direction, speed if direction != DIRECTION_STOP else 0)
            user_data.last_direction = direction
            user_data.same_dir_count = 0
        else:
            user_data.same_dir_count += 1
            print(f"same direction count: {direction}")
            if user_data.same_dir_count > pipeline_server.move_frequency and direction != DIRECTION_STOP:
                move_car_with_flush(user_data.arduino,user_data, direction, speed)
                user_data.same_dir_count = 0
    except Exception as e:
        print(f"Error processing frame: {e}")
        move_car_with_flush(user_data.arduino,user_data, DIRECTION_STOP, 0)
        direction = DIRECTION_STOP
    return Gst.PadProbeReturn.OK
if __name__ == "__main__":
    pipeline_server.start()
    user_data = user_app_callback.user_app_callback()
    try:
        sign_sio.connect('http://localhost:5000')
        print("Sign detection SocketIO client connected successfully")
    except Exception as e:
        print(f"Failed to connect sign detection SocketIO client: {e}")
    try:
        app_instance = CustomGStreamerDetectionApp(app_callback, user_data)
        time.sleep(1)
        app_instance.run()
    finally:
        cv2.destroyAllWindows()