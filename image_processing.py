import math
import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst
import cv2
import numpy as np
from constants import DIRECTION_LEFT, DIRECTION_RIGHT, DIRECTION_FORWARD, DIRECTION_STOP
from action_manager import determine_action
from constants import COMMAND_MAP
import debugpy
import traceback
from arduino_control import move_car_with_flush
from server import pipeline_server
from collections import Counter

def prepare_frame(current_frame, user_data):
    if current_frame.shape[2] != 3:
        if user_data.frame_format == "NV12":
            current_frame = cv2.cvtColor(current_frame, cv2.COLOR_YUV2BGR_NV12)
        elif user_data.frame_format == "RGB":
            current_frame = cv2.cvtColor(current_frame, cv2.COLOR_RGB2BGR)
    current_frame = cv2.rotate(current_frame, cv2.ROTATE_180)
    current_frame = cv2.GaussianBlur(current_frame, (5, 5), 0)
    sharpen_kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    current_frame = cv2.filter2D(current_frame, -1, sharpen_kernel)
    return current_frame

def calculate_error_for_pid(user_data, error):
    user_data.current_error = error
    
    abs_error = abs(error)
    direction = DIRECTION_FORWARD
    
    if abs_error > pipeline_server.movement_tolerance * 1.5:
        direction = DIRECTION_LEFT if error < 0 else DIRECTION_RIGHT
    
    return error, direction

def extract_blackline(user_data,current_frame):
    thresh=cv2.inRange(current_frame, (0, 0, 0), (pipeline_server.black_threshold, pipeline_server.black_threshold, pipeline_server.black_threshold))
    thresh = cv2.erode(thresh, np.ones((5, 5), np.uint8), iterations=pipeline_server.erode_count)
    thresh = cv2.dilate(thresh, np.ones((5, 5), np.uint8), iterations=pipeline_server.dilate_count)
    return thresh

def calculate_error(user_data,error):
    abs_error = abs(error)
    direction = DIRECTION_FORWARD
    
    if error < -pipeline_server.movement_tolerance:
        direction = DIRECTION_LEFT
    elif error > pipeline_server.movement_tolerance:
        direction = DIRECTION_RIGHT
    return 0, direction

def extract_intersection(c, current_frame, cx, cy):
    approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
    cv2.circle(current_frame, (cx, cy), 5, (255, 255, 0), -1)
    cv2.circle(current_frame, (cx, 450), 5, (0, 0, 0), -1)
    cv2.polylines(
        current_frame, [approx], isClosed=True, color=(0, 255, 255), thickness=2
    )
    cv2.putText(
        current_frame,
        "INTERSECTION",
        (cx - 50, cy - 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 0, 0),
        2,
    )
    return approx, current_frame


def extract_line_center(blackline, min_contour_area=1000):
    contours, _ = cv2.findContours(blackline, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_contour_area]
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    if c is None:
        return None
    M = cv2.moments(c)
    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return c, cx, cy


def extract_line_angle(c):
    data = np.array(c, dtype=np.float32).reshape(-1, 2)
    mean = np.empty((0))
    mean, eigenvectors, _ = cv2.PCACompute2(data, mean)
    angle = np.degrees(np.arctan2(eigenvectors[0, 1], eigenvectors[0, 0]))
    if angle > 90:
        angle -= 180
    return angle

def process_frame(current_frame, detections, user_data, mode=0,send_sign_callback=None):
    try:
        error = None
        dynamic_modifier = 0
        direction = DIRECTION_STOP
        arrow_color = (255, 0, 0)
        approx = None
        current_frame = prepare_frame(current_frame, user_data)
        blackline = extract_blackline(user_data,current_frame)
        if not hasattr(user_data, 'current_error'):
            user_data.current_error = 0
        if user_data.pending_direction:
            if user_data.forward_frames_ > 0:
                user_data.forward_frames_ -= 1
                print(f"Forward frames left: {user_data.forward_frames_}")
                user_data.current_error = 0
                return DIRECTION_FORWARD, current_frame, blackline, dynamic_modifier
            if user_data.direction_frames > 0:
                if user_data.stop_frames > 0:
                    print(f"Stop frames left: {user_data.stop_frames}")
                    user_data.stop_frames -= 1
                    return DIRECTION_STOP, current_frame, blackline, dynamic_modifier
                print(f"Direction frames left: {user_data.direction_frames}")
                user_data.direction_frames -= 1
                return user_data.pending_direction, current_frame, blackline, dynamic_modifier
            elif user_data.direction_frames == 0 or user_data.forward_frames_ % 2==0:
                line_info = extract_line_center(blackline)
                print(f"Moved enough frames in pending direction, aligning now....{error}",user_data.pending_direction)
                if line_info is None:
                    if user_data.pending_direction!=None:
                        print("Aligning with pending direction:", user_data.pending_direction)
                        direction=user_data.pending_direction
                        print("direction:",direction)
                    return direction, current_frame, blackline, dynamic_modifier
                c, cx, cy = line_info
                angle = extract_line_angle(c)
                print(cx,cy)
                error = cx - 320
                user_data.current_error = error
                dynamic_modifier, direction = calculate_error_for_pid(user_data, error)
                threshold=50
                if error is not None and error != 0:
                    print(f"error:{error}")
                    if abs(error) < threshold :
                        print("Aligned, clearing pending direction.")
                        user_data.pending_direction = None
                        user_data.can_process_intersection = False
                        user_data.intersection_detected = False
                        user_data.sign_detected = False
                        user_data.direction_frames = (
                            user_data.initial_direction_frames
                        )
                        user_data.current_error = 0
                        direction = DIRECTION_FORWARD
                elif user_data.pending_direction!=None:
                        print("Aligning with pending direction:", user_data.pending_direction)
                        direction=user_data.pending_direction
                        print("direction:",direction)
                return direction, current_frame, blackline, dynamic_modifier
            
        if blackline is None:
            return DIRECTION_STOP, current_frame, blackline, dynamic_modifier
        if mode == 1:
            line_info = extract_line_center(blackline)
            if line_info is None:
                return DIRECTION_STOP, current_frame, blackline, dynamic_modifier
            c, cx, cy = line_info
            approx, current_frame = extract_intersection(c, current_frame, cx, cy)
            return None, current_frame, blackline, None
        if blackline is None:
                return DIRECTION_STOP, current_frame, blackline, dynamic_modifier
        line_info = extract_line_center(blackline)
        if line_info is None:
            return DIRECTION_STOP, current_frame, blackline, dynamic_modifier
        c, cx, cy = line_info
        angle = extract_line_angle(c)
        cv2.circle(current_frame, (cx, cy), 5, (0, 255, 0), -1)
        error = cx - 320
        print(f"cx: {cx}, cy: {cy}, error: {error}")
        dynamic_modifier, direction = calculate_error_for_pid(user_data, error)
        approx, current_frame = extract_intersection(c, current_frame, cx, cy)
        if approx is not None and len(approx) >= 6:
            if user_data.intersection_count == 0:
                user_data.intersection_count += 1
                print("Intersection detected")
            user_data.can_process_intersection = True
        frame_height = current_frame.shape[0]
        lower_threshold = frame_height * pipeline_server.height_modifier
        valid_detections = []
        for det in detections:
            bbox = det.get_bbox()
            y_center = (bbox.ymin() + bbox.ymax()) / 2 * frame_height
            print(f"y_center: {y_center}, lower_threshold: {lower_threshold}")
            if y_center < lower_threshold:
                user_data.intersection_count += 1
                valid_detections.append(det.get_label())
        action = determine_action(valid_detections)
        if action:
            user_data.sign_detected = True
            print("Sign detected")
            if user_data.can_process_intersection and send_sign_callback:
                try:
                    send_sign_callback(action)
                    print(f"Sent sign detection to dashboard: {action}")
                except Exception as e:
                    print(f"Failed to send sign to dashboard: {e}")
            sign_direction = COMMAND_MAP[action]
            if sign_direction == DIRECTION_STOP:
                direction = DIRECTION_STOP
                user_data.pending_direction = None
            else:
                user_data.found_direction = sign_direction
        elif user_data.sign_detected:
            user_data.sign_detected = False
        if user_data.can_process_intersection and user_data.sign_detected:
            user_data.pending_direction = user_data.found_direction
            print(f"Intersection detected, moving in pending direction:{user_data.pending_direction}")
            user_data.forward_frames_ = (
                    pipeline_server.forward_frames
            )
            user_data.stop_frames = (
                pipeline_server.stop_frames
            )
            user_data.can_process_intersection = False
        if pipeline_server.show_debug:
            show_next_direction(current_frame, direction, arrow_color)

        return direction, current_frame, blackline, dynamic_modifier
    except Exception as e:
        print(f"Error processing frame: {e}")
        traceback.print_exc()
        user_data.current_error = 0
        return DIRECTION_STOP, current_frame, None, 0

def show_next_direction(current_frame, direction, arrow_color=(0, 255, 0)):
    height, width = current_frame.shape[:2]
    center = (width // 2, height // 2)
    arrow_thickness = 3
    if direction == DIRECTION_LEFT:
        cv2.arrowedLine(
            current_frame,
            center,
            (center[0] - 100, center[1]),
            arrow_color,
            arrow_thickness,
        )
        cv2.putText(
            current_frame,
            "LEFT",
            (center[0] - 120, center[1] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            arrow_color,
            2,
        )
    elif direction == DIRECTION_RIGHT:
        cv2.arrowedLine(
            current_frame,
            center,
            (center[0] + 100, center[1]),
            arrow_color,
            arrow_thickness,
        )
        cv2.putText(
            current_frame,
            "RIGHT",
            (center[0] + 20, center[1] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            arrow_color,
            2,
        )
    elif direction == DIRECTION_FORWARD:
        cv2.arrowedLine(
            current_frame,
            center,
            (center[0], center[1] - 100),
            arrow_color,
            arrow_thickness,
        )
        cv2.putText(
            current_frame,
            "FORWARD",
            (center[0] - 40, center[1] - 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            arrow_color,
            2,
        )
    else:
        cv2.putText(
            current_frame,
            "STOP",
            (center[0] - 40, center[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            arrow_color,
            2,
        )
