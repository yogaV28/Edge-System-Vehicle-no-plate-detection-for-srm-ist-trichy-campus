from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.websockets import WebSocketDisconnect

import cv2
import base64
import numpy as np
import os
import asyncio
from datetime import datetime, timedelta

from backend.detector import PlateDetector
from backend.ocr import read_plate
from backend.database import SessionLocal, engine, Base
from backend.models import Vehicle
from backend.config import *

# ================= INITIAL SETUP =================
Base.metadata.create_all(bind=engine)

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/data", StaticFiles(directory="data"), name="data")

os.makedirs(IN_IMAGE_PATH, exist_ok=True)
os.makedirs(OUT_IMAGE_PATH, exist_ok=True)

detector = PlateDetector(MODEL_PATH)

# OCR cooldown per plate (seconds)
OCR_COOLDOWN = 5
last_seen = {}  # plate -> datetime

# ================= ROUTES =================
@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/logs")
def logs_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "logs.html"))

# ================= LOGS API =================
@app.get("/api/logs")
def get_logs():
    db = SessionLocal()
    records = db.query(Vehicle).order_by(Vehicle.id.desc()).all()
    db.close()

    return JSONResponse([
        {
            "id": r.id,
            "vehicle_no": r.vehicle_no,
            "status": r.status,
            "time_in": r.time_in.strftime("%Y-%m-%d %H:%M:%S") if r.time_in else "",
            "time_out": r.time_out.strftime("%Y-%m-%d %H:%M:%S") if r.time_out else "",
            "image_path": r.image_path
        }
        for r in records
    ])

# ================= UTIL FUNCTIONS =================
def decode_frame(b64_data: str):
    img_bytes = base64.b64decode(b64_data)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

def encode_frame(frame):
    _, buffer = cv2.imencode(".jpg", frame)
    return base64.b64encode(buffer).decode("utf-8")

def can_run_ocr(plate: str):
    now = datetime.utcnow()
    if plate not in last_seen or (now - last_seen[plate]).seconds > OCR_COOLDOWN:
        last_seen[plate] = now
        return True
    return False

# ================= WEBSOCKET =================
@app.websocket("/ws/{cam_type}")
async def camera_ws(ws: WebSocket, cam_type: str):
    """
    cam_type: in | out
    Browser sends base64 frames
    Backend returns annotated frames
    """
    await ws.accept()
    print(f"[WS CONNECTED] {cam_type}")

    db = SessionLocal()

    try:
        while True:
            data = await ws.receive_text()
            frame = decode_frame(data)

            if frame is None:
                continue

            plates = detector.detect(frame)

            for (x1, y1, x2, y2) in plates:
                crop = frame[y1:y2, x1:x2]
                plate_text = read_plate(crop)

                # Draw bounding box always
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                if not plate_text:
                    continue

                cv2.putText(
                    frame, plate_text, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
                )

                if not can_run_ocr(plate_text):
                    continue

                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

                if cam_type == "in":
                    exists = db.query(Vehicle).filter(
                        Vehicle.vehicle_no == plate_text,
                        Vehicle.status == "IN"
                    ).first()

                    if not exists:
                        img_path = f"{IN_IMAGE_PATH}/{plate_text}_{timestamp}.jpg"
                        cv2.imwrite(img_path, frame)

                        entry = Vehicle(
                            vehicle_no=plate_text,
                            status="IN",
                            time_in=datetime.utcnow(),
                            image_path=img_path
                        )
                        db.add(entry)
                        db.commit()

                elif cam_type == "out":
                    entry = db.query(Vehicle).filter(
                        Vehicle.vehicle_no == plate_text,
                        Vehicle.status == "IN"
                    ).order_by(Vehicle.id.desc()).first()

                    if entry:
                        img_path = f"{OUT_IMAGE_PATH}/{plate_text}_{timestamp}.jpg"
                        cv2.imwrite(img_path, frame)

                        entry.status = "OUT"
                        entry.time_out = datetime.utcnow()
                        entry.image_path = img_path
                        db.commit()

            await ws.send_text(encode_frame(frame))

            # 🔹 FPS CONTROL (Jetson-safe)
            await asyncio.sleep(0.03)  # ~30 FPS max send rate

    except WebSocketDisconnect:
        print(f"[WS DISCONNECTED] {cam_type}")

    except Exception as e:
        print(f"[WS ERROR] {cam_type}: {e}")

    finally:
        db.close()
