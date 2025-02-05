import serial
import hailo
import numpy as np
import cv2
from hailo_apps_infra.hailo_rpi_common import get_caps_from_pad

def serialProcessing(detections):
    try:
        arduino = serial.Serial(port='/dev/ttyUSB0', baudrate=9600, timeout=0.1)
        if detections:
            arduino.write(b'R')
            print("Object detected \n")
    except FileNotFoundError:
        print("Port not found\n")
    except Exception as e:
        print(f"Port error: {e}")

def update_detection(user_data, detection, frame, frame_width, frame_height):
    """
    Update the detection information in the user data.

    This function updates the user data with the latest detection bounding box,
    label, region of interest (ROI) from the current frame, and keypoints detected
    in the ROI using the ORB detector.

    Args:
        user_data (UserAppCallbackClass): An instance of the UserAppCallbackClass
                                             where the detection information will be stored.
        detection (Detection): The detection object containing bounding box and label information.
        frame (numpy.ndarray): The current frame from which the ROI will be extracted.
        frame_width (int): The width of the frame.
        frame_height (int): The height of the frame.
    """
    user_data.last_bbox = detection.get_bbox()  # Get bounding box of the detection
    user_data.last_label = detection.get_label()  # Get label of the detection
    x, y, w, h = get_bbox_coords(user_data.last_bbox, frame_width, frame_height)
    user_data.prev_roi = frame[y : y + h, x : x + w]

    # Detect keypoints in the ROI using ORB
    kp = user_data.orb.detect(user_data.prev_roi, None)
    # Convert the list of 2D points (x, y) into a 3D numpy array with shape (n, 1, 2),
    # where n is the number of keypoints. This format is required by OpenCV's optical flow functions.
    user_data.prev_pts = np.float32([kp[i].pt for i in range(len(kp))]).reshape(
        -1, 1, 2
    )


def track_object(user_data, frame, roi, frame_width, frame_height):
    """
    Track the detected object using optical flow.

    This function tracks the previously detected object in the current frame
    by calculating the optical flow between the previous region of interest (ROI)
    and the current ROI.

    Args:
        user_data (UserAppCallbackClass): An instance of the UserAppCallbackClass
                                             containing the previous frame's ROI and keypoints.
        frame (numpy.ndarray): The current frame from which the ROI will be extracted.
        roi (hailo.HailoROI): The region of interest object where the tracking information
                              will be added.
        frame_width (int): The width of the frame.
        frame_height (int): The height of the frame.
    """
    if user_data.prev_pts is None or len(user_data.prev_pts) == 0:
        return

    x, y, w, h = get_bbox_coords(user_data.last_bbox, frame_width, frame_height)
    roi_curr = frame[y : y + h, x : x + w]

    # Calculate optical flow between previous and current ROI
    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(
        user_data.prev_roi, roi_curr, user_data.prev_pts, None
    )
    good_new = curr_pts[status == 1]  # Select points with successful status
    if len(good_new) == 0:
        return  # If no good points, exit

    # Convert local coordinates to global coordinates
    global_pts = np.array([(pt[0] + x, pt[1] + y) for pt in good_new])

    x_min, y_min = np.min(global_pts, axis=0)  # Find minimum coordinates
    x_max, y_max = np.max(global_pts, axis=0)  # Find maximum coordinates

    tracking_bbox = hailo.HailoBBox(
        x_min / frame_width,
        y_min / frame_height,
        (x_max - x_min) / frame_width,
        (y_max - y_min) / frame_height,
    )
    # Drawing bbox with HailoDetection using calculated bbox for tracking
    tracking = hailo.HailoDetection(
        bbox=tracking_bbox, label=f"tracking {user_data.last_label}", confidence=0.85
    )
    roi.add_object(tracking)  # Add tracking object to ROI

    user_data.prev_pts = good_new.reshape(-1, 1, 2)  # Update previous points
    user_data.prev_roi = roi_curr


def get_frame_info(pad, info):
    """
    Extract frame information from the GStreamer pad and buffer.

    Args:
        pad (Gst.Pad): The GStreamer pad from which to extract frame information.
        info (Gst.PadProbeInfo): The probe info containing the buffer to be processed.

    Returns:
        tuple: A tuple containing the following elements:
            - frame_buffer (Gst.Buffer): The buffer containing the frame data, or None if no buffer is available.
            - frame_format (str): The format of the frame, or None if no buffer is available.
            - frame_width (int): The width of the frame, or None if no buffer is available.
            - frame_height (int): The height of the frame, or None if no buffer is available.
    """
    frame_buffer = info.get_buffer()
    frame_format, frame_width, frame_height = (
        get_caps_from_pad(pad) if frame_buffer else (None, None, None)
    )
    return frame_buffer, frame_format, frame_width, frame_height


def get_bbox_coords(bbox, width, height):
    """
    Calculate the coordinates of a bounding box in pixel values.

    Args:
        bbox (hailo.HailoBBox): The bounding box object containing normalized coordinates.
        width (int): The width of the image/frame in pixels.
        height (int): The height of the image/frame in pixels.

    Returns:
        list: A list of integers representing the bounding box coordinates
        in the order [x, y, width, height], where (x, y) is the top-left
        corner of the bounding box.
    """
    return [
        int(v)
        for v in (
            bbox.xmin() * width,
            bbox.ymin() * height,
            bbox.width() * width,
            bbox.height() * height,
        )
    ]