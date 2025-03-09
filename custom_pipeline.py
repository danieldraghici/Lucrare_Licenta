import os
import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
import sys

sys.path.append(os.path.abspath("hailo-rpi5-examples/basic_pipelines"))
import debugpy
import queue
import cv2
import numpy as np
import user_app_callback
import threading
from car_utilities import move_car
from image_processes import detect_line
from display_thread import DisplayThread
from gi.repository import Gst
from hailo_apps_infra.hailo_rpi_common import get_numpy_from_buffer
from custom_streamer import CustomGStreamerDetectionApp
from utilities import (
    get_frame_info,
)

STREAM_PORT = 5000
STREAM_WIDTH = 640
STREAM_HEIGHT = 480

# Create a thread-safe queue for display frames
display_queue = queue.Queue(maxsize=2)
exit_event = threading.Event()


# Modified app_callback
def app_callback(pad, info, user_data):
    frame_buffer, frame_format, frame_width, frame_height = get_frame_info(pad, info)

    if not all([frame_buffer, frame_format, frame_width, frame_height]):
        return Gst.PadProbeReturn.OK

    current_frame = get_numpy_from_buffer(
        frame_buffer, frame_format, frame_width, frame_height
    )
    match frame_format:
        case "RGB":
            current_frame = cv2.cvtColor(current_frame, cv2.COLOR_RGB2BGR)
        case "NV12":
            current_frame = cv2.cvtColor(current_frame, cv2.COLOR_YUV2BGR_NV12)

    direction, mask, display_frame = detect_line(current_frame)
    move_car(user_data.arduino, direction)

    if display_queue.empty():
        try:
            mask_display = (
                cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) if mask is not None else None
            )
            display_queue.put_nowait((display_frame, mask_display))
        except queue.Full:
            pass

    return Gst.PadProbeReturn.OK


if __name__ == "__main__":
    user_data = user_app_callback.user_app_callback()
    display_queue = queue.Queue(maxsize=2)
    exit_event = threading.Event()
    display_thread = DisplayThread(display_queue, exit_event, user_data)
    display_thread.start()
    try:
        app = CustomGStreamerDetectionApp(app_callback, user_data)
        app.run()
    finally:
        exit_event.set()
        display_thread.join()
        cv2.destroyAllWindows()
