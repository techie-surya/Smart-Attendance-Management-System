"""Configuration for Smart Attendance Management System."""

import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATASET_PATH = os.path.join(DATA_DIR, "dataset")
ENCODINGS_PATH = os.path.join(DATA_DIR, "encodings")
DATABASE_PATH = os.path.join(DATA_DIR, "database")
LOGS_PATH = os.path.join(DATA_DIR, "logs")
REPORTS_PATH = os.path.join(DATA_DIR, "reports")

# File paths
ENCODINGS_FILE = os.path.join(ENCODINGS_PATH, "face_encodings.pkl")
DATABASE_FILE = os.path.join(DATABASE_PATH, "attendance.db")
LOG_FILE = os.path.join(LOGS_PATH, "system_logs.txt")
YOLO_MODEL_PATH = os.path.join(MODELS_DIR, "yolov8n-face.pt")

# Runtime / web settings
APP_ENV = os.getenv("SMART_ATTENDANCE_ENV", "development")
FLASK_HOST = os.getenv("SMART_ATTENDANCE_HOST", "0.0.0.0")
FLASK_PORT = _env_int("SMART_ATTENDANCE_PORT", _env_int("PORT", 5000))
FLASK_DEBUG = _env_bool("SMART_ATTENDANCE_DEBUG", False)
SECRET_KEY = os.getenv("SMART_ATTENDANCE_SECRET_KEY", "change-me-in-production")

# API security and traffic controls
API_KEY = os.getenv("SMART_ATTENDANCE_API_KEY", "").strip()
API_KEY_HEADER = os.getenv("SMART_ATTENDANCE_API_KEY_HEADER", "X-API-Key").strip()
REQUIRE_API_KEY = _env_bool("SMART_ATTENDANCE_REQUIRE_API_KEY", bool(API_KEY))
RATE_LIMIT_WINDOW_SECONDS = _env_int("SMART_ATTENDANCE_RATE_LIMIT_WINDOW", 60)
RATE_LIMIT_MAX_REQUESTS = _env_int("SMART_ATTENDANCE_RATE_LIMIT_MAX_REQUESTS", 120)
MAX_REQUEST_SIZE_MB = _env_int("SMART_ATTENDANCE_MAX_REQUEST_SIZE_MB", 12)
MAX_IMAGE_BYTES = _env_int("SMART_ATTENDANCE_MAX_IMAGE_BYTES", 3_500_000)
MAX_IMAGES_PER_UPLOAD = _env_int("SMART_ATTENDANCE_MAX_IMAGES_PER_UPLOAD", 40)
MAX_STUDENT_ID_LENGTH = _env_int("SMART_ATTENDANCE_MAX_STUDENT_ID_LENGTH", 64)
MAX_NAME_LENGTH = _env_int("SMART_ATTENDANCE_MAX_NAME_LENGTH", 80)
MAX_ROLL_LENGTH = _env_int("SMART_ATTENDANCE_MAX_ROLL_LENGTH", 24)

# API pagination
DEFAULT_PAGE_LIMIT = _env_int("SMART_ATTENDANCE_DEFAULT_PAGE_LIMIT", 100)
MAX_PAGE_LIMIT = _env_int("SMART_ATTENDANCE_MAX_PAGE_LIMIT", 500)

# Camera settings (CCTV-ready)
# Supports multiple formats:
# - USB Camera: "0", "1", "2" (camera device ID)
# - RTSP Stream: "rtsp://username:password@ip:port/stream"
# - RTMP Stream: "rtmp://ip:port/stream"
# - HTTP/MJPEG: "http://ip:port/video"
# - IP Camera: Direct IP camera stream URL
CAMERA_ENTRY_SOURCE = os.getenv("SMART_ATTENDANCE_CAMERA_ENTRY_SOURCE", "0")
CAMERA_EXIT_SOURCE = os.getenv("SMART_ATTENDANCE_CAMERA_EXIT_SOURCE", "0")

# Legacy support - fallback to old numeric IDs if SOURCE not provided
CAMERA_ENTRY_ID = _env_int("SMART_ATTENDANCE_CAMERA_ENTRY_ID", 0)
CAMERA_EXIT_ID = _env_int("SMART_ATTENDANCE_CAMERA_EXIT_ID", 0)

WINDOW_WIDTH = _env_int("SMART_ATTENDANCE_WINDOW_WIDTH", 640)
WINDOW_HEIGHT = _env_int("SMART_ATTENDANCE_WINDOW_HEIGHT", 480)

# Camera connection settings for CCTV/network streams
CAMERA_RECONNECT_ATTEMPTS = _env_int("SMART_ATTENDANCE_CAMERA_RECONNECT_ATTEMPTS", 3)
CAMERA_RECONNECT_DELAY_SECONDS = _env_int("SMART_ATTENDANCE_CAMERA_RECONNECT_DELAY", 5)
CAMERA_STREAM_BUFFER_SIZE = _env_int("SMART_ATTENDANCE_CAMERA_BUFFER_SIZE", 1)

