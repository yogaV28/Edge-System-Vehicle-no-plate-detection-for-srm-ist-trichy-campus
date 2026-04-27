from ultralytics import YOLO

class VehicleDetector:
    def __init__(self, engine_path):
        self.model = YOLO(engine_path, task="detect")

    def detect(self, frame):
        results = self.model(
            frame,
            conf=0.5,
            imgsz=640,
            verbose=False
        )[0]

        vehicles = []
        if results.boxes is None:
            return vehicles

        for box, cls in zip(results.boxes.xyxy, results.boxes.cls):
            x1, y1, x2, y2 = map(int, box.tolist())
            vehicle_type = int(cls.item())  # class id
            vehicles.append((x1, y1, x2, y2, vehicle_type))

        return vehicles
