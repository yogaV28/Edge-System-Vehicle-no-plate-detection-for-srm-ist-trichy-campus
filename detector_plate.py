from ultralytics import YOLO

class PlateDetector:
    def __init__(self, engine_path):
        self.model = YOLO(engine_path, task="detect")

    def detect(self, frame):
        results = self.model(
            frame,
            conf=0.4,
            imgsz=640,
            verbose=False
        )[0]

        plates = []
        if results.boxes is None:
            return plates

        for box in results.boxes.xyxy:
            plates.append(tuple(map(int, box.tolist())))

        return plates
