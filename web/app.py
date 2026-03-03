"""Flask web app for Smart Attendance Management System."""

import os
import logging
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from io import BytesIO
from logging.handlers import RotatingFileHandler

import cv2
import face_recognition
import numpy as np
from flask import Flask, jsonify, render_template, request, send_from_directory, g
from PIL import Image
from werkzeug.exceptions import HTTPException

# Add parent directory to path for src imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src.config as config
from src.attendance_manager import AttendanceManager
from src.database_manager import DatabaseManager
from src.encode_faces import FaceEncoder
from src.rate_limiter import RateLimiter
from src.recognition_service import RecognitionService
from src.utils import ReportGenerator
from src.validators import (
    ValidationError,
    validate_camera_run_mode,
    parse_limit_offset,
    validate_base64_image,
    validate_date,
    validate_name,
    validate_roll_number,
    validate_subject,
    validate_status,
    validate_student_id,
)


def _configure_logging():
    os.makedirs(config.LOGS_PATH, exist_ok=True)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter(config.LOG_FORMAT)

    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


_configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_REQUEST_SIZE_MB * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 300  # Cache static files for 5 minutes
app.config["PROPAGATE_EXCEPTIONS"] = True  # Better error handling

db = DatabaseManager()
report_gen = ReportGenerator()
attendance_mgr = AttendanceManager()

# Initialize recognizer with error handling
try:
    recognizer = RecognitionService()
    logger.info("Recognition service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize recognition service: {e}")
    logger.warning("Server will start but face recognition may not work until encodings are generated")
    recognizer = RecognitionService()  # Create with default state

rate_limiter = RateLimiter(
    window_seconds=config.RATE_LIMIT_WINDOW_SECONDS,
    max_requests=config.RATE_LIMIT_MAX_REQUESTS,
)

PUBLIC_API_PATHS = {"/api/health"}


def _bool_from_any(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_from_any(value, default=0, minimum=1):
    if value in (None, ""):
        return max(minimum, int(default))
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return max(minimum, int(default))
    return max(minimum, parsed)


def _float_from_any(value, default=0.0, minimum=0.0):
    if value in (None, ""):
        return max(minimum, float(default))
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return max(minimum, float(default))
    return max(minimum, parsed)


def _json_error(message: str, status_code: int = 400):
    return jsonify({"success": False, "message": message, "request_id": g.get("request_id")}), status_code


def _json_body():
    return request.get_json(silent=True) or {}


def _safe_dataset_folder(student_id: str) -> str:
    root = os.path.abspath(config.DATASET_PATH)
    folder = os.path.abspath(os.path.join(root, student_id))
    if not folder.startswith(root + os.sep) and folder != root:
        raise ValidationError("invalid storage path")
    return folder


def _current_settings():
    settings = db.get_system_settings()
    camera_policy = settings.get("camera_policy", config.DEFAULT_CAMERA_POLICY)
    camera_run_mode = settings.get("camera_run_mode", config.DEFAULT_CAMERA_RUN_MODE)
    active_subject = settings.get("active_subject", config.DEFAULT_SUBJECT)
    run_interval_seconds = _int_from_any(
        settings.get("run_interval_seconds"), config.DEFAULT_RUN_INTERVAL_SECONDS, minimum=3
    )
    session_duration_minutes = _int_from_any(
        settings.get("session_duration_minutes"),
        config.DEFAULT_SESSION_DURATION_MINUTES,
        minimum=1,
    )
    fair_motion_threshold = _float_from_any(
        settings.get("fair_motion_threshold"),
        config.DEFAULT_FAIR_MOTION_THRESHOLD,
        minimum=0.0,
    )
    minimum_duration_minutes = _int_from_any(
        settings.get("minimum_duration_minutes"),
        config.MINIMUM_DURATION,
        minimum=1,
    )

    use_yolo_requested = _bool_from_any(
        settings.get("use_yolo"), config.ENABLE_YOLO_IF_AVAILABLE
    )
    yolo_active = recognizer.set_yolo_active(use_yolo_requested)
    return {
        "camera_policy": camera_policy,
        "camera_run_mode": camera_run_mode,
        "active_subject": active_subject,
        "run_interval_seconds": run_interval_seconds,
        "session_duration_minutes": session_duration_minutes,
        "fair_motion_threshold": fair_motion_threshold,
        "minimum_duration_minutes": minimum_duration_minutes,
        "subject_options": config.SUBJECT_OPTIONS,
        "use_yolo": yolo_active,
        "use_yolo_requested": use_yolo_requested,
        "yolo_supported": recognizer.yolo_supported,
        "yolo_active": yolo_active,
        "recognition_interval_seconds": config.RECOGNITION_INTERVAL_SECONDS,
    }


def _get_minimum_duration():
    """Get current minimum duration from database settings."""
    settings = db.get_system_settings()
    return _int_from_any(
        settings.get("minimum_duration_minutes"),
        config.MINIMUM_DURATION,
        minimum=1,
    )


def _dashboard_payload():
    today = datetime.now().strftime(config.REPORT_DATE_FORMAT)
    records = db.get_attendance_by_date(today)
    total = len(records)
    present = sum(1 for record in records if record[5] == "PRESENT")
    absent = sum(1 for record in records if record[5] == "ABSENT")
    return {
        "date": today,
        "total": total,
        "present": present,
        "absent": absent,
        "attendance_rate": round((present / total) * 100, 2) if total else 0,
        "records": records,
    }


def _student_payload():
    students = db.get_all_students()
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "roll_number": row[2],
            "registered_date": row[3],
        }
        for row in students
    ]


def _attendance_payload(records):
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "entry_time": row[2],
            "exit_time": row[3],
            "duration": row[4],
            "status": row[5],
            "date": row[6],
            "subject": row[7] if len(row) > 7 else config.DEFAULT_SUBJECT,
        }
        for row in records
    ]


def _recent_entries_payload(limit=config.MAX_RECENT_ITEMS):
    rows = db.get_recent_entries(limit=limit)
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "entry_time": row[2],
            "status": row[3],
        }
        for row in rows
    ]


def _recent_exits_payload(limit=config.MAX_RECENT_ITEMS):
    rows = db.get_recent_exits(limit=limit)
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "entry_time": row[2],
            "exit_time": row[3],
            "duration": row[4],
            "status": row[5],
            "date": row[6],
            "subject": row[7] if len(row) > 7 else config.DEFAULT_SUBJECT,
        }
        for row in rows
    ]


def _inside_payload(limit=config.MAX_RECENT_ITEMS):
    rows = db.get_inside_students(limit=limit)
    return [
        {
            "student_id": row[0],
            "name": row[1],
            "entry_time": row[2],
            "date": row[3],
        }
        for row in rows
    ]


def _recognize_or_error(image_data):
    if not image_data:
        return None, _json_error("image payload is required", 400)

    validate_base64_image(image_data)
    
    # Check if encodings are loaded
    if not recognizer.known_encodings:
        return None, _json_error("no face encodings available - please register students and generate encodings first", 503)
    
    match = recognizer.recognize_from_base64(image_data)
    if not match:
        return None, _json_error(
            "face not recognized - please ensure: (1) face is clearly visible, "
            "(2) good lighting (avoid backlighting), (3) facing camera directly, "
            "(4) student is registered with encodings generated",
            404
        )

    return match, None


@app.before_request
def _before_request():
    g.started_at = time.perf_counter()
    g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    if not request.path.startswith("/api/"):
        return None

    if config.REQUIRE_API_KEY and request.path not in PUBLIC_API_PATHS:
        provided = request.headers.get(config.API_KEY_HEADER, "").strip()
        if not provided or provided != config.API_KEY:
            return _json_error("unauthorized", 401)

    key = f"{request.remote_addr}:{request.path}"
    allowed, retry_after = rate_limiter.check(key)
    if not allowed:
        response, status = _json_error("rate limit exceeded", 429)
        response.headers["Retry-After"] = str(retry_after)
        return response, status

    return None


@app.after_request
def _after_request(response):
    response.headers["X-Request-ID"] = g.get("request_id", "")
    if request.path.startswith("/api/"):
        elapsed_ms = int((time.perf_counter() - g.get("started_at", time.perf_counter())) * 1000)
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%s",
            g.get("request_id"),
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )
    return response


@app.errorhandler(ValidationError)
def _handle_validation_error(exc):
    return _json_error(str(exc), 400)


@app.errorhandler(413)
def _handle_payload_too_large(_exc):
    return _json_error("request payload too large", 413)


@app.errorhandler(Exception)
def _handle_unexpected_error(exc):
    # Log the full traceback
    logger.exception("Unhandled exception - server continuing")
    
    # Handle HTTP exceptions (404, 500, etc.) properly
    if isinstance(exc, HTTPException):
        if request.path.startswith("/api/"):
            return _json_error(exc.description or "error", exc.code or 500)
        return exc
    
    # For non-HTTP exceptions
    if request.path.startswith("/api/"):
        return _json_error("internal server error - check logs for details", 500)
    
    return render_template("base.html"), 500


@app.route("/")
@app.route("/dashboard")
def dashboard():
    payload = _dashboard_payload()
    return render_template(
        "dashboard.html",
        stats={
            "date": payload["date"],
            "total": payload["total"],
            "present": payload["present"],
            "absent": payload["absent"],
            "attendance_rate": payload["attendance_rate"],
        },
        records=payload["records"],
    )


@app.route("/register")
def register_page():
    return render_template(
        "register.html",
        images_per_student=config.IMAGES_PER_STUDENT,
    )


@app.route("/entry")
def entry_page():
    settings = _current_settings()
    return render_template("entry.html", settings=settings)


@app.route("/exit")
def exit_page():
    settings = _current_settings()
    return render_template(
        "exit.html",
        settings=settings,
    )


@app.route("/reports")
def reports_page():
    selected_subject = validate_subject(
        request.args.get("subject"), "subject", allow_empty=True
    )
    all_records = db.get_all_attendance(subject=selected_subject)
    students = db.get_all_students()
    today = datetime.now().strftime(config.REPORT_DATE_FORMAT)
    return render_template(
        "reports.html",
        records=all_records,
        students=students,
        today=today,
        subjects=config.SUBJECT_OPTIONS,
        selected_subject=selected_subject,
    )


@app.route("/student-attendance")
def student_attendance_page():
    return render_template(
        "student_attendance.html",
        subjects=config.SUBJECT_OPTIONS,
    )


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        settings = _current_settings()
        return jsonify({"success": True, "settings": settings, "runtime": recognizer.get_runtime_info()})

    data = _json_body()
    camera_policy = data.get("camera_policy")
    if camera_policy is not None:
        if camera_policy not in {
            config.CAMERA_POLICY_ALWAYS_ON,
            config.CAMERA_POLICY_ON_DEMAND,
        }:
            raise ValidationError("invalid camera policy")
        db.set_setting("camera_policy", camera_policy)

    if "camera_run_mode" in data:
        run_mode = validate_camera_run_mode(data.get("camera_run_mode"))
        db.set_setting("camera_run_mode", run_mode)

    if "active_subject" in data:
        active_subject = validate_subject(data.get("active_subject"))
        db.set_setting("active_subject", active_subject)

    if "run_interval_seconds" in data:
        interval_seconds = _int_from_any(data.get("run_interval_seconds"), minimum=3)
        db.set_setting("run_interval_seconds", str(interval_seconds))

    if "session_duration_minutes" in data:
        session_minutes = _int_from_any(data.get("session_duration_minutes"), minimum=1)
        db.set_setting("session_duration_minutes", str(session_minutes))

    if "fair_motion_threshold" in data:
        motion_threshold = _float_from_any(data.get("fair_motion_threshold"), minimum=0.0)
        db.set_setting("fair_motion_threshold", str(motion_threshold))

    if "minimum_duration_minutes" in data:
        min_duration = _int_from_any(data.get("minimum_duration_minutes"), minimum=1)
        db.set_setting("minimum_duration_minutes", str(min_duration))

    if "use_yolo" in data:
        use_yolo = _bool_from_any(data.get("use_yolo"))
        db.set_setting("use_yolo", str(use_yolo).lower())

    settings = _current_settings()
    return jsonify({"success": True, "settings": settings, "runtime": recognizer.get_runtime_info()})


@app.route("/api/health")
def api_health():
    return jsonify(
        {
            "success": True,
            "timestamp": datetime.now().strftime(config.REPORT_DATETIME_FORMAT),
            "runtime": recognizer.get_runtime_info(),
            "settings": _current_settings(),
        }
    )


@app.route("/api/students", methods=["GET"])
def api_get_students():
    """Get list of all registered students for manual attendance."""
    try:
        students = db.get_all_students()
        # get_all_students returns tuples: (student_id, name, roll_number, registered_date)
        student_list = [
            {
                "student_id": s[0],
                "name": s[1],
                "roll_number": s[2],
            }
            for s in students
        ]
        return jsonify({"success": True, "students": student_list})
    except Exception as e:
        logger.error(f"Error fetching students list: {e}")
        return _json_error("failed to load students", 500)


@app.route("/api/register-student", methods=["POST"])
def register_student():
    data = _json_body()
    student_id = validate_student_id(data.get("student_id"))
    name = validate_name(data.get("name"))
    roll_number = validate_roll_number(data.get("roll_number"))

    success = db.register_student(student_id, name, roll_number)
    if success:
        return jsonify({"success": True, "message": "Student registered successfully"})
    return _json_error("student_id or roll_number already exists", 409)


@app.route("/api/save-face-images", methods=["POST"])
def save_face_images():
    """Save face images for a student after validation."""
    try:
        data = _json_body()
        student_id = validate_student_id(data.get("student_id"))
        images = data.get("images") or []

        if not isinstance(images, list) or not images:
            raise ValidationError("at least one image is required")
        if len(images) > config.MAX_IMAGES_PER_UPLOAD:
            raise ValidationError(
                f"too many images in one request (max {config.MAX_IMAGES_PER_UPLOAD})"
            )

        folder_path = _safe_dataset_folder(student_id)
        os.makedirs(folder_path, exist_ok=True)

        saved_count = 0
        no_face_count = 0
        invalid_count = 0
        
        def process_single_image(index_and_payload):
            """Process a single image for face detection - designed for parallel execution."""
            index, image_payload = index_and_payload
            try:
                # Validate and decode base64 image
                image_bytes = validate_base64_image(image_payload)
                image = Image.open(BytesIO(image_bytes)).convert("RGB")
                
                # Convert PIL image to numpy array for face detection
                image_np = np.array(image)
                
                # Detect faces using HOG with same upsampling as encoding (consistency)
                # Using upsample=1 balances speed with reliable face detection
                face_locations = face_recognition.face_locations(
                    image_np, 
                    model="hog",
                    number_of_times_to_upsample=1  # Match encoding for consistency
                )
                
                if len(face_locations) > 0:
                    return ("success", image, index)
                else:
                    logger.info(f"Image {index} skipped - no face detected (student_id={student_id})")
                    return ("no_face", None, index)
                    
            except ValidationError:
                return ("invalid", None, index)
            except Exception as e:
                logger.warning("invalid image skipped at index=%s for student_id=%s: %s", index, student_id, str(e))
                return ("invalid", None, index)
        
        # Process images in parallel with timeout protection
        max_workers = min(4, len(images))  # Limit concurrent workers
        timeout_per_batch = 30  # 30 seconds total timeout
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(process_single_image, (i, img)): i 
                    for i, img in enumerate(images, start=1)
                }
                
                # Collect results with timeout
                results = []
                start_time = time.time()
                for future in futures:
                    remaining_time = timeout_per_batch - (time.time() - start_time)
                    if remaining_time <= 0:
                        logger.warning(f"Image processing timeout for student_id={student_id}")
                        break
                        
                    try:
                        result = future.result(timeout=remaining_time)
                        results.append(result)
                    except FuturesTimeoutError:
                        logger.warning(f"Image processing timeout for student_id={student_id}")
                        break
                    except Exception as e:
                        logger.warning(f"Image processing error: {e}")
                        results.append(("invalid", None, futures[future]))
                        
        except Exception as e:
            logger.error(f"Parallel processing failed for student_id={student_id}: {e}")
            raise ValidationError("image processing failed - please try again with fewer images")
        
        # Save successfully processed images
        for status, image, index in results:
            if status == "success":
                try:
                    image.save(os.path.join(folder_path, f"img{saved_count + 1}.jpg"), "JPEG", quality=85)
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to save image {index}: {e}")
                    invalid_count += 1
            elif status == "no_face":
                no_face_count += 1
            elif status == "invalid":
                invalid_count += 1

        # Require at least 5 images with faces for reliable encoding
        # Reduced from previous higher requirements for better user experience
        min_required_images = 5
        if saved_count < min_required_images:
            # Clean up any saved images if we don't have enough
            if os.path.exists(folder_path):
                try:
                    for file in os.listdir(folder_path):
                        os.remove(os.path.join(folder_path, file))
                    os.rmdir(folder_path)  # Remove empty folder too
                except Exception as e:
                    logger.error(f"Failed to cleanup folder {folder_path}: {e}")
            
            # Provide detailed error message with guidance
            error_parts = []
            error_parts.append(f"Only {saved_count} out of {len(images)} images had detectable faces (minimum {min_required_images} required).\n")
            
            if no_face_count > 0:
                error_parts.append(f"{no_face_count} images had no face detected.")
            if invalid_count > 0:
                error_parts.append(f"{invalid_count} images were invalid.")
                
            error_parts.append("\nPlease ensure:")
            error_parts.append("• Your face is clearly visible and centered")
            error_parts.append("• You are in a well-lit area (avoid backlighting)")
            error_parts.append("• The camera lens is clean and in focus")
            error_parts.append("• You are facing the camera directly")
            
            error_message = "\n".join(error_parts)
            logger.warning(f"Face validation failed for {student_id}: {saved_count}/{len(images)} valid (need {min_required_images})")
            raise ValidationError(error_message)

        logger.info(f"Successfully saved {saved_count} images for {student_id}")
        return jsonify({
            "success": True, 
            "message": f"saved {saved_count} images with detected faces",
            "details": {
                "saved": saved_count,
                "no_face_detected": no_face_count,
                "invalid": invalid_count,
                "total_submitted": len(images)
            }
        })
        
    except ValidationError as e:
        logger.warning(f"Validation error in save_face_images: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in save_face_images")
        return _json_error(f"image processing failed: {str(e)}", 500)


@app.route("/api/encode-student/<student_id>", methods=["POST"])
def encode_student(student_id):
    """Encode faces for a single student. MUCH faster than re-encoding all students.
    This is automatically called after saving face images for a new student.
    """
    try:
        student_id = validate_student_id(student_id)
        
        logger.info(f"Encoding faces for student: {student_id}")
        start_time = time.time()
        
        encoder = FaceEncoder()
        success, num_encoded = encoder.encode_single_student(student_id)
        
        elapsed = time.time() - start_time
        logger.info(f"Student encoding completed in {elapsed:.2f}s - {num_encoded} faces encoded")
        
        if success:
            # Reload encodings in recognizer
            recognizer.load_encodings(force=True)
            return jsonify({
                "success": True,
                "message": f"encoded {num_encoded} faces for {student_id}",
                "elapsed_seconds": round(elapsed, 2),
                "num_faces_encoded": num_encoded
            })
        
        logger.error(f"Failed to encode faces for {student_id}")
        return _json_error(f"failed to encode faces for {student_id}", 500)
        
    except ValidationError as e:
        logger.error(f"Validation error in encode_student: {e}")
        return _json_error(str(e), 400)
    except Exception as e:
        logger.exception(f"Unexpected error encoding student {student_id}")
        return _json_error(f"encoding failed: {str(e)}", 500)


@app.route("/api/generate-encodings", methods=["POST"])
def generate_encodings():
    """Generate face encodings from saved images. 
    
    NOTE: This re-encodes ALL students and may take time.
    For new students, use /api/encode-student/<student_id> instead (much faster).
    """
    logger.info("Starting FULL face encoding generation (all students)...")
    start_time = time.time()
    
    encoder = FaceEncoder()
    success = encoder.run()
    
    elapsed = time.time() - start_time
    logger.info(f"Face encoding generation completed in {elapsed:.2f}s - success={success}")
    
    if success:
        recognizer.load_encodings(force=True)
        return jsonify({
            "success": True, 
            "message": "encodings generated successfully",
            "elapsed_seconds": round(elapsed, 2)
        })
    return _json_error("failed to generate encodings", 500)


@app.route("/api/recognize-entry", methods=["POST"])
def recognize_entry():
    data = _json_body()
    image_data = data.get("image")
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)
    if not subject:
        subject = db.get_setting("active_subject", config.DEFAULT_SUBJECT)
    
    match, error_response = _recognize_or_error(image_data)
    if error_response:
        return error_response

    student_id = match["student_id"]
    name = validate_name(match["name"])
    confidence = match["confidence"]

    if not db.get_student_info(student_id):
        return _json_error("recognized student is not registered", 404)

    entry_result = db.mark_entry(student_id, name, subject=subject)
    if not entry_result:
        logger.warning(f"Entry already marked for {name} ({student_id}) - subject: {subject}")
        return _json_error(f"{name} is already marked inside for {subject}", 409)

    # Use the actual timestamp from database (not a new one!)
    entry_id = entry_result["entry_id"]
    entry_time = entry_result["entry_time"]
    entry_subject = entry_result.get("subject", subject)
    
    # Log successful entry with subject
    logger.info(
        f"Entry marked: {name} ({student_id}) at {entry_time} - "
        f"subject: {entry_subject}"
    )
    
    return jsonify(
        {
            "success": True,
            "message": f"entry marked for {entry_subject}",
            "entry_id": entry_id,
            "student_id": student_id,
            "student_name": name,
            "confidence": confidence,
            "entry_time": entry_time,
            "subject": entry_subject,
        }
    )


@app.route("/api/recognize-exit", methods=["POST"])
def recognize_exit():
    data = _json_body()
    image_data = data.get("image")
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)
    if not subject:
        subject = db.get_setting("active_subject", config.DEFAULT_SUBJECT)
    
    match, error_response = _recognize_or_error(image_data)
    if error_response:
        return error_response

    student_id = match["student_id"]
    name = validate_name(match["name"])
    confidence = match["confidence"]

    if not db.get_student_info(student_id):
        return _json_error("recognized student is not registered", 404)

    exit_result = db.mark_exit_and_save_attendance(
        student_id=student_id,
        name=name,
        minimum_duration=_get_minimum_duration(),
        subject=subject,
    )
    if not exit_result:
        logger.warning(f"No active entry found for {name} ({student_id}) - subject: {subject}")
        return _json_error(
            f"no active entry found for {name} in {subject} - please mark entry first for this subject",
            404
        )

    # Log successful exit with subject
    logger.info(
        f"Exit marked: {name} ({student_id}) - subject: {exit_result.get('subject', subject)} - "
        f"status: {exit_result['status']}"
    )

    return jsonify(
        {
            "success": True,
            "message": "exit marked and attendance recorded",
            "student_id": student_id,
            "student_name": name,
            "confidence": confidence,
            "entry_time": exit_result["entry_time"],
            "exit_time": exit_result["exit_time"],
            "duration_minutes": exit_result["duration"],
            "attendance_status": exit_result["status"],
            "date": exit_result["date"],
            "subject": exit_result["subject"],
        }
    )


