from constants import (
    ACTION_PRIORITY,
    COMMAND_MAP,
)


def determine_arduino_commands(detections):
    commands = []
    for label in detections:
        if label in COMMAND_MAP:
            commands.append(COMMAND_MAP[label])
    return list(set(commands))


def determine_priority_action(detections):
    highest_priority = -1
    priority_action = None
    for label in detections:
        if label in ACTION_PRIORITY:
            if ACTION_PRIORITY[label] > highest_priority:
                highest_priority = ACTION_PRIORITY[label]
                priority_action = label
    return priority_action

def determine_action(detections):
    current_priority = -1
    action = None
    for label in detections:
        if label in ACTION_PRIORITY:
            if ACTION_PRIORITY[label] > current_priority:
                current_priority = ACTION_PRIORITY[label]
                action = label

    return action
