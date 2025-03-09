import serial.tools.list_ports
import cv2
import serial
import threading
from hailo_apps_infra.hailo_rpi_common import app_callback_class


class user_app_callback(app_callback_class):
    def __init__(self):
        super().__init__()
        self.arduino = None
        try:
            port = find_available_port()
            if port is not None:
                self.arduino = serial.Serial(port)
                if  not self.arduino.is_open: 
                    self.arduino.open()
                
        except serial.SerialException:
            raise serial.SerialException("No serial port found")
        
        self.fps_lock = threading.Lock()
        self.ema_fps = 30.0  # Initial value for display FPS
        self.last_bbox = None
        self.prev_pts = None
        self.last_label = None
        self.prev_roi = None
        self.orb = cv2.ORB_create()


def find_available_port():
    ports = serial.tools.list_ports.comports()
    ports_list = []
    for port in ports:
        ports_list.append(str(port))
    for i in range(len(ports_list)):
        if "USB" in ports_list[i]:
            port = ports_list[0].split(" ")[0]
            return port
    return None