# Recognition settings
# HOG is faster but less accurate - CNN is more accurate but slower
# Using CNN for better accuracy to prevent misidentification
FACE_DETECTION_MODEL = os.getenv("SMART_ATTENDANCE_FACE_DETECTION_MODEL", "cnn")
# Set tolerance to 0.5 for strict matching to avoid confusing different people
# Lower = stricter (0.4-0.5), Higher = more lenient (0.6-0.65)
FACE_RECOGNITION_TOLERANCE = _env_float("SMART_ATTENDANCE_FACE_TOLERANCE", 0.5)
FACE_ENCODING_MODEL = os.getenv("SMART_ATTENDANCE_FACE_ENCODING_MODEL", "large")
# Using 0.75 scale for better face detail capture
RECOGNITION_FRAME_SCALE = _env_float("SMART_ATTENDANCE_RECOGNITION_FRAME_SCALE", 0.75)
RECOGNITION_INTERVAL_SECONDS = _env_float("SMART_ATTENDANCE_RECOGNITION_INTERVAL", 1.5)
ENABLE_YOLO_IF_AVAILABLE = _env_bool("SMART_ATTENDANCE_ENABLE_YOLO", True)
YOLO_CONFIDENCE_THRESHOLD = _env_float("SMART_ATTENDANCE_YOLO_CONFIDENCE", 0.25)

# Teacher camera policy
CAMERA_POLICY_ALWAYS_ON = "always_on"
CAMERA_POLICY_ON_DEMAND = "on_demand"
DEFAULT_CAMERA_POLICY = CAMERA_POLICY_ON_DEMAND
CAMERA_RUN_MODE_ONCE = "once"
CAMERA_RUN_MODE_SESSION = "session"
CAMERA_RUN_MODE_INTERVAL = "interval"
DEFAULT_CAMERA_RUN_MODE = CAMERA_RUN_MODE_ONCE

# Timed monitoring controls
DEFAULT_RUN_INTERVAL_SECONDS = _env_int("SMART_ATTENDANCE_RUN_INTERVAL_SECONDS", 45)
DEFAULT_SESSION_DURATION_MINUTES = _env_int("SMART_ATTENDANCE_SESSION_DURATION_MINUTES", 90)
DEFAULT_FAIR_MOTION_THRESHOLD = _env_float("SMART_ATTENDANCE_FAIR_MOTION_THRESHOLD", 0.018)

# Data collection settings
IMAGES_PER_STUDENT = _env_int("SMART_ATTENDANCE_IMAGES_PER_STUDENT", 15)
IMAGE_CAPTURE_DELAY = _env_float("SMART_ATTENDANCE_IMAGE_CAPTURE_DELAY", 0.1)

# Attendance settings
MINIMUM_DURATION = _env_int("SMART_ATTENDANCE_MINIMUM_DURATION", 90)
MAX_RECOGNITION_ATTEMPTS = _env_int("SMART_ATTENDANCE_MAX_RECOGNITION_ATTEMPTS", 3)

# Display settings
FONT_SCALE = _env_float("SMART_ATTENDANCE_FONT_SCALE", 0.7)
FONT_THICKNESS = _env_int("SMART_ATTENDANCE_FONT_THICKNESS", 2)

# Colors (BGR for OpenCV)
COLOR_GREEN = (0, 255, 0)
COLOR_RED = (0, 0, 255)
COLOR_BLUE = (255, 0, 0)
COLOR_WHITE = (255, 255, 255)

# Student ID format
STUDENT_ID_PREFIX = "student_"
STUDENT_ID_LENGTH = 10

# Subject settings
SUBJECT_OPTIONS = [
    "Operating System",
    "Compiler Design",
    "ESSP",
    "Data Science",
    "Machine Learning",
]
DEFAULT_SUBJECT = SUBJECT_OPTIONS[0]

# Database settings
DB_TIMEOUT = _env_int("SMART_ATTENDANCE_DB_TIMEOUT", 10)
MAX_RECENT_ITEMS = _env_int("SMART_ATTENDANCE_MAX_RECENT_ITEMS", 10)

# Logging settings
LOG_LEVEL = os.getenv("SMART_ATTENDANCE_LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv(
    "SMART_ATTENDANCE_LOG_FORMAT",
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
LOG_MAX_BYTES = _env_int("SMART_ATTENDANCE_LOG_MAX_BYTES", 2_500_000)
LOG_BACKUP_COUNT = _env_int("SMART_ATTENDANCE_LOG_BACKUP_COUNT", 5)

# Report settings
REPORT_DATE_FORMAT = "%Y-%m-%d"
REPORT_TIME_FORMAT = "%H:%M:%S"
REPORT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
