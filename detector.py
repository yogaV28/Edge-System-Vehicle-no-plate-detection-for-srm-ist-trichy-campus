from ultralytics import YOLO

class PlateDetector:
    def __init__(self, model_path):
        """
        model_path can be:
        - .pt  (PyTorch)
        - .engine (TensorRT)
        """
        self.model = YOLO(model_path)

    def detect(self, frame):
        results = self.model.predict(
            source=frame,
            device=0,          # ✅ REQUIRED for TensorRT
            conf=0.4,
            imgsz=640,
            verbose=False
        )

        boxes = []
        for r in results:
            if r.boxes is None:
                continue
            for b in r.boxes.xyxy:
                x1, y1, x2, y2 = map(int, b.tolist())
                boxes.append((x1, y1, x2, y2))

        return boxes
