import cv2
from ultralytics import YOLO

CAMERA_URL = "http://rover-3.local/stream"

model = YOLO("yolov8n.pt")

cap = cv2.VideoCapture(CAMERA_URL)

if not cap.isOpened():
    print("❌ Could not open camera")
    exit()

print("✓ Camera connected")
print("Press Q to quit")

while True:
    success, frame = cap.read()

    if not success:
        print("❌ Failed to read frame")
        continue

    results = model(frame, conf=0.25)

    annotated = results[0].plot()

    cv2.imshow("Rover Camera + YOLO", annotated)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()