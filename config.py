# ===================== MODEL PATHS =====================

# TensorRT engine for vehicle detection
VEHICLE_MODEL_PATH = "models/vehicle.engine"   # fallback: .pt

# TensorRT engine for number plate detection
PLATE_MODEL_PATH = "models/plate.engine"       # fallback: .pt


# ===================== IMAGE STORAGE =====================

IN_IMAGE_PATH = "data/in"
OUT_IMAGE_PATH = "data/out"


# ===================== CAMERA / STREAM =====================

# Target display FPS (RTSP stream FPS, NOT detection FPS)
STREAM_FPS = 35

# Frame skip for detection (35 / 5 ≈ 7 FPS detection)
FRAME_SKIP = 5


# ===================== INFERENCE =====================

# YOLO input size
INFER_SIZE = 640

# Confidence thresholds
VEHICLE_CONF = 0.5
PLATE_CONF = 0.4


# ===================== OCR =====================

# Cooldown to avoid duplicate OCR for same plate (seconds)
OCR_COOLDOWN = 5

# Minimum valid plate length
MIN_PLATE_LENGTH = 6


# ===================== DATABASE =====================

DB_PATH = "anpr.db"


# ===================== VEHICLE CLASS MAP =====================
# Must match your vehicle model training classes

VEHICLE_CLASSES = {
    0: "Bike",
    1: "Bus",
    2: "Car",
    3: "Hiace",
    4: "Rickshaw",
    5: "Tractor",
    6: "Truck"
}