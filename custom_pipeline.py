import gi
import os
import cv2
import hailo
import sys
import setproctitle
import serial
import numpy as np
sys.path.append(os.path.abspath("hailo-rpi5-examples/basic_pipelines"))
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst
from gi.repository import GstRtspServer
from hailo_rpi_common import app_callback_class
from detection_pipeline import GStreamerDetectionApp


from hailo_rpi_common import (
    get_default_parser,
    QUEUE,
    INFERENCE_PIPELINE,
    INFERENCE_PIPELINE_WRAPPER,
    USER_CALLBACK_PIPELINE,
    DISPLAY_PIPELINE,
    GStreamerApp,
    get_caps_from_pad,
    app_callback_class,
    dummy_callback,
    display_user_data_frame,
    get_numpy_from_buffer, 
    disable_qos,
    detect_hailo_arch,
)

def SOURCE_PIPELINE(video_format='RGB', video_width=640, video_height=640, name='source'):
    source_element = (
        f'libcamerasrc name={name} ! '
        f'video/x-raw, format=NV12, width={video_width}, height={video_height} ! '
    )
    source_pipeline = (
        f'{source_element} '
        f'{QUEUE(name=f"{name}_scale_q")} ! '
        f'videoscale name={name}_videoscale n-threads=2 ! '
        f'videoflip video-direction=180 ! '
        f'{QUEUE(name=f"{name}_convert_q")} ! '
        f'videoconvert n-threads=3 name={name}_convert qos=false ! '
        f'video/x-raw, format={video_format}, pixel-aspect-ratio=1/1 ! '
    )

    return source_pipeline
    
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


class CustomGStreamerDetectionApp(GStreamerApp):
    def __init__(self, app_callback, user_data):
        parser = get_default_parser()
        parser.add_argument(
            "--labels-json",
            default=None,
            help="Path to costume labels JSON file",
        )
        parser.add_argument(
            "--headless",
            action="store_true",
            help="Run the application in headless mode (no display).")
        args = parser.parse_args()
        # Call the parent class constructor
        super().__init__(args, user_data)
        # Additional initialization code can be added here
        # Set Hailo parameters these parameters should be set based on the model used
        self.batch_size = 2
        self.network_width = 640
        self.network_height = 640
        self.network_format = "RGB"
        nms_score_threshold = 0.3
        nms_iou_threshold = 0.45
        # Determine the architecture if not specified
        if args.arch is None:
            detected_arch = detect_hailo_arch()
            if detected_arch is None:
                raise ValueError("Could not auto-detect Hailo architecture. Please specify --arch manually.")
            self.arch = detected_arch
            print(f"Auto-detected Hailo architecture: {self.arch}")
        else:
            self.arch = args.arch

        if args.hef_path is not None:
            self.hef_path = args.hef_path
        # Set the HEF file path based on the arch
        elif self.arch == "hailo8":
            self.hef_path = os.path.join(self.current_path, '../resources/yolov8m.hef')
        else:  # hailo8l
            self.hef_path = os.path.join(self.current_path, '../resources/yolov8s_h8l.hef')

        # Set the post-processing shared object file
        self.post_process_so = os.path.join(self.current_path, '../resources/libyolo_hailortpp_postprocess.so')

        # User-defined label JSON file
        self.labels_json = args.labels_json

        self.app_callback = app_callback

        self.thresholds_str = (
            f"nms-score-threshold={nms_score_threshold} "
            f"nms-iou-threshold={nms_iou_threshold} "
            f"output-format-type=HAILO_FORMAT_TYPE_FLOAT32"
        )

        # Set the process title
        setproctitle.setproctitle("Hailo Detection App")
        self.headless = args.headless
        if self.headless:
            self.video_sink = "fakesink"
        else:
            self.video_sink = "autovideosink"
        self.options_menu.show_fps = not self.headless
        self.create_pipeline()

    def get_pipeline_string(self):
        source_pipeline = SOURCE_PIPELINE()
        detection_pipeline = INFERENCE_PIPELINE(
            hef_path=self.hef_path,
            post_process_so=self.post_process_so,
            batch_size=self.batch_size,
            config_json=self.labels_json,
            additional_params=self.thresholds_str)
        user_callback_pipeline = USER_CALLBACK_PIPELINE()
        display_pipeline = DISPLAY_PIPELINE(video_sink=self.video_sink, sync=self.sync, show_fps=self.show_fps)
        pipeline_string = (
            f'{source_pipeline} '
            f'{detection_pipeline} ! '
            f'{user_callback_pipeline} ! '
            f'{display_pipeline}'
        )
        return pipeline_string


class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.last_bbox = None
        self.prev_pts = None
        self.last_label = None
        self.prev_roi = None
        # Initialize ORB (Oriented FAST and Rotated BRIEF) detector
        self.orb = cv2.ORB_create()

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
        bbox=tracking_bbox, label=f"tracking {user_data.last_label}", confidence=0.75
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

user_data = user_app_callback_class()

if __name__ == "__main__":
    app = CustomGStreamerDetectionApp(app_callback, user_data)
    app.run()