# Backward compatible aliases
@app.route("/api/mark-entry", methods=["POST"])
def mark_entry():
    data = _json_body()
    if data.get("image"):
        return recognize_entry()

    student_id = validate_student_id(data.get("student_id"))
    name = validate_name(data.get("name"))
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)
    if not subject:
        subject = db.get_setting("active_subject", config.DEFAULT_SUBJECT)

    if not db.get_student_info(student_id):
        return _json_error("student not registered", 404)

    entry_result = db.mark_entry(student_id, name, subject=subject)
    if not entry_result:
        return _json_error(f"{name} is already marked inside for {subject}", 409)

    return jsonify(
        {
            "success": True,
            "message": f"entry marked for {subject}",
            "entry_id": entry_result["entry_id"],
            "student_id": student_id,
            "student_name": name,
            "entry_time": entry_result["entry_time"],
            "subject": entry_result.get("subject", subject),
        }
    )


@app.route("/api/mark-exit", methods=["POST"])
def mark_exit():
    data = _json_body()
    if data.get("image"):
        return recognize_exit()

    student_id = validate_student_id(data.get("student_id"))
    name = validate_name(data.get("name"))
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)
    if not subject:
        subject = db.get_setting("active_subject", config.DEFAULT_SUBJECT)

    if not db.get_student_info(student_id):
        return _json_error("student not registered", 404)

    exit_result = db.mark_exit_and_save_attendance(
        student_id=student_id,
        name=name,
        minimum_duration=_get_minimum_duration(),
        subject=subject,
    )
    if not exit_result:
        return _json_error("no active entry found", 409)

    return jsonify(
        {
            "success": True,
            "message": "exit marked successfully",
            "student_id": student_id,
            "student_name": name,
            "entry_time": exit_result["entry_time"],
            "exit_time": exit_result["exit_time"],
            "duration_minutes": exit_result["duration"],
            "attendance_status": exit_result["status"],
            "date": exit_result["date"],
            "subject": exit_result["subject"],
        }
    )


@app.route("/api/manual-attendance", methods=["POST"])
def manual_attendance():
    """Manual correction endpoint for teachers/admins."""
    data = _json_body()
    student_id = validate_student_id(data.get("student_id"))
    name = validate_name(data.get("name"))
    entry_time = (data.get("entry_time") or "").strip()
    exit_time = (data.get("exit_time") or "").strip()
    status_override = data.get("status")
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)
    if not subject:
        subject = db.get_setting("active_subject", config.DEFAULT_SUBJECT)

    if not db.get_student_info(student_id):
        return _json_error("student not registered", 404)

    try:
        entry_dt = datetime.strptime(entry_time, config.REPORT_DATETIME_FORMAT)
        exit_dt = datetime.strptime(exit_time, config.REPORT_DATETIME_FORMAT)
    except ValueError as exc:
        raise ValidationError(
            f"entry_time and exit_time must match {config.REPORT_DATETIME_FORMAT}"
        ) from exc

    if exit_dt < entry_dt:
        raise ValidationError("exit_time cannot be earlier than entry_time")

    duration = int((exit_dt - entry_dt).total_seconds() / 60)
    # Use dynamic minimum duration from settings for status determination
    if status_override:
        status = validate_status(status_override)
    else:
        attendance_mgr.minimum_duration = _get_minimum_duration()
        status = attendance_mgr.determine_status(duration)
    date = entry_dt.strftime(config.REPORT_DATE_FORMAT)

    saved = db.upsert_attendance(
        student_id=student_id,
        name=name,
        entry_time=entry_time,
        exit_time=exit_time,
        duration=duration,
        status=status,
        date=date,
        subject=subject,
    )
    if not saved:
        return _json_error("failed to save manual attendance", 500)

    return jsonify(
        {
            "success": True,
            "message": "manual attendance saved",
            "student_id": student_id,
            "student_name": name,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "duration_minutes": duration,
            "attendance_status": status,
            "date": date,
            "subject": subject,
        }
    )


