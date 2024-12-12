import cv2
import time
from ultralytics import YOLO
from adafruit_motorkit import MotorKit

model = YOLO('yolov8n.pt')

kit = MotorKit()

def control_motor(detections):
    if detections:
        print("Object detected! Motor start.")
        kit.motor1.throttle = 0.5
    else:
        print("No object detected! Motor stop.")
        kit.motor1.throttle = 0

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Eroare: Camera can't open")
    exit()

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Can't read frame.")
            break

        results = model(frame)

        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = box.conf[0].cpu().numpy()
                cls = int(box.cls[0].cpu().numpy())

                if conf > 0.5:
                    detections.append((x1, y1, x2, y2, cls))

        for (x1, y1, x2, y2, cls) in detections:
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(frame, str(cls), (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        control_motor(detections)

        cv2.imshow("Object detection", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        time.sleep(0.1)

except KeyboardInterrupt:
    print("Program stopped.")
finally:
    cap.release()
    cv2.destroyAllWindows()
    kit.motor1.throttle = 0
    print("Resources freed.")
