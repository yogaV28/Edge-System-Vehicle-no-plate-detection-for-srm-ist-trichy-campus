from ultralytics import YOLO

m = YOLO("models/vehicle.engine")
print(m.names)
