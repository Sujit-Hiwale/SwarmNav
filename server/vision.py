from ultralytics import YOLO


class Vision:

    def __init__(
        self,
        model_path="yolov8n.pt",
        confidence=0.5,
    ):

        self.model = YOLO(
            model_path
        )

        self.confidence = confidence


    def process(
        self,
        frame,
    ):

        results = self.model(
            frame,
            conf=self.confidence,
            verbose=False,
        )

        detections = []

        for result in results:

            if result.boxes is None:
                continue

            for box in result.boxes:

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist()
                )

                confidence = float(
                    box.conf[0]
                )

                class_id = int(
                    box.cls[0]
                )

                class_name = (
                    self.model.names[
                        class_id
                    ]
                )

                crop = frame[
                    max(0, y1):min(
                        frame.shape[0],
                        y2
                    ),
                    max(0, x1):min(
                        frame.shape[1],
                        x2
                    ),
                ]

                detections.append({

                    "class":
                        class_name,

                    "confidence":
                        confidence,

                    "bbox":
                        (x1, y1, x2, y2),

                    "center":
                        (
                            (x1 + x2) // 2,
                            (y1 + y2) // 2,
                        ),

                    "image":
                        crop,
                })

        return detections