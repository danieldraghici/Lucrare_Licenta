from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
from constants import AUTO_MODE,MANUAL_MODE, DIRECTION_STOP
from flask_socketio import SocketIO, emit
import debugpy
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)
AUTO_MODE, MANUAL_MODE = "auto", "manual"

class PipelineServer:
    def __init__(self):
        self.control_state = "stop"
        self.messages = []
        self.server_thread = None
        self.control_mode = AUTO_MODE
        self.show_debug = False
        self.manual_direction = DIRECTION_STOP
        self.manual_speed = 0
        self.brightness = 0
        self.contrast = 1.0
        self.allow_auto_movement = True
        self.movement_tolerance = 50
        self.car_speed = 150
        self.forward_frames = 15
        self.direction_frames = 25
        self.stop_frames = 25
        self.height_modifier=0.3
        self.black_threshold=100
        self.erode_count=2
        self.dilate_count=3
        self.Kp = 0.6
        self.Ki = 0.02
        self.Kd = 0.15
        self.move_frequency = 5
        self._update_auto_calculated_values()

    def _update_auto_calculated_values(self):
        self.output_limit = max(20, int(self.car_speed * 0.3))
        if self.Ki > 0:
            self.max_integral = max(50, int(self.output_limit / self.Ki))
        else:
            self.max_integral = 100
        
        print(f"Auto-calculated PID limits - Output Limit: {self.output_limit}, Max Integral: {self.max_integral}")
    def start(self):
        self.server_thread = threading.Thread(
            target=lambda: socketio.run(app,host='0.0.0.0', port=5000,allow_unsafe_werkzeug=True),
            daemon=True
        )
        self.server_thread.start()
    def set_movement_tolerance(self, value: int):
        self.movement_tolerance = max(0, min(int(value), 1000))
    def set_car_speed(self, value: int):
        self.car_speed = max(0, min(int(value), 255))
        self._update_auto_calculated_values()
    def set_allow_auto_movement(self, enabled: bool):
        self.allow_auto_movement = enabled
    def set_brightness(self, value: float):
        self.brightness = value
    def set_contrast(self, value: float):
        self.contrast = max(0.0, min(float(value), 3.0))
    def set_show_debug(self, value: bool):
        self.show_debug = value
    def get_control_state(self):
            return self.control_state  
    def get_control_mode(self):
        return self.control_mode
    def set_control_mode(self, mode):
        self.control_mode = mode
    def set_manual_state(self, direction, speed):
        self.control_mode = MANUAL_MODE
        self.manual_direction = direction
        self.manual_speed = speed

    def set_control_state(self, state):
        self.control_state = state

    def add_message(self, message):
        self.messages.append(message)

    def get_messages(self):
        return self.messages[-1] if self.messages else None
    def set_forward_frames(self, value: int):
        self.forward_frames = max(0, min(int(value), 500))
    def set_direction_frames(self, value: int):
        self.direction_frames = max(0, min(int(value), 500))
    def set_stop_frames(self, value: int):
        self.stop_frames = max(0, min(int(value), 500))
    def set_height_modifier(self, value: float):
        self.height_modifier = max(0.0, min(float(value), 1.0))
    def set_black_threshold(self, value: int):
        self.black_threshold = max(0, min(int(value), 500))
    def set_erode_count(self, value: int):
        self.erode_count = max(0, min(int(value), 500))
    def set_dilate_count(self, value: int):
        self.dilate_count = max(0, min(int(value), 500))
    def set_move_frequency(self, value: int):
        self.move_frequency = max(0, min(int(value), 100))
    def set_kp_modifier(self, value: float):
        self.Kp = max(0.0, min(float(value), 10.0))
        self._update_auto_calculated_values()
    def set_ki_modifier(self, value: float):
        self.Ki = max(0.0, min(float(value), 10.0))
        self._update_auto_calculated_values()
    def set_kd_modifier(self, value: float):
        self.Kd = max(0.0, min(float(value), 10.0))
        self._update_auto_calculated_values()

@socketio.on('connect')
def handle_connect():
    print("Client connected")
@socketio.on('sign_detected')
def handle_sign_detection(data):
    sign_name = data.get('sign', '')
    if sign_name:
        print(f"Broadcasting sign detection: {sign_name}")
        emit('sign_detected', {'sign': sign_name}, broadcast=True)
@socketio.on('set_auto_movement')
def handle_set_auto_movement(data):
    enabled = data.get('enabled', True)
    pipeline_server.set_allow_auto_movement(enabled)
    emit('auto_movement_ack', {'enabled': enabled}, broadcast=False)
