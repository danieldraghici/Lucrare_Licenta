import cv2

from hailo_apps_infra.hailo_rpi_common import app_callback_class

class user_app_callback(app_callback_class):
    def __init__(self):
        super().__init__()
        self.last_bbox = None
        self.prev_pts = None
        self.last_label = None
        self.prev_roi = None
        # Initialize ORB (Oriented FAST and Rotated BRIEF) detector
        self.orb = cv2.ORB_create()