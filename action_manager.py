from constants import (
    ACTION_PRIORITY,
    COMMAND_MAP,
)


def determine_arduino_commands(detections):
    """Get all commands for detected objects in current frame"""
    commands = []
    for label in detections:
        if label in COMMAND_MAP:
            commands.append(COMMAND_MAP[label])
    return list(set(commands))


def determine_priority_action(detections):
    """Get highest priority action for vehicle control"""
    highest_priority = -1
    priority_action = None
    for label in detections:
        if label in ACTION_PRIORITY:
            if ACTION_PRIORITY[label] > highest_priority:
                highest_priority = ACTION_PRIORITY[label]
                priority_action = label
    return priority_action
import debugpy

def determine_action(detections):
    """Determine the highest priority action from detected signs/lights"""
    current_priority = -1
    action = None
    speed_limit = None
    for label in detections:
        if label in ACTION_PRIORITY:
            if ACTION_PRIORITY[label] > current_priority:
                current_priority = ACTION_PRIORITY[label]
                action = label
        elif label.isdigit():
            speed_limit = int(label)

    return action, speed_limit
