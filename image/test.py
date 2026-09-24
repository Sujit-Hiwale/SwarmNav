import cv2
import time

ESP32_IP = "192.168.1.100"   # change this
STREAM_URL = f"http://172.17.232.153:80/stream"

cap = cv2.VideoCapture(STREAM_URL)

cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap.isOpened():
    print("Could not connect to ESP32-CAM")
    exit()

frame_count = 0
start_time = time.time()
fps = 0.0

while True:
    ret, frame = cap.read()

    if not ret:
        print("Frame read failed")
        time.sleep(0.1)
        continue

    # -----------------------------
    # Image processing goes here
    # -----------------------------

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Example processing
    processed = cv2.GaussianBlur(gray, (5, 5), 0)

    # Convert back to BGR for display
    processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)

    # FPS calculation
    frame_count += 1
    elapsed = time.time() - start_time

    if elapsed >= 1:
        fps = frame_count / elapsed
        frame_count = 0
        start_time = time.time()

    cv2.putText(
        processed,
        f"FPS: {fps:.1f}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.imshow("ESP32-CAM Processing", processed)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()