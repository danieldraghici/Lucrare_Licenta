import cv2
import numpy as np
from constants import (
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    DIRECTION_FORWARD,
    DIRECTION_STOP,
)


def detect_line(frame):
    display_frame = frame.copy()
    frame_height, frame_width = frame.shape[:2]

    # 1. Convert to HSV and threshold for black
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 50])
    mask = cv2.inRange(hsv, lower_black, upper_black)

    # 2. Morphological operations to clean the mask
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # 3. Find contours and process
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
    direction = DIRECTION_STOP  # Default direction

    if len(contours) > 0:
        # Select contour that's lowest in the image (closest to camera)
        def contour_priority(cnt):
            _, y, _, h = cv2.boundingRect(cnt)
            bottom_y = y + h  # Bottom edge of contour
            area = cv2.contourArea(cnt)
            return (bottom_y, area)  # Prioritize lower contours, then larger ones

        c = max(contours, key=contour_priority)
        _, y, _, h = cv2.boundingRect(c)
        bottom_y = y + h

        # Proximity thresholds (adjust these values based on your needs)
        PROXIMITY_THRESHOLD = (
            frame_height * 0.7
        )  # 70% from top (line must reach this Y position)
        MIN_CONTOUR_AREA = 500  # Minimum contour area to consider

        # Draw proximity line for visualization
        cv2.line(
            display_frame,
            (0, int(PROXIMITY_THRESHOLD)),
            (frame_width, int(PROXIMITY_THRESHOLD)),
            (0, 0, 255),
            2,
        )

        if cv2.contourArea(c) > MIN_CONTOUR_AREA and bottom_y > PROXIMITY_THRESHOLD:

            # Calculate centroid only if line is close enough
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                # Decision boundaries
                if cx > frame_width * 0.66:  # Right 33% of frame
                    direction = DIRECTION_LEFT
                elif cx > frame_width * 0.33:  # Middle 33%
                    direction = DIRECTION_FORWARD
                else:  # Left 33%
                    direction = DIRECTION_RIGHT

                # Draw centroid and contour
                cv2.circle(display_frame, (cx, cy), 5, (0, 255, 0), -1)
                cv2.drawContours(display_frame, [c], -1, (0, 255, 0), 2)

        else:
            # Line is too far or too small
            direction = DIRECTION_STOP
            cv2.putText(
                display_frame,
                "Line too far",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )

    # Apply mask visualization
    display_frame[mask != 0] = (255, 0, 0)
    return direction, mask, display_frame