@app.route("/api/recent-entries")
def recent_entries():
    return jsonify({"success": True, "entries": _recent_entries_payload()})


@app.route("/api/recent-exits")
def recent_exits():
    return jsonify({"success": True, "exits": _recent_exits_payload()})


@app.route("/api/inside-students")
def inside_students():
    limit, _ = parse_limit_offset(request.args.get("limit"), 0)
    return jsonify({"success": True, "inside": _inside_payload(limit=limit)})


@app.route("/api/analytics")
def analytics():
    from_date = validate_date(request.args.get("from_date"), "from_date")
    to_date = validate_date(request.args.get("to_date"), "to_date")
    return jsonify({"success": True, "analytics": db.get_analytics(from_date, to_date)})


@app.route("/api/get-students")
def get_students():
    return jsonify({"success": True, "students": _student_payload()})


@app.route("/api/get-today-attendance")
def get_today_attendance():
    today = datetime.now().strftime(config.REPORT_DATE_FORMAT)
    records = db.get_attendance_by_date(today)
    return jsonify({"success": True, "attendance": _attendance_payload(records)})


@app.route("/api/check-stale-entries")
def check_stale_entries():
    """Check for stale entries (students still marked INSIDE after 24 hours)."""
    max_age_hours = int(request.args.get("max_age_hours", 24))
    student_id = request.args.get("student_id")
    
    stale_entries = db.get_stale_entries(student_id=student_id, max_age_hours=max_age_hours)
    
    return jsonify({
        "success": True,
        "stale_count": len(stale_entries),
        "stale_entries": stale_entries,
        "warning": "These entries may need manual cleanup" if stale_entries else None
    })


@app.route("/api/cleanup-stale-entries", methods=["POST"])
def cleanup_stale_entries():
    """Automatically cleanup stale entries (admin function)."""
    data = _json_body()
    max_age_hours = int(data.get("max_age_hours", 24))
    mark_as_absent = data.get("mark_as_absent", True)
    
    cleaned_count = db.auto_cleanup_stale_entries(
        max_age_hours=max_age_hours,
        mark_as_absent=mark_as_absent
    )
    
    logger.info(f"Stale entries cleanup: {cleaned_count} entries processed")
    
    return jsonify({
        "success": True,
        "message": f"Cleaned up {cleaned_count} stale entries",
        "cleaned_count": cleaned_count
    })



@app.route("/api/get-attendance")
def get_attendance():
    date = validate_date(request.args.get("date"), "date")
    student_id = request.args.get("student_id")
    if student_id:
        student_id = validate_student_id(student_id)

    status = request.args.get("status")
    if status:
        status = validate_status(status)

    subject = validate_subject(request.args.get("subject"), "subject", allow_empty=True)

    limit, offset = parse_limit_offset(request.args.get("limit"), request.args.get("offset"))
    records, total = db.get_attendance_filtered(
        date=date,
        student_id=student_id,
        status=status,
        subject=subject,
        limit=limit,
        offset=offset,
    )

    return jsonify(
        {
            "success": True,
            "records": _attendance_payload(records),
            "total": total,
            "limit": limit,
            "offset": offset,
            "subject": subject,
        }
    )


@app.route("/api/student-attendance")
def api_student_attendance():
    student_id = validate_student_id(request.args.get("student_id"))
    subject = validate_subject(request.args.get("subject"), "subject", allow_empty=True)
    limit, _ = parse_limit_offset(request.args.get("limit"), 0)

    student = db.get_student_info(student_id)
    if not student:
        return _json_error("student not registered", 404)

    records = db.get_student_subject_records(
        student_id=student_id,
        subject=subject,
        limit=limit,
    )
    summary = db.get_student_subject_summary(student_id)

    return jsonify(
        {
            "success": True,
            "student": {
                "student_id": student[0],
                "name": student[1],
                "roll_number": student[2],
                "registered_date": student[3],
            },
            "subject": subject,
            "subject_summary": summary,
            "records": _attendance_payload(records),
        }
    )


@app.route("/api/generate-report", methods=["POST"])
def api_generate_report():
    data = _json_body()
    report_type = (data.get("type") or "daily").strip().lower()
    date = validate_date(data.get("date"), "date")
    subject = validate_subject(data.get("subject"), "subject", allow_empty=True)

    if report_type == "daily":
        report_path = report_gen.generate_daily_report(date, subject=subject)
    elif report_type == "csv":
        report_path = report_gen.generate_csv_report(date, subject=subject)
    else:
        raise ValidationError("type must be 'daily' or 'csv'")

    file_name = os.path.basename(report_path)
    return jsonify(
        {
            "success": True,
            "message": "report generated successfully",
            "path": report_path,
            "file_name": file_name,
            "subject": subject,
        }
    )


@app.route("/api/download-report")
def download_report():
    file_name = (request.args.get("file") or "").strip()
    if not file_name:
        raise ValidationError("missing file parameter")

    safe_name = os.path.basename(file_name)
    full_path = os.path.join(config.REPORTS_PATH, safe_name)
    if not os.path.exists(full_path):
        return _json_error("report file not found", 404)

    return send_from_directory(config.REPORTS_PATH, safe_name, as_attachment=True)


# Admin routes
@app.route("/admin")
def admin_page():
    """Admin dashboard for managing students."""
    return render_template("admin.html")


@app.route("/api/admin/students")
def api_admin_students():
    """Get all students with complete information for admin view."""
    students = db.get_all_students()
    result = []
    for student in students:
        student_id = student[0]
        # Get attendance stats for each student
        summary = db.get_student_subject_summary(student_id)
        total_classes = sum(s["total_classes"] for s in summary)
        present_classes = sum(s["present_classes"] for s in summary)
        overall_rate = round((present_classes / total_classes) * 100, 2) if total_classes else 0.0
        
        result.append({
            "student_id": student[0],
            "name": student[1],
            "roll_number": student[2],
            "registered_date": student[3],
            "total_classes": total_classes,
            "attendance_rate": overall_rate
        })
    
    return jsonify({"success": True, "students": result})


@app.route("/api/admin/delete-student", methods=["POST"])
def api_admin_delete_student():
    """Delete a student and all their data (encodings, images, database records)."""
    data = _json_body()
    student_id = validate_student_id(data.get("student_id"))
    
    # Check if student exists
    student = db.get_student_info(student_id)
    if not student:
        return _json_error("student not found", 404)
    
    # Delete from database
    if not db.delete_student(student_id):
        return _json_error("failed to delete student from database", 500)
    
    # Delete student's dataset folder
    try:
        dataset_folder = _safe_dataset_folder(student_id)
        if os.path.exists(dataset_folder):
            import shutil
            shutil.rmtree(dataset_folder)
            logger.info(f"Deleted dataset folder for student: {student_id}")
    except Exception as e:
        logger.error(f"Error deleting dataset folder for {student_id}: {e}")
        # Continue anyway, database deletion is more important
    
    # Remove student's encodings efficiently (no re-encoding needed)
    try:
        encoder = FaceEncoder()
        encoder.remove_student_encodings(student_id)
        recognizer.load_encodings(force=True)
        logger.info(f"Removed encodings for {student_id} - no re-encoding needed")
    except Exception as e:
        logger.error(f"Error removing encodings for {student_id}: {e}")
        # Continue anyway, the student is already deleted from database
    
    return jsonify({
        "success": True,
        "message": f"Student {student_id} deleted successfully",
        "student_name": student[1]
    })


def startup_cleanup():
    """Run cleanup tasks on application startup."""
    try:
        # Clean up stale entries from previous days
        cleaned = db.auto_cleanup_stale_entries(max_age_hours=24, mark_as_absent=True)
        if cleaned > 0:
            logger.info(f"Startup cleanup: Processed {cleaned} stale entries")
    except Exception as e:
        logger.error(f"Startup cleanup failed: {e}")


if __name__ == "__main__":
    try:
        os.makedirs(config.DATASET_PATH, exist_ok=True)
        os.makedirs(config.ENCODINGS_PATH, exist_ok=True)
        os.makedirs(config.DATABASE_PATH, exist_ok=True)
        os.makedirs(config.LOGS_PATH, exist_ok=True)
        os.makedirs(config.REPORTS_PATH, exist_ok=True)

        # Run startup cleanup (with error handling)
        try:
            startup_cleanup()
        except Exception as e:
            logger.error(f"Startup cleanup failed (continuing anyway): {e}")

        logger.info("="*60)
        logger.info("Smart Attendance System - Server Starting")
        logger.info("="*60)
        logger.info(f"Host: {config.FLASK_HOST}")
        logger.info(f"Port: {config.FLASK_PORT}")
        logger.info(f"Debug: {config.FLASK_DEBUG}")
        logger.info(f"Concurrent requests: Enabled (threaded=True)")
        logger.info("="*60)

        # Enable threaded mode for concurrent request handling
        # This allows multiple students to mark entry/exit simultaneously
        app.run(
            debug=config.FLASK_DEBUG, 
            host=config.FLASK_HOST, 
            port=config.FLASK_PORT,
            threaded=True,  # Enable multi-threading for concurrent requests
            use_reloader=False  # Disable reloader to prevent double cleanup
        )
    except Exception as e:
        logger.critical(f"Server failed to start: {e}", exc_info=True)
        raise

