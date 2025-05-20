import serial.tools.list_ports
import serial.tools.list_ports
import cv2
import serial
import threading
import threading
from hailo_apps_infra.hailo_rpi_common import app_callback_class
from constants import DIRECTION_FORWARD, DIRECTION_LEFT
import time
from pid import PIDController
from server import pipeline_server
class user_app_callback(app_callback_class):
    def __init__(self):
        super().__init__()
        self.arduino = None
        try:
            port = find_available_port()
            if port is not None:
                self.arduino = serial.Serial(port,baudrate=115200)
                if  not self.arduino.is_open: 
                    self.arduino.open()
                
        except serial.SerialException:
            raise serial.SerialException("No serial port found")
        self.movement_enabled = False
        self.line_present_prev = False
        self.command_frames = 0
        self.frame_format= None
        self.post_line_action = None
        self.action_start_time = 0 
        self.line_present_current=False
        self.control_state = 'stop'
        self.control_mode= 'auto'
        self.previous_movement_state = False
        self.lock = threading.Lock()
        self.is_calibrating=False
        self.frame_counter=0
        self.intersection_detected=False
        self.pending_direction = None
        self.intersection_count=0
        self.initial_forward_frames = pipeline_server.forward_frames
        self.forward_frames_=self.initial_forward_frames
        self.initial_direction_frames=pipeline_server.direction_frames
        self.stop_frames=pipeline_server.stop_frames
        self.direction_frames=self.initial_direction_frames
        self.detections = []
        self.processing_times = []
        self.angle_buffer = []
        self.left_speed=0
        self.right_speed=0
        self.found_direction=False
        self.sign_detected=False
        self.can_process_intersection=True
        self.debug1=False
        self.debug2=False
        self.pid = PIDController(Kp=pipeline_server.Kp, Ki=pipeline_server.Ki, Kd=pipeline_server.Kd, max_integral=pipeline_server.max_integral, output_limit=pipeline_server.output_limit)
        # self.is_moving_forward = False
    def update_control_state(self, state):
            self.control_state = state
            
    def get_control_state(self):
            return self.control_state


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