@socketio.on('set_mode')
def handle_set_mode(data):
    mode = data.get('mode', 'auto')
    pipeline_server.set_control_mode(mode)
    emit('mode_ack', {'mode': mode}, broadcast=False)
@socketio.on('toggle_debug')
def handle_toggle_debug(data):
    enabled = data.get('enabled', False)
    pipeline_server.set_show_debug(enabled)
    emit('debug_ack', {'enabled': enabled}, broadcast=False)
@socketio.on('control_cmd')
def handle_control_cmd(data):
    state = data.get('state')
    pipeline_server.set_control_state(state)
    emit('control_ack', {'state': state}, broadcast=False)
    
@socketio.on('detection_msg')
def handle_detection(data):
    emit('detection', {'msg': data['msg']}, broadcast=True)

@socketio.on('set_mode')
def handle_set_mode(data):
    mode = data.get('mode', 'auto')
    print(f"Setting mode to {mode}")
    pipeline_server.set_control_mode(mode)
    emit('mode_ack', {'mode': mode})

@socketio.on('manual_cmd')
def handle_manual_cmd(data):
    if pipeline_server.allow_auto_movement:
        pipeline_server.set_manual_state(data['direction'], data['speed'])
    else:
        print("Movement disabled - ignoring manual command")
    
@socketio.on('set_brightness')
def handle_set_brightness(data):
    value = data.get('value', 0)
    pipeline_server.set_brightness(value)
    emit('brightness_ack', {'value': value}, broadcast=False)
@socketio.on('set_tolerance')
def handle_set_tolerance(data):
    value = data.get('value', 50)
    pipeline_server.set_movement_tolerance(value)
    emit('tolerance_ack', {'value': value}, broadcast=False)

@socketio.on('set_speed')
def handle_set_speed(data):
    value = data.get('value', 150)
    pipeline_server.set_car_speed(value)
    emit('speed_ack', {'value': value}, broadcast=False)
@socketio.on('set_contrast')
def handle_set_contrast(data):
    value = data.get('value', 1.0)
    pipeline_server.set_contrast(value)
    emit('contrast_ack', {'value': value}, broadcast=False)
@socketio.on('set_forward_frames')
def handle_set_forward_frames(data):
    value = data.get('value', 15)
    pipeline_server.set_forward_frames(value)
    emit('forward_frames_ack', {'value': value}, broadcast=False)
@socketio.on('set_direction_frames')
def handle_set_direction_frames(data):
    value = data.get('value', 15)
    pipeline_server.set_direction_frames(value)
    emit('direction_frames_ack', {'value': value}, broadcast=False)
@socketio.on('set_stop_frames')
def handle_set_stop_frames(data):
    value = data.get('value', 15)
    pipeline_server.set_stop_frames(value)
    emit('direction_stop_ack', {'value': value}, broadcast=False)
@socketio.on('set_height_modifier')
def handle_set_height_modifier(data):
    value = data.get('value', 0.3)
    pipeline_server.set_height_modifier(value)
    emit('height_modifier_ack', {'value': value}, broadcast=False)
@socketio.on('set_black_threshold')
def handle_set_black_threshold(data):
    value = data.get('value', 15)
    pipeline_server.set_black_threshold(value)
    emit('black_threshold_ack', {'value': value}, broadcast=False)
@socketio.on('set_erode_count')
def handle_set_erode_count(data):
    value = data.get('value', 2)
    pipeline_server.set_erode_count(value)
    emit('erode_count_ack', {'value': value}, broadcast=False)
@socketio.on('set_dilate_count')
def handle_set_dilate_count(data):
    value = data.get('value', 3)
    pipeline_server.set_dilate_count(value)
    emit('dilate_count_ack', {'value': value}, broadcast=False)
@socketio.on('set_move_frequency')
def handle_set_move_frequency(data):
    value = data.get('value', 5)
    pipeline_server.set_move_frequency(value)
    emit('move_frequency_ack', {'value': value}, broadcast=False)
@socketio.on('set_kp_modifier')
def handle_set_kp_modifier(data):
    value = data.get('value', 0.6)
    pipeline_server.set_kp_modifier(value)
    emit('kp_modifier_ack', {'value': value}, broadcast=False)
@socketio.on('set_ki_modifier')
def handle_set_ki_modifier(data):
    value = data.get('value', 0.02)
    pipeline_server.set_ki_modifier(value)
    emit('ki_modifier_ack', {'value': value}, broadcast=False)
@socketio.on('set_kd_modifier')
def handle_set_kd_modifier(data):
    value = data.get('value', 0.15)
    pipeline_server.set_kd_modifier(value)
    emit('kd_modifier_ack', {'value': value}, broadcast=False)
pipeline_server = PipelineServer()
