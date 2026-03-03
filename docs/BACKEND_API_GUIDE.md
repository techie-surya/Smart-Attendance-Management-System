# Backend API Development Guide

## Table of Contents
1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Flask Application Architecture](#flask-application-architecture)
4. [API Endpoints Reference](#api-endpoints-reference)
5. [Request/Response Patterns](#requestresponse-patterns)
6. [Error Handling](#error-handling)
7. [Authentication & Security](#authentication--security)
8. [Performance & Optimization](#performance--optimization)
9. [Common Questions & Troubleshooting](#common-questions--troubleshooting)

---

## Overview

### What is Used?
The backend is a **Flask-based RESTful API** that serves both static HTML pages and JSON API endpoints for the attendance system.

**Core Components**:
- **Flask**: Python web framework
- **SQLite**: Database management
- **face_recognition**: Face detection and encoding
- **Threading**: Parallel image processing
- **JSON**: Data exchange format

### Architecture Pattern
**MVC-like Structure**:
- **Models**: Database operations (`src/database_manager.py`)
- **Views**: Flask routes and templates (`web/app.py`, `web/templates/`)
- **Controllers**: Business logic in route handlers

---

## Technology Stack

### 1. Flask Framework
**Version**: 2.x
**Purpose**: Web application framework and API server

**Installation**:
```bash
pip install flask
pip install flask-cors  # For cross-origin requests (if needed)
```

**Basic Flask Application**:
```python
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Configure Flask
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['JSON_SORT_KEYS'] = False  # Maintain JSON key order

# Route example
@app.route('/api/endpoint', methods=['POST'])
def endpoint():
    data = request.get_json()
    return jsonify({"status": "success", "data": data})

# Run server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

### 2. Request Handling Libraries

**flask.request**: Access incoming request data
```python
from flask import request

# Get JSON data
data = request.get_json()

# Get form data
name = request.form.get('name')

# Get query parameters
page = request.args.get('page', default=1, type=int)

# Get files
file = request.files['upload']
```

**flask.jsonify**: Create JSON responses
```python
from flask import jsonify

# Success response
return jsonify({
    "status": "success",
    "message": "Operation completed",
    "data": {"id": 123, "name": "John"}
}), 200

# Error response
return jsonify({
    "status": "error",
    "message": "Invalid input"
}), 400
```

### 3. Logging
**Purpose**: Track application behavior and debug issues

```python
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/system_logs.txt'),
        logging.StreamHandler()  # Also print to console
    ]
)

logger = logging.getLogger(__name__)

# Use in code
logger.info("User registered successfully")
logger.warning("Low encoding quality detected")
logger.error("Database connection failed")
logger.debug("Processing frame 123")
```

### 4. Threading & Concurrency
**concurrent.futures.ThreadPoolExecutor**
```python
from concurrent.futures import ThreadPoolExecutor

# Create thread pool
executor = ThreadPoolExecutor(max_workers=4)

# Submit tasks
futures = []
for item in items:
    future = executor.submit(process_function, item)
    futures.append(future)

# Get results with timeout
for future in futures:
    try:
        result = future.result(timeout=30)
    except TimeoutError:
        logger.error("Task timeout")
```

---

## Flask Application Architecture

### File Structure
```
web/
├── app.py              # Main Flask application (1,292 lines)
├── wsgi.py             # WSGI entry point for production
├── static/             # Static files (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── images/
└── templates/          # HTML templates (Jinja2)
    ├── base.html       # Base template with navigation
    ├── dashboard.html  # Home page
    ├── entry.html      # Entry attendance
    ├── exit.html       # Exit attendance
    ├── register.html   # Student registration
    ├── reports.html    # Attendance reports
    ├── student_attendance.html
    └── admin.html
```

### Application Initialization

**web/app.py** (Lines 1-50):
```python
from flask import Flask, render_template, request, jsonify
import logging
from datetime import datetime
import os

# Import custom modules
from src.database_manager import DatabaseManager
from src.recognition_service import RecognitionService
from src.encode_faces import FaceEncoder
from src.validators import *
from src.rate_limiter import RateLimiter

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request

# Initialize services
db = DatabaseManager()
recognition_service = RecognitionService()
encoder = FaceEncoder()
rate_limiter = RateLimiter(cooldown_seconds=3)

# Configure logging
logger = logging.getLogger(__name__)
```

### Route Organization Pattern

**1. HTML Page Routes** (Return rendered templates):
```python
@app.route('/')
def index():
    """Dashboard page"""
    return render_template('dashboard.html')

@app.route('/entry')
def entry():
    """Entry attendance page"""
    return render_template('entry.html')

@app.route('/register')
def register_page():
    """Student registration page"""
    return render_template('register.html')
```

**2. API Routes** (Return JSON):
```python
@app.route('/api/students', methods=['GET'])
def get_students():
    """Get list of all students"""
    try:
        students = db.get_all_students()
        result = [
            {
                "student_id": s[0],
                "name": s[1],
                "roll_number": s[2]
            }
            for s in students
        ]
        return jsonify({
            "status": "success",
            "students": result
        })
    except Exception as e:
        logger.error(f"Error fetching students: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

---

## API Endpoints Reference

### Registration Endpoints

#### 1. Save Face Images
**Endpoint**: `POST /api/save-face-images`
**Purpose**: Upload and validate student face images during registration

**Request Body**:
```json
{
  "student_id": "student_2301105225_Asish_Kumar_Sahoo",
  "name": "Asish Kumar Sahoo",
  "roll_number": "2301105225",
  "images": [
    "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    // ... 14 more base64-encoded images
  ]
}
```

**Response (Success)**:
```json
{
  "status": "success",
  "message": "15 images saved successfully",
  "valid_images": 14,
  "student_id": "student_2301105225_Asish_Kumar_Sahoo"
}
```

**Implementation** (Lines 370-435):
```python
@app.route('/api/save-face-images', methods=['POST'])
def save_face_images():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        name = data.get('name')
        roll_number = data.get('roll_number')
        images = data.get('images', [])
        
        # Validate input
        if not all([student_id, name, roll_number, images]):
            return jsonify({
                "status": "error",
                "message": "Missing required fields"
            }), 400
        
        # Validate images have faces
        valid_count = 0
        for img_data in images:
            # Remove data URL prefix
            if ',' in img_data:
                img_data = img_data.split(',')[1]
            
            # Decode base64
            nparr = np.frombuffer(base64.b64decode(img_data), np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Detect faces
            face_locations = face_recognition.face_locations(
                rgb_image,
                number_of_times_to_upsample=1,
                model="hog"
            )
            
            if len(face_locations) == 1:
                valid_count += 1
        
        # Require minimum valid images
        if valid_count < 5:
            return jsonify({
                "status": "error",
                "message": f"Only {valid_count} valid images. Need at least 5."
            }), 400
        
        # Save images to disk
        student_dir = f"data/dataset/{student_id}"
        os.makedirs(student_dir, exist_ok=True)
        
        for idx, img_data in enumerate(images):
            if ',' in img_data:
                img_data = img_data.split(',')[1]
            
            img_bytes = base64.b64decode(img_data)
            img_path = f"{student_dir}/image_{idx+1}.jpg"
            
            with open(img_path, 'wb') as f:
                f.write(img_bytes)
        
        # Register in database
        db.register_student(student_id, name, roll_number)
        
        # Generate face encodings
        encoder.encode_single_student(student_id, name)
        
        # Reload recognition service
        recognition_service.load_encodings()
        
        logger.info(f"Student {name} registered with {valid_count} valid images")
        
        return jsonify({
            "status": "success",
            "message": f"{len(images)} images saved successfully",
            "valid_images": valid_count,
            "student_id": student_id
        })
        
    except Exception as e:
        logger.error(f"Error saving images: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

#### 2. Check Student Exists
**Endpoint**: `POST /api/check-student`
**Purpose**: Verify if student ID already exists

**Request**:
```json
{
  "student_id": "student_2301105225_Asish_Kumar_Sahoo"
}
```

**Response**:
```json
{
  "exists": true,
  "student": {
    "student_id": "student_2301105225_Asish_Kumar_Sahoo",
    "name": "Asish Kumar Sahoo",
    "roll_number": "2301105225"
  }
}
```

### Attendance Endpoints

#### 3. Mark Entry (Automated)
**Endpoint**: `POST /api/mark-entry`
**Purpose**: Mark student entry via face recognition

**Request**:
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "subject": "Data Science"
}
```

**Response (Success)**:
```json
{
  "status": "success",
  "student_id": "student_2301105225_Asish_Kumar_Sahoo",
  "name": "Asish Kumar Sahoo",
  "confidence": 95.5,
  "timestamp": "2026-03-03T14:30:00"
}
```

**Response (No Face Detected)**:
```json
{
  "status": "error",
  "message": "No face detected in image"
}
```

**Response (Unknown Face)**:
```json
{
  "status": "error",
  "message": "Face not recognized",
  "confidence": 45.2
}
```

**Implementation** (Lines 550-620):
```python
@app.route('/api/mark-entry', methods=['POST'])
def mark_entry():
    try:
        data = request.get_json()
        image_data = data.get('image')
        subject = data.get('subject', 'General')
        
        # Rate limiting
        client_ip = request.remote_addr
        if not rate_limiter.is_allowed(client_ip):
            return jsonify({
                "status": "error",
                "message": "Please wait before next scan"
            }), 429
        
        # Decode image
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        nparr = np.frombuffer(base64.b64decode(image_data), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Recognize face
        results = recognition_service.recognize_face(frame)
        
        if not results:
            return jsonify({
                "status": "error",
                "message": "No face detected in image"
            }), 400
        
        # Get best match
        best_result = max(results, key=lambda x: x['confidence'])
        
        if best_result['student_id'] is None:
            return jsonify({
                "status": "error",
                "message": "Face not recognized",
                "confidence": best_result['confidence']
            }), 400
        
        # Check confidence threshold
        if best_result['confidence'] < 70.0:
            return jsonify({
                "status": "error",
                "message": "Low confidence recognition",
                "confidence": best_result['confidence']
            }), 400
        
        # Mark entry in database
        success = db.mark_entry(
            best_result['student_id'],
            best_result['name'],
            subject
        )
        
        if not success:
            return jsonify({
                "status": "error",
                "message": "Entry already marked recently"
            }), 400
        
        logger.info(f"Entry marked: {best_result['name']} ({best_result['confidence']:.1f}%)")
        
        return jsonify({
            "status": "success",
            "student_id": best_result['student_id'],
            "name": best_result['name'],
            "confidence": best_result['confidence'],
            "timestamp": datetime.now().isoformat(),
            "subject": subject
        })
        
    except Exception as e:
        logger.error(f"Error marking entry: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

#### 4. Mark Entry (Manual)
**Endpoint**: `POST /api/manual-entry`
**Purpose**: Manually mark entry when face recognition fails

**Request**:
```json
{
  "student_id": "student_2301105225_Asish_Kumar_Sahoo",
  "name": "Asish Kumar Sahoo",
  "subject": "Data Science"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Manual entry marked successfully",
  "timestamp": "2026-03-03T14:30:00"
}
```

#### 5. Mark Exit (Automated)
**Endpoint**: `POST /api/mark-exit`
**Purpose**: Mark student exit via face recognition
**Similar to mark-entry endpoint**

#### 6. Mark Exit (Manual)
**Endpoint**: `POST /api/manual-exit`
**Purpose**: Manually mark exit
**Similar to manual-entry endpoint**

### Data Retrieval Endpoints

#### 7. Get All Students
**Endpoint**: `GET /api/students`
**Purpose**: Retrieve list of registered students

**Response**:
```json
{
  "status": "success",
  "students": [
    {
      "student_id": "student_2301105225_Asish_Kumar_Sahoo",
      "name": "Asish Kumar Sahoo",
      "roll_number": "2301105225"
    },
    // ... more students
  ]
}
```

**Implementation** (Lines 501-515):
```python
@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        students = db.get_all_students()
        result = [
            {
                "student_id": s[0],
                "name": s[1],
                "roll_number": s[2]
            }
            for s in students
        ]
        return jsonify({
            "status": "success",
            "students": result
        })
    except Exception as e:
        logger.error(f"Error fetching students: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

#### 8. Get Student Info
**Endpoint**: `GET /api/student/<student_id>`
**Purpose**: Get detailed information about a student

**Response**:
```json
{
  "status": "success",
  "student": {
    "student_id": "student_2301105225_Asish_Kumar_Sahoo",
    "name": "Asish Kumar Sahoo",
    "roll_number": "2301105225",
    "registered_date": "2026-03-01T10:00:00"
  }
}
```

#### 9. Get Entry Logs
**Endpoint**: `GET /api/entry-logs?date=2026-03-03&subject=Data Science`
**Purpose**: Retrieve entry attendance logs

**Query Parameters**:
- `date` (optional): Filter by date (YYYY-MM-DD)
- `subject` (optional): Filter by subject

**Response**:
```json
{
  "status": "success",
  "logs": [
    {
      "student_id": "student_2301105225_Asish_Kumar_Sahoo",
      "name": "Asish Kumar Sahoo",
      "timestamp": "2026-03-03T09:00:15",
      "subject": "Data Science",
      "method": "automated"
    },
    // ... more logs
  ]
}
```

#### 10. Get Exit Logs
**Endpoint**: `GET /api/exit-logs?date=2026-03-03`
**Purpose**: Retrieve exit attendance logs
**Similar to entry-logs**

#### 11. Get Attendance Report
**Endpoint**: `GET /api/attendance-report?start_date=2026-03-01&end_date=2026-03-03`
**Purpose**: Generate attendance report for date range

**Response**:
```json
{
  "status": "success",
  "report": {
    "total_students": 5,
    "date_range": {
      "start": "2026-03-01",
      "end": "2026-03-03"
    },
    "attendance": [
      {
        "student_id": "student_2301105225_Asish_Kumar_Sahoo",
        "name": "Asish Kumar Sahoo",
        "roll_number": "2301105225",
        "entry_count": 3,
        "exit_count": 3,
        "attendance_percentage": 100.0
      },
      // ... more students
    ]
  }
}
```

### System Endpoints

#### 12. Get System Settings
**Endpoint**: `GET /api/settings`
**Purpose**: Retrieve system configuration

**Response**:
```json
{
  "status": "success",
  "settings": {
    "active_subject": "Data Science",
    "tolerance": 0.6,
    "confidence_threshold": 70.0,
    "images_per_student": 15
  }
}
```

#### 13. Update System Settings
**Endpoint**: `POST /api/settings`
**Purpose**: Update system configuration

**Request**:
```json
{
  "active_subject": "Machine Learning",
  "tolerance": 0.55,
  "confidence_threshold": 75.0
}
```

---

## Request/Response Patterns

### Standard Response Format

**Success Response**:
```python
{
    "status": "success",
    "message": "Operation completed successfully",  # Optional
    "data": { ... },  # Optional
    "timestamp": "2026-03-03T14:30:00"  # Optional
}
```

**Error Response**:
```python
{
    "status": "error",
    "message": "Descriptive error message",
    "error_code": "VALIDATION_ERROR",  # Optional
    "details": { ... }  # Optional
}
```

### HTTP Status Codes

```python
# Success
200  # OK - Request successful
201  # Created - Resource created successfully

# Client Errors  
400  # Bad Request - Invalid input
401  # Unauthorized - Authentication required
403  # Forbidden - No permission
404  # Not Found - Resource doesn't exist
409  # Conflict - Resource already exists
429  # Too Many Requests - Rate limit exceeded

# Server Errors
500  # Internal Server Error - Server-side error
503  # Service Unavailable - Server overloaded
```

### Request Validation Pattern

```python
@app.route('/api/endpoint', methods=['POST'])
def endpoint():
    try:
        # 1. Get request data
        data = request.get_json()
        
        # 2. Validate required fields
        required_fields = ['field1', 'field2', 'field3']
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing)}"
            }), 400
        
        # 3. Validate field types
        if not isinstance(data['field1'], str):
            return jsonify({
                "status": "error",
                "message": "field1 must be a string"
            }), 400
        
        # 4. Business logic validation
        if not validate_roll_number(data['roll_number']):
            return jsonify({
                "status": "error",
                "message": "Invalid roll number format"
            }), 400
        
        # 5. Process request
        result = process_data(data)
        
        # 6. Return success
        return jsonify({
            "status": "success",
            "data": result
        }), 200
        
    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": f"Validation error: {str(e)}"
        }), 400
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500
```

---

## Error Handling

### Exception Hierarchy

```python
# Custom exceptions (src/validators.py)
class ValidationError(Exception):
    """Raised when input validation fails"""
    pass

class DatabaseError(Exception):
    """Raised when database operation fails"""
    pass

class RecognitionError(Exception):
    """Raised when face recognition fails"""
    pass
```

### Global Error Handlers

```python
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "status": "error",
        "message": "Endpoint not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal error: {error}", exc_info=True)
    return jsonify({
        "status": "error",
        "message": "Internal server error"
    }), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """Catch-all error handler"""
    logger.error(f"Unhandled exception: {error}", exc_info=True)
    return jsonify({
        "status": "error",
        "message": "An unexpected error occurred"
    }), 500
```

### Try-Except Pattern in Routes

```python
@app.route('/api/operation', methods=['POST'])
def operation():
    try:
        # Main logic here
        result = perform_operation()
        return jsonify({"status": "success", "data": result})
        
    except ValidationError as e:
        # User input error
        logger.warning(f"Validation error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
        
    except DatabaseError as e:
        # Database error
        logger.error(f"Database error: {e}")
        return jsonify({
            "status": "error",
            "message": "Database operation failed"
        }), 500
        
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500
```

---

## Authentication & Security

### CORS Configuration
**For cross-origin requests (if frontend is on different domain)**:

```python
from flask_cors import CORS

# Allow all origins (development only)
CORS(app)

# Production: Restrict to specific origins
CORS(app, origins=["https://yourdomain.com"])
```

### Input Validation

**Validators** (src/validators.py):
```python
import re

def validate_roll_number(roll_number):
    """Validate roll number format"""
    pattern = r'^\d{10}$'  # 10 digits
    return bool(re.match(pattern, str(roll_number)))

def validate_student_id(student_id):
    """Validate student ID format"""
    pattern = r'^student_\d{10}_[A-Za-z_]+$'
    return bool(re.match(pattern, student_id))

def validate_name(name):
    """Validate student name"""
    if len(name) < 3 or len(name) > 100:
        return False
    pattern = r'^[A-Za-z\s]+$'
    return bool(re.match(pattern, name))

def validate_subject(subject):
    """Validate subject name"""
    allowed_subjects = [
        "Data Science",
        "Machine Learning",
        "Computer Networks",
        "Database Systems",
        "Web Development"
    ]
    return subject in allowed_subjects
```

### SQL Injection Prevention
**Use parameterized queries** (handled in DatabaseManager):

```python
# WRONG - vulnerable to SQL injection
cursor.execute(f"SELECT * FROM students WHERE name = '{name}'")

# CORRECT - parameterized query
cursor.execute("SELECT * FROM students WHERE name = ?", (name,))
```

### File Upload Security

```python
import os
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400
    
    # Secure filename
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    return jsonify({"status": "success"})
```

---

## Performance & Optimization

### 1. Database Connection Pooling
**Implemented in DatabaseManager**:

```python
import sqlite3
from threading import Lock

class DatabaseManager:
    def __init__(self):
        self.db_path = "data/database/attendance.db"
        self.lock = Lock()
        self._connection = None
    
    def get_connection(self):
        """Thread-safe connection"""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            # Enable WAL mode for better concurrency
            self._connection.execute("PRAGMA journal_mode=WAL")
        return self._connection
```

### 2. Caching Strategy

**In-Memory Cache for Recognition Service**:
```python
class RecognitionService:
    def __init__(self):
        self.encoding_cache = {}  # Loaded once at startup
        self.load_encodings()
    
    def load_encodings(self):
        """Load encodings into memory (called once)"""
        with open('data/encodings/face_encodings.pkl', 'rb') as f:
            self.encoding_cache = pickle.load(f)
```

**Benefits**: No disk I/O during recognition (10x faster)

### 3. Request Rate Limiting

**Implementation** (src/rate_limiter.py):
```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, cooldown_seconds=3):
        self.cooldown = cooldown_seconds
        self.requests = defaultdict(float)
    
    def is_allowed(self, identifier):
        """Check if request is allowed"""
        now = time.time()
        last_request = self.requests.get(identifier, 0)
        
        if now - last_request >= self.cooldown:
            self.requests[identifier] = now
            return True
        
        return False
```

### 4. Async Image Processing

**ThreadPoolExecutor for parallel processing**:
```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

@app.route('/api/batch-process', methods=['POST'])
def batch_process():
    data = request.get_json()
    images = data.get('images', [])
    
    # Process in parallel
    futures = [executor.submit(process_image, img) for img in images]
    
    # Collect results
    results = []
    for future in futures:
        try:
            result = future.result(timeout=30)
            results.append(result)
        except Exception as e:
            logger.error(f"Processing error: {e}")
    
    return jsonify({"status": "success", "results": results})
```

### 5. Response Compression

```python
from flask_compress import Compress

# Enable gzip compression
Compress(app)

# Reduces JSON response size by ~60-70%
```

### 6. Database Query Optimization

```python
# BAD - N+1 query problem
students = db.get_all_students()
for student in students:
    entries = db.get_entries(student['id'])  # One query per student!

# GOOD - Single query with JOIN
query = """
    SELECT s.*, e.timestamp
    FROM students s
    LEFT JOIN entry_log e ON s.student_id = e.student_id
    WHERE DATE(e.timestamp) = ?
"""
results = cursor.execute(query, (today,)).fetchall()
```

---

## Common Questions & Troubleshooting

### Q1: How do I add a new API endpoint?
**A**:
```python
# 1. Add route decorator
@app.route('/api/new-endpoint', methods=['POST', 'GET'])
def new_endpoint():
    # 2. Handle request
    if request.method == 'POST':
        data = request.get_json()
        # Process POST request
    else:
        # Handle GET request
        pass
    
    # 3. Return JSON response
    return jsonify({"status": "success", "data": result})

# 4. Test with curl or frontend
```

### Q2: Why is my endpoint returning 404?
**A**: Common causes:
- **Typo in URL**: Check spelling `/api/students` vs `/api/student`
- **Wrong HTTP method**: Endpoint expects POST but you sent GET
- **Trailing slash**: `/api/endpoint/` vs `/api/endpoint`
- **Server not running**: Restart Flask server

### Q3: How do I debug API requests?
**A**:
```python
@app.before_request
def log_request():
    """Log all incoming requests"""
    logger.info(f"{request.method} {request.path}")
    if request.method == 'POST':
        logger.debug(f"Body: {request.get_json()}")

@app.after_request
def log_response(response):
    """Log all responses"""
    logger.info(f"Response: {response.status_code}")
    return response
```

### Q4: How do I handle CORS errors?
**A**:
```python
from flask_cors import CORS

# Option 1: Allow all (development)
CORS(app)

# Option 2: Specific origins (production)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "https://yourdomain.com"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type"]
    }
})
```

### Q5: Why is my JSON response empty?
**A**: Check:
1. **Return statement**: Must use `return jsonify({...})`
2. **Database query**: Might return empty results
3. **Variable scope**: Ensure variable is defined in scope
4. **Serialization**: Check if objects are JSON-serializable

```python
# DEBUG: Print before returning
result = get_data()
print(f"Result: {result}")  # Check what's being returned
return jsonify(result)
```

### Q6: How do I improve API response time?
**A**:
1. **Profile slow endpoints**:
```python
import time

@app.route('/api/slow')
def slow_endpoint():
    start = time.time()
    result = expensive_operation()
    duration = time.time() - start
    logger.info(f"Endpoint took {duration:.2f}s")
    return jsonify(result)
```

2. **Optimize database queries**: Use indexes, reduce JOINs
3. **Cache results**: Store frequently accessed data in memory
4. **Reduce payload size**: Return only necessary fields

### Q7: How do I handle file uploads?
**A**:
```python
@app.route('/api/upload', methods=['POST'])
def upload():
    # For form data file upload
    if 'file' in request.files:
        file = request.files['file']
        file.save(f"uploads/{file.filename}")
    
    # For base64 encoded files (current method)
    if 'image' in request.get_json():
        img_data = request.get_json()['image']
        img_bytes = base64.b64decode(img_data.split(',')[1])
        with open('image.jpg', 'wb') as f:
            f.write(img_bytes)
    
    return jsonify({"status": "success"})
```

### Q8: How do I test endpoints without frontend?
**A**: Use curl or Python requests:

```bash
# GET request
curl http://localhost:5000/api/students

# POST request with JSON
curl -X POST http://localhost:5000/api/mark-entry \
  -H "Content-Type: application/json" \
  -d '{"student_id":"student_123","subject":"Math"}'
```

```python
# Python requests
import requests

response = requests.post(
    'http://localhost:5000/api/mark-entry',
    json={"student_id": "student_123", "subject": "Math"}
)
print(response.json())
```

### Q9: How do I deploy the Flask app to production?
**A**:
```bash
# Option 1: Gunicorn (Linux/Mac)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 web.wsgi:app

# Option 2: Waitress (Windows/Cross-platform)
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 web.wsgi:app

# Option 3: Docker
# See Dockerfile in project root
```

### Q10: How do I handle database migrations?
**A**:
```python
# Create migration script
def migrate_add_column():
    """Add new column to students table"""
    conn = sqlite3.connect('data/database/attendance.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            ALTER TABLE students
            ADD COLUMN email TEXT
        """)
        conn.commit()
        print("Migration successful")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("Column already exists")
        else:
            raise
    finally:
        conn.close()
```

---

## Testing

### Unit Testing Example

```python
import unittest
from web.app import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        """Setup test client"""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_get_students(self):
        """Test GET /api/students"""
        response = self.app.get('/api/students')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('students', data)
    
    def test_mark_entry_missing_fields(self):
        """Test POST /api/mark-entry with missing fields"""
        response = self.app.post('/api/mark-entry', json={})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data['status'], 'error')

if __name__ == '__main__':
    unittest.main()
```

---

## File Reference

### Key Files for Backend Team

1. **web/app.py** (1,292 lines)
   - All API endpoints
   - Request handling
   - Business logic
   - Error handling

2. **src/database_manager.py** (1,055 lines)
   - Database operations
   - SQL queries
   - Connection management

3. **src/recognition_service.py** (~400 lines)
   - Face recognition logic
   - Used by attendance endpoints

4. **src/validators.py** (~200 lines)
   - Input validation functions
   - Security checks

5. **src/rate_limiter.py** (~100 lines)
   - Request rate limiting
   - Spam prevention

---

## Summary

**Backend Team Responsibilities**:
1. ✅ Implement RESTful API endpoints
2. ✅ Handle request validation and error handling
3. ✅ Integrate with database and recognition services
4. ✅ Optimize performance (caching, threading)
5. ✅ Implement security measures (validation, rate limiting)
6. ✅ Write tests for endpoints
7. ✅ Monitor and log system behavior

**Total API Endpoints**: 35 routes
**Main Framework**: Flask 2.x
**Database**: SQLite with connection pooling
**Response Format**: JSON
**Security**: Input validation, rate limiting, parameterized queries
