import cv2
from pathlib import Path
from ultralytics import YOLO

IMAGE_PATH = Path("data/vision/images/robot_3_0_3_NORTH.jpg")
MODEL_PATH = "yolov8n.pt"

CONFIDENCE = 0.10

OUTPUT_DIR = Path("runs/vision")
OUTPUT_PATH = OUTPUT_DIR / f"{IMAGE_PATH.stem}_enhanced_yolo11.jpg"


def enhance_image(image):
    # Mild denoising
    denoised = cv2.fastNlMeansDenoisingColored(
        image,
        None,
        3,
        3,
        7,
        21
    )

    # Improve local contrast
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(
        clipLimit=1.5,
        tileGridSize=(8, 8)
    )

    l = clahe.apply(l)

    enhanced = cv2.merge((l, a, b))
    enhanced = cv2.cvtColor(
        enhanced,
        cv2.COLOR_LAB2BGR
    )

    # Very mild sharpening
    blurred = cv2.GaussianBlur(
        enhanced,
        (0, 0),
        1
    )

    enhanced = cv2.addWeighted(
        enhanced,
        1.15,
        blurred,
        -0.15,
        0
    )

    return enhanced

def main():
    print("Loading YOLO11n...")
    model = YOLO(MODEL_PATH)

    image = cv2.imread(str(IMAGE_PATH))

    if image is None:
        print("❌ Failed to load image")
        return

    print(f"Original: {image.shape[1]}x{image.shape[0]}")

    # Improve image
    enhanced = enhance_image(image)

    print(
        f"Enhanced: "
        f"{enhanced.shape[1]}x{enhanced.shape[0]}"
    )

    # YOLO11
    print("Running YOLO11n...")

    results = model.predict(
        source=enhanced,
        conf=CONFIDENCE,
        imgsz=640,
        verbose=False
    )

    result = results[0]

    print("\nDetected objects:")

    if result.boxes is None or len(result.boxes) == 0:
        print("No objects detected.")
    else:
        for i, box in enumerate(result.boxes, 1):

            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            name = model.names[class_id]

            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0].tolist()
            )

            print(
                f"{i}. {name} "
                f"| Confidence: {confidence:.2%} "
                f"| Box: ({x1}, {y1}, {x2}, {y2})"
            )

    # Draw boxes
    annotated = result.plot()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    cv2.imwrite(
        str(OUTPUT_PATH),
        annotated
    )

    print(
        f"\n✓ Saved: {OUTPUT_PATH}"
    )

    cv2.imshow(
        "Enhanced Image + YOLO11n",
        annotated
    )

    print("Press any key to exit.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()