import sys, os, time, csv
import cv2
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem,
    QMessageBox, QFileDialog
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QTimer, Qt

from detector_vehicle import VehicleDetector
from detector_plate import PlateDetector
from ocr_super import read_plate
from camera_config import CAMERAS
from database import SessionLocal, engine, Base
from models import Vehicle

# ================= DATABASE INIT =================
Base.metadata.create_all(bind=engine)
db = SessionLocal()

os.makedirs("data/in", exist_ok=True)
os.makedirs("data/out", exist_ok=True)

# ⚠️ Use .pt first (TensorRT engine must be built on SAME Jetson)
vehicle_detector = VehicleDetector("models/vehicle.pt")
plate_detector = PlateDetector("models/plate.pt")

VEHICLE_CLASSES = {
    0: "Bike",
    1: "Bus",
    2: "Car",
    3: "Hiace",
    4: "Rickshaw",
    5: "Tractor",
    6: "Truck"
}

# ================= CAMERA HANDLER =================
class IPCamera:
    def __init__(self, cam):
        self.name = cam["name"]
        self.role = cam["role"]
        self.source = cam["rtsp"]
        self.frame_id = 0

        self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

    def read(self):
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            time.sleep(0.2)

        ret, frame = self.cap.read()

        # 🔁 Loop recorded CCTV footage
        if not ret and isinstance(self.source, str) and self.source.lower().endswith(
            (".mp4", ".avi", ".asf", ".mkv")
        ):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()

        return ret, frame

# ================= MAIN APPLICATION =================
class ANPRApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ANPR – Vehicle & Plate Detection")
        self.resize(1600, 950)

        title = QLabel("Automatic Number Plate Recognition")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:26px; font-weight:bold")

        self.cameras = [IPCamera(c) for c in CAMERAS]
        self.labels = []

        grid = QGridLayout()
        r = c = 0
        for cam in self.cameras:
            lbl = QLabel(cam.name)
            lbl.setFixedSize(380, 240)
            lbl.setStyleSheet("border:2px solid black")
            self.labels.append(lbl)
            grid.addWidget(lbl, r, c)
            c += 1
            if c == 4:
                c = 0
                r += 1

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["No", "Plate", "Vehicle Type", "Status", "Time IN", "Time OUT"]
        )

        export_btn = QPushButton("Export Database to CSV")
        export_btn.setStyleSheet(
            "font-size:16px; padding:10px; background:#2ecc71; color:white;"
        )
        export_btn.clicked.connect(self.export_csv)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(grid)
        layout.addWidget(QLabel("Live Vehicle Status"))
        layout.addWidget(self.table)
        layout.addWidget(export_btn)
        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frames)
        self.timer.start(30)  # ~35 FPS

    # ================= FRAME LOOP =================
    def update_frames(self):
        for cam, label in zip(self.cameras, self.labels):
            cam.frame_id += 1
            ret, frame = cam.read()
            if not ret:
                continue

            display = frame.copy()

            if cam.frame_id % 5 == 0:
                vehicles = vehicle_detector.detect(frame)
                plates = plate_detector.detect(frame)  # FULL FRAME

                for vx1, vy1, vx2, vy2, vcls in vehicles:
                    vtype = VEHICLE_CLASSES.get(vcls, "Unknown")

                    # VEHICLE BOX
                    cv2.rectangle(display, (vx1, vy1), (vx2, vy2), (0, 255, 0), 2)
                    cv2.putText(
                        display, vtype, (vx1, vy1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                    )

                    matched_plate = None
                    for px1, py1, px2, py2 in plates:
                        if px1 > vx1 and py1 > vy1 and px2 < vx2 and py2 < vy2:
                            matched_plate = (px1, py1, px2, py2)
                            break

                    if not matched_plate:
                        continue

                    px1, py1, px2, py2 = matched_plate

                    # PLATE BOX
                    cv2.rectangle(display, (px1, py1), (px2, py2), (0, 0, 255), 2)

                    plate_crop = frame[py1:py2, px1:px2]
                    text = read_plate(plate_crop)

                    if not text:
                        continue

                    now = datetime.utcnow()

                    cv2.putText(
                        display, text, (px1, py1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2
                    )

                    if cam.role == "IN":
                        path = f"data/in/{text}_{int(time.time())}.jpg"
                        cv2.imwrite(path, frame)
                        db.add(Vehicle(
                            vehicle_no=text,
                            vehicle_type=vtype,
                            status="IN",
                            time_in=now,
                            in_image=path
                        ))
                        db.commit()
                    else:
                        entry = db.query(Vehicle).filter(
                            Vehicle.vehicle_no == text,
                            Vehicle.status == "IN"
                        ).first()

                        if entry:
                            path = f"data/out/{text}_{int(time.time())}.jpg"
                            cv2.imwrite(path, frame)
                            entry.status = "OUT"
                            entry.time_out = now
                            entry.out_image = path
                            db.commit()

            self.show_frame(display, label)

        self.refresh_table()

    # ================= DISPLAY =================
    def show_frame(self, frame, label):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        label.setPixmap(QPixmap.fromImage(img).scaled(
            label.size(), Qt.KeepAspectRatio
        ))

    # ================= TABLE =================
    def refresh_table(self):
        records = db.query(Vehicle).all()
        self.table.setRowCount(len(records))
        for i, r in enumerate(records):
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(r.vehicle_no))
            self.table.setItem(i, 2, QTableWidgetItem(r.vehicle_type))
            self.table.setItem(i, 3, QTableWidgetItem(r.status))
            self.table.setItem(i, 4, QTableWidgetItem(str(r.time_in)))
            self.table.setItem(i, 5, QTableWidgetItem(str(r.time_out) if r.time_out else "-"))

    # ================= CSV EXPORT =================
    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "vehicle_logs.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        records = db.query(Vehicle).all()
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Plate", "Vehicle Type", "Status",
                "Time IN", "Time OUT", "IN Image", "OUT Image"
            ])
            for r in records:
                writer.writerow([
                    r.vehicle_no, r.vehicle_type, r.status,
                    r.time_in, r.time_out, r.in_image, r.out_image
                ])

        QMessageBox.information(self, "Success", "CSV Exported Successfully")

# ================= RUN =================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ANPRApp()
    win.show()
    sys.exit(app.exec())
