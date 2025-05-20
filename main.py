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
from arduino_control import move_car_with_flush
from image_processing import process_frame
from constants import MANUAL_MODE
import hailo
from utilities import get_frame_info
from hailo_apps_infra.hailo_rpi_common import get_numpy_from_buffer
import time

def app_callback(pad, info,user_data):
    user_data.frame_counter += 1
    user_data.pid.set_parameters(Kp=pipeline_server.Kp, Ki=pipeline_server.Ki, Kd=pipeline_server.Kd)
    user_data.pid.set_output_limit(pipeline_server.output_limit)
    user_data.pid.set_max_integral(pipeline_server.max_integral)
    frame_buffer, frame_format, frame_width, frame_height = get_frame_info(pad, info)
    if not all([frame_buffer, frame_format, frame_width, frame_height]):
        return Gst.PadProbeReturn.OK
    current_frame = get_numpy_from_buffer(frame_buffer, frame_format, frame_width, frame_height)
    roi = hailo.get_roi_from_buffer(frame_buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    if pipeline_server.get_control_state() == "stop" or not hasattr(current_frame, 'shape'):
        return Gst.PadProbeReturn.OK
    elif pipeline_server.get_control_state() == "start" and pipeline_server.get_control_mode() == MANUAL_MODE:
        move_car_with_flush(user_data.arduino,
                            pipeline_server.manual_direction,
                            pipeline_server.manual_speed)
        return Gst.PadProbeReturn.OK
    if not pipeline_server.allow_auto_movement:
        if user_data.previous_movement_state:
            print("Stopping car")
            move_car_with_flush(user_data.arduino,user_data, DIRECTION_STOP, 0)
            user_data.previous_movement_state=False
        return Gst.PadProbeReturn.OK
    # st=time.time()
    # cv2.imwrite(f"frames/frame_{user_data.frame_counter}.jpg", current_frame)
    speed=pipeline_server.car_speed
    user_data.previous_movement_state=True
    dynamic_modifier=0
    try:
        # st1=time.time()
        direction, current_frame, _, dynamic_modifier = process_frame(current_frame, detections, user_data)
        # print(F"Frame{user_data.frame_counter} img processing time:", time.time()-st1)
    except Exception as e:
        print(f"Error processing frame: {e}")
        move_car_with_flush(user_data.arduino,user_data, DIRECTION_STOP, 0)
        direction = DIRECTION_STOP
    # st2=time.time()
    move_car_with_flush(user_data.arduino, user_data, direction, speed, 
                        modifier=dynamic_modifier, 
                        max_speed=pipeline_server.max_speed, 
                        min_speed=pipeline_server.min_speed)
    # print(f"Processing movement for frame{user_data.frame_counter} time:", time.time()-st2)
    # print(f"Frame_{user_data.frame_counter}'s total frame time",time.time()-st)
    with user_data.lock:
        user_data.detections=detections
    return Gst.PadProbeReturn.OK
if __name__ == "__main__":
    pipeline_server.start()
    user_data = user_app_callback.user_app_callback()
    try:
        app_instance = CustomGStreamerDetectionApp(app_callback, user_data)
        time.sleep(1)
        app_instance.run()
    finally:
        cv2.destroyAllWindows()