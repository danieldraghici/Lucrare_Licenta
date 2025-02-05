import gi
import os
import cv2
import hailo
import sys
import user_app_callback
sys.path.append(os.path.abspath("hailo-rpi5-examples/basic_pipelines"))
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst
from gi.repository import GstRtspServer
from hailo_apps_infra.hailo_rpi_common import get_numpy_from_buffer
from custom_streamer import CustomGStreamerDetectionApp

from utilities import (
    get_frame_info,
    serialProcessing,
    update_detection,track_object
)


def app_callback(pad, info, user_data):
    """
    Callback function for processing video frames in the GStreamer pipeline.

    This function is called for each frame passing through the GStreamer pipeline. It extracts
    the frame information, converts it to a NumPy array, processes the frame to filter or track objects,
    and updates the user data with the latest detection or tracking results.

    Args:
        pad (Gst.Pad): The GStreamer pad from which to extract frame information.
        info (Gst.PadProbeInfo): The probe info containing the buffer to be processed.
        user_data (UserAppCallbackClass): The instance of UserAppCallbackClass that stores detection
            and tracking information.

    Returns:
        Gst.PadProbeReturn: A Gst.PadProbeReturn value indicating the result of the probe.
    """
    # Get frame information such as buffer, format, width, and height from the pad and info
    frame_buffer, frame_format, frame_width, frame_height = get_frame_info(pad, info)

    # Check if any of the obtained frame information is None or invalid
    if not all([frame_buffer, frame_format, frame_width, frame_height]):
        # If any information is invalid, return OK to indicate no further processing
        return Gst.PadProbeReturn.OK

    # Convert buffer into NumPy array
    current_frame = get_numpy_from_buffer(
        frame_buffer, frame_format, frame_width, frame_height
    )
    current_gray = cv2.cvtColor(
        current_frame, cv2.COLOR_BGR2GRAY
    )  # Make frame grayscale
    roi = hailo.get_roi_from_buffer(
        frame_buffer
    )  # Get the region of interesr from buffer
    detections = roi.get_objects_typed(
        hailo.HAILO_DETECTION
    )  # Get the detected objects

    # If there are detections in the current frame, update the detection information in user_data
    if detections:
        update_detection(
            user_data, detections[0], current_gray, frame_width, frame_height
        )
    # If no detections are found but a previous ROI exists in user_data, track the object using
    # the previous ROI, current grayscale frame, and frame dimensions
    elif user_data.prev_roi is not None:
        track_object(user_data, current_gray, roi, frame_width, frame_height)
    # Enable serial processing
    serialProcessing(detections)
    return Gst.PadProbeReturn.OK

user_data = user_app_callback.user_app_callback()

if __name__ == "__main__":
    app = CustomGStreamerDetectionApp(app_callback, user_data)
    app.run()
