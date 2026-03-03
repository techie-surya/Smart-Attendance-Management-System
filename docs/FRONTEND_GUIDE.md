# Frontend Development Guide
## Smart Attendance System - Complete Frontend Architecture

---

## 📋 Table of Contents
1. [Technology Stack Overview](#technology-stack-overview)
2. [Architecture & Design Principles](#architecture--design-principles)
3. [Core Technologies Explained](#core-technologies-explained)
4. [Implementation Details](#implementation-details)
5. [File Structure & Responsibilities](#file-structure--responsibilities)
6. [API Integration Patterns](#api-integration-patterns)
7. [Common Workflows](#common-workflows)
8. [Troubleshooting & Best Practices](#troubleshooting--best-practices)
9. [FAQs for Frontend Developers](#faqs-for-frontend-developers)

---

## 🛠️ Technology Stack Overview

### Core Technologies
- **HTML5**: Template structure with Jinja2 syntax
- **CSS3**: Responsive styling with Flexbox/Grid
- **Vanilla JavaScript (ES6+)**: No frameworks, pure JS for maximum performance
- **WebRTC (getUserMedia API)**: Real-time camera access
- **Flask Jinja2**: Server-side template rendering
- **Bootstrap 5**: UI component framework (via CDN)

### Why These Technologies?

**Why Vanilla JavaScript over React/Vue/Angular?**
- **Performance**: No framework overhead, faster page loads
- **Simplicity**: Direct DOM manipulation for real-time video processing
- **Browser Compatibility**: Better control over WebRTC APIs
- **Learning Curve**: Easier for team members to understand and modify

**Why WebRTC?**
- **Native Browser Support**: No plugins required
- **Low Latency**: Direct camera access without server streaming
- **Security**: HTTPS enforcement for production safety

---

## 🏗️ Architecture & Design Principles

### 1. **Separation of Concerns**
```
Templates (HTML) → Structure & Layout
CSS Files       → Styling & Responsiveness  
JS Files        → Behavior & Interactivity
API Layer       → Data Management
```

### 2. **Module Pattern**
Each JavaScript file follows a modular approach:
```javascript
// Encapsulated state
let videoStream = null;
let isCapturing = false;

// Initialization function
function initializeCamera() { ... }

// Event handlers
document.getElementById('btn').addEventListener('click', handler);
```

### 3. **Async/Await Pattern**
All API calls and camera operations use modern async syntax:
```javascript
async function captureImage() {
    try {
        const response = await fetch('/api/endpoint', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
    } catch (error) {
        handleError(error);
    }
}
```

### 4. **Progressive Enhancement**
- Base functionality works without JavaScript
- Enhanced features activate when JS is available
- Graceful degradation for older browsers

---

## 🔧 Core Technologies Explained

### 1. WebRTC (Web Real-Time Communication)

**What is it?**
- Open-source standard for real-time audio/video communication
- Direct peer-to-peer or device-to-browser connections
- Built into modern browsers (Chrome, Firefox, Safari, Edge)

**How We Use It:**
```javascript
// Request camera access
const stream = await navigator.mediaDevices.getUserMedia({
    video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user'
    }
});

// Attach to video element
videoElement.srcObject = stream;
```

**Key Concepts:**
- **MediaStream**: Represents the video/audio stream from device
- **getUserMedia()**: Browser API to request device permissions
- **srcObject**: Connects stream to `<video>` element
- **Constraints**: Control resolution, facing mode, frame rate

**Browser Compatibility:**
- Chrome 53+ ✅
- Firefox 36+ ✅
- Safari 11+ ✅
- Edge 79+ ✅

### 2. Canvas API

**What is it?**
- HTML5 element for drawing graphics via JavaScript
- Pixel-level manipulation for image processing

**How We Use It:**
```javascript
// Create canvas context
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');

// Draw video frame to canvas
ctx.drawImage(videoElement, 0, 0, width, height);

// Extract image data
const imageData = canvas.toDataURL('image/jpeg', 0.9);
```

**Key Methods:**
- `getContext('2d')`: 2D rendering context
- `drawImage()`: Copy video frame to canvas
- `toDataURL()`: Convert to base64-encoded image
- `toBlob()`: Convert to binary blob for upload

### 3. Fetch API

**What is it?**
- Modern replacement for XMLHttpRequest
- Promise-based HTTP requests
- Cleaner syntax with async/await

**How We Use It:**
```javascript
async function apiRequest(endpoint, options = {}) {
    const response = await fetch(endpoint, {
        method: options.method || 'GET',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        body: JSON.stringify(options.data)
    });
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    
    return await response.json();
}
```

**Key Features:**
- **Promises**: Chainable .then() or async/await
- **Streaming**: Read response in chunks
- **CORS**: Automatic cross-origin handling
- **Abort Controller**: Cancel in-flight requests

### 4. FormData API

**What is it?**
- Construct key/value pairs for form submission
- Supports binary file uploads
- Automatically sets Content-Type header

**How We Use It:**
```javascript
const formData = new FormData();
formData.append('student_id', '2301105225');
formData.append('name', 'John Doe');
formData.append('roll_number', '2301105225');

// Append images
for (let i = 0; i < images.length; i++) {
    const blob = await fetch(images[i]).then(r => r.blob());
    formData.append('images', blob, `image_${i}.jpg`);
}

// Send to server
await fetch('/api/save-face-images', {
    method: 'POST',
    body: formData // No manual Content-Type header!
});
```

---

## 🎯 Implementation Details

### Camera Initialization Flow

**Step-by-Step Process:**

1. **HTML Setup**
```html
<video id="video" autoplay playsinline></video>
<canvas id="canvas" style="display: none;"></canvas>
```

2. **Request Permissions**
```javascript
async function initCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        });
        
        const video = document.getElementById('video');
        video.srcObject = stream;
        
        // CRITICAL: Wait for video metadata to load
        await new Promise((resolve) => {
            video.onloadedmetadata = () => resolve();
        });
        
        await video.play();
        
    } catch (error) {
        console.error('Camera access denied:', error);
        alert('Please allow camera access');
    }
}
```

3. **Common Issues & Solutions**

**Problem**: Video shows black screen
```javascript
// Solution: Check if stream is active
if (stream.active) {
    console.log('Stream is active');
} else {
    console.error('Stream failed to start');
}
```

**Problem**: Dimensions are 0x0
```javascript
// Solution: Wait for metadata
video.onloadedmetadata = () => {
    console.log(`Resolution: ${video.videoWidth}x${video.videoHeight}`);
};
```

**Problem**: Permission denied
```javascript
// Solution: Must be served over HTTPS (or localhost)
// Check browser permissions: chrome://settings/content/camera
```

### Image Capture Process

**Registration Flow (capture 15 images):**

```javascript
async function startAutoCapture() {
    const images = [];
    const totalImages = 15;
    const intervalMs = 600; // Slow enough to avoid motion blur
    const initialDelay = 800; // Let user settle
    
    await new Promise(resolve => setTimeout(resolve, initialDelay));
    
    for (let i = 0; i < totalImages; i++) {
        // Update UI progress
        updateProgress(i + 1, totalImages);
        
        // Capture frame
        const imageData = captureFrame();
        images.push(imageData);
        
        // Wait before next capture
        if (i < totalImages - 1) {
            await new Promise(resolve => setTimeout(resolve, intervalMs));
        }
    }
    
    return images;
}

function captureFrame() {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    
    // Set canvas dimensions to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Draw current frame
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    
    // Convert to JPEG (0.9 quality = good balance)
    return canvas.toDataURL('image/jpeg', 0.9);
}
```

**Recognition Flow (single scan):**

```javascript
async function scanOnce() {
    // Rate limiting check
    const now = Date.now();
    if (now - lastScanTime < 3000) {
        showNotification('Please wait 3 seconds between scans', 'warning');
        return;
    }
    lastScanTime = now;
    
    // Capture and send
    const imageData = captureFrame();
    const blob = await dataURLtoBlob(imageData);
    
    const formData = new FormData();
    formData.append('image', blob, 'scan.jpg');
    formData.append('subject', getCurrentSubject());
    
    const response = await fetch('/api/recognize-entry', {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    
    if (result.success) {
        displayRecognitionResult(result);
    } else {
        showError(result.message);
    }
}
```

### Manual Attendance System

**Why Manual Attendance?**
- Fallback when face recognition fails (poor lighting, glasses, etc.)
- Accessibility for users with recognition issues
- Faster for known students in trusted environments

**Implementation:**

```javascript
// Load student list on page load
async function loadStudents() {
    try {
        const response = await fetch('/api/students');
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message);
        }
        
        const select = document.getElementById('manualStudentSelect');
        select.innerHTML = '<option value="">-- Select Student --</option>';
        
        data.students.forEach(student => {
            const option = document.createElement('option');
            option.value = student.student_id;
            option.textContent = `${student.name} (${student.roll_number})`;
            option.dataset.name = student.name;
            select.appendChild(option);
        });
        
    } catch (error) {
        console.error('Failed to load students:', error);
        showNotification('Could not load student list', 'error');
    }
}

// Mark manual attendance
document.getElementById('manualEntryBtn').addEventListener('click', async () => {
    const select = document.getElementById('manualStudentSelect');
    const studentId = select.value;
    
    if (!studentId) {
        showNotification('Please select a student', 'warning');
        return;
    }
    
    const selectedOption = select.options[select.selectedIndex];
    const studentName = selectedOption.dataset.name;
    const subject = document.getElementById('subjectSelect').value;
    
    try {
        const response = await apiRequest('/api/mark-entry', {
            method: 'POST',
            data: {
                student_id: studentId,
                student_name: studentName,
                subject: subject,
                manual: true
            }
        });
        
        if (response.success) {
            showNotification(`Entry marked for ${studentName}`, 'success');
            select.value = ''; // Reset selection
        }
        
    } catch (error) {
        showNotification('Failed to mark attendance', 'error');
    }
});
```

---

## 📁 File Structure & Responsibilities

### HTML Templates (`web/templates/`)

```
templates/
├── base.html              # Master template with common layout
├── dashboard.html         # Admin dashboard
├── entry.html            # Entry camera page
├── exit.html             # Exit camera page
├── register.html         # Student registration
├── reports.html          # Attendance reports
├── student_attendance.html # Individual student view
└── admin.html            # System settings
```

**base.html** - Master Template
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Smart Attendance System{% endblock %}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Custom CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <!-- Nav content -->
    </nav>
    
    <!-- Page content -->
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <!-- Scripts -->
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### JavaScript Files (`web/static/js/`)

```
js/
├── main.js                   # Common utilities (650 lines)
├── entry.js                  # Entry camera logic (540 lines)
├── exit.js                   # Exit camera logic (540 lines)
├── register.js               # Registration workflow (313 lines)
├── reports.js                # Report generation (95 lines)
└── student_attendance.js     # Student view (130 lines)
```

**main.js** - Shared Utilities

```javascript
/**
 * Common API request handler
 * Used by all other JS files
 */
async function apiRequest(endpoint, options = {}) {
    const config = {
        method: options.method || 'GET',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    };
    
    if (options.data && config.method !== 'GET') {
        config.body = JSON.stringify(options.data);
    }
    
    try {
        const response = await fetch(endpoint, config);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * Show toast notification
 */
function showNotification(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.add('show'), 100);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * Format datetime for display
 */
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Convert dataURL to Blob for uploading
 */
async function dataURLtoBlob(dataURL) {
    const response = await fetch(dataURL);
    return await response.blob();
}
```

### CSS Architecture (`web/static/css/style.css`)

```css
/* ===== CSS Variables ===== */
:root {
    --primary-color: #0f766e;
    --secondary-color: #14b8a6;
    --danger-color: #dc2626;
    --success-color: #16a34a;
    --warning-color: #fbbf24;
    --dark-bg: #1f2937;
    --light-bg: #f3f4f6;
}

/* ===== Layout System ===== */
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

/* ===== Camera Feed ===== */
.camera-container {
    position: relative;
    background: #000;
    border-radius: 8px;
    overflow: hidden;
}

#video {
    width: 100%;
    max-width: 640px;
    height: auto;
    display: block;
}

/* ===== Recognition Overlay ===== */
.recognition-overlay {
    position: absolute;
    top: 10px;
    left: 10px;
    right: 10px;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 15px;
    border-radius: 6px;
    backdrop-filter: blur(10px);
}

/* ===== Responsive Design ===== */
@media (max-width: 768px) {
    .camera-container {
        margin: 10px 0;
    }
    
    .controls-panel {
        flex-direction: column;
    }
}
```

---

## 🔌 API Integration Patterns

### RESTful Endpoints Used by Frontend

| Endpoint | Method | Purpose | Request Body | Response |
|----------|--------|---------|--------------|----------|
| `/api/students` | GET | Get all students | None | `{success: true, students: [...]}` |
| `/api/save-face-images` | POST | Register student | FormData (images, student_id, name, roll) | `{success: true, message: "..."}` |
| `/api/recognize-entry` | POST | Mark entry attendance | FormData (image, subject) | `{success: true, student: {...}}` |
| `/api/recognize-exit` | POST | Mark exit attendance | FormData (image, subject) | `{success: true, student: {...}}` |
| `/api/mark-entry` | POST | Manual entry | JSON (student_id, subject, manual) | `{success: true}` |
| `/api/mark-exit` | POST | Manual exit | JSON (student_id, subject, manual) | `{success: true}` |
| `/api/reports` | GET | Get attendance reports | Query params (date_from, date_to) | `{success: true, data: [...]}` |

### Error Handling Pattern

```javascript
async function handleApiCall(endpoint, options) {
    try {
        const response = await fetch(endpoint, options);
        
        // Check HTTP status
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Check application-level success
        if (!data.success) {
            throw new Error(data.message || 'Operation failed');
        }
        
        return data;
        
    } catch (error) {
        // Network errors
        if (error instanceof TypeError) {
            showNotification('Network error. Check connection.', 'error');
        } else {
            showNotification(error.message, 'error');
        }
        
        console.error('API Call Failed:', error);
        throw error;
    }
}
```

---

## 🔄 Common Workflows

### Workflow 1: Student Registration

```
User Action → Frontend → Backend → Database
```

**Detailed Steps:**

1. User fills registration form
2. User clicks "Start Capture"
3. Camera initializes (WebRTC)
4. Auto-capture 15 images (600ms intervals)
5. Images converted to base64
6. FormData created with images + metadata
7. POST to `/api/save-face-images`
8. Backend validates each image (face detection)
9. Requires minimum 5 valid faces
10. Saves images to `data/dataset/{student_id}/`
11. Triggers face encoding (background process)
12. Returns success/failure to frontend
13. Display result to user

**Code Integration:**

```javascript
// Step 1-2: Form submission
document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const student_id = document.getElementById('studentId').value;
    const name = document.getElementById('name').value;
    const roll_number = document.getElementById('rollNumber').value;
    
    // Step 3-4: Capture images
    const images = await startAutoCapture();
    
    // Step 5-6: Prepare FormData
    const formData = new FormData();
    formData.append('student_id', student_id);
    formData.append('name', name);
    formData.append('roll_number', roll_number);
    
    for (let i = 0; i < images.length; i++) {
        const blob = await dataURLtoBlob(images[i]);
        formData.append('images', blob, `image_${i}.jpg`);
    }
    
    // Step 7: Send to backend
    const response = await fetch('/api/save-face-images', {
        method: 'POST',
        body: formData
    });
    
    // Step 12-13: Handle response
    const result = await response.json();
    
    if (result.success) {
        showNotification('Registration successful!', 'success');
        setTimeout(() => window.location.href = '/dashboard', 2000);
    } else {
        showNotification(result.message, 'error');
    }
});
```

### Workflow 2: Real-Time Face Recognition

```
Camera Feed → Capture → Send → Recognize → Display
```

**Detailed Steps:**

1. Camera continuously streams to `<video>` element
2. User clicks "Scan Once" or timer triggers scan
3. Current frame captured to canvas
4. Canvas converted to blob
5. FormData with image + current subject
6. POST to `/api/recognize-entry` or `/api/recognize-exit`
7. Backend performs face recognition
8. Returns matched student or "unknown"
9. Frontend displays result with animation
10. Updates recent activity log
11. Rate limits next scan (3 seconds minimum)

---

## 🐛 Troubleshooting & Best Practices

### Common Issues

**1. Camera Not Working**

```javascript
// Check if browser supports getUserMedia
if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert('Your browser does not support camera access');
    return;
}

// Check for HTTPS (required for camera access)
if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
    alert('Camera requires HTTPS connection');
    return;
}
```

**2. CORS Errors**

```python
# Backend must set CORS headers (already configured in app.py)
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    return response
```

**3. Memory Leaks with Camera**

```javascript
// ALWAYS release camera when done
function stopCamera() {
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
}

// Release on page unload
window.addEventListener('beforeunload', stopCamera);
```

**4. Base64 Image Too Large**

```javascript
// Compress before sending
function captureFrame() {
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    
    // Reduce resolution if needed
    const maxWidth = 1280;
    const maxHeight = 720;
    
    let width = video.videoWidth;
    let height = video.videoHeight;
    
    if (width > maxWidth) {
        height = (height * maxWidth) / width;
        width = maxWidth;
    }
    
    canvas.width = width;
    canvas.height = height;
    
    ctx.drawImage(video, 0, 0, width, height);
    
    // Use 0.8 quality for smaller file size
    return canvas.toDataURL('image/jpeg', 0.8);
}
```

### Performance Best Practices

**1. Debounce Button Clicks**

```javascript
let isProcessing = false;

async function handleScan() {
    if (isProcessing) return;
    
    isProcessing = true;
    try {
        await performScan();
    } finally {
        isProcessing = false;
    }
}
```

**2. Lazy Load Images**

```javascript
// Don't load all report images at once
const images = document.querySelectorAll('img[data-src]');
const imageObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const img = entry.target;
            img.src = img.dataset.src;
            imageObserver.unobserve(img);
        }
    });
});

images.forEach(img => imageObserver.observe(img));
```

**3. Cancel Pending Requests**

```javascript
let currentRequest = null;

async function searchStudents(query) {
    // Cancel previous request
    if (currentRequest) {
        currentRequest.abort();
    }
    
    currentRequest = new AbortController();
    
    try {
        const response = await fetch(`/api/search?q=${query}`, {
            signal: currentRequest.signal
        });
        return await response.json();
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Request cancelled');
        } else {
            throw error;
        }
    }
}
```

---

## ❓ FAQs for Frontend Developers

**Q1: Why can't I access the camera on HTTP?**

A: WebRTC's `getUserMedia()` requires a secure context (HTTPS) for security reasons. Exception: `localhost` is always considered secure. For production, you must use HTTPS.

---

**Q2: How do I debug camera issues?**

A: Check browser console for errors. Common issues:
```javascript
// Permission denied
DOMException: Permission denied

// No camera found
DOMException: Requested device not found

// Already in use
DOMException: Could not start video source
```

Check: `chrome://settings/content/camera` for permissions

---

**Q3: Why are my images blurry during registration?**

A: Motion blur from fast capture. Solution:
- Increase interval between captures (currently 600ms)
- Add initial delay for user to settle (currently 800ms)
- Ensure good lighting
- Ask user to stay still

---

**Q4: How do I add a new page?**

A:
1. Create HTML template in `web/templates/new_page.html`
2. Extend base template:
```html
{% extends "base.html" %}
{% block content %}
    <!-- Your content -->
{% endblock %}
```
3. Add route in `web/app.py`:
```python
@app.route('/new-page')
def new_page():
    return render_template('new_page.html')
```
4. Create JS file in `web/static/js/new_page.js`
5. Include in template:
```html
{% block extra_js %}
<script src="{{ url_for('static', filename='js/new_page.js') }}"></script>
{% endblock %}
```

---

**Q5: How do I modify the camera resolution?**

A: Edit constraints in camera initialization:
```javascript
const stream = await navigator.mediaDevices.getUserMedia({
    video: {
        width: { ideal: 1920 },  // Change this
        height: { ideal: 1080 }, // Change this
        facingMode: 'user'
    }
});
```

Note: Higher resolution = larger file uploads. Balance quality vs. performance.

---

**Q6: How does the manual attendance dropdown get populated?**

A: Via `/api/students` endpoint:
```javascript
// Called on page load
async function loadStudents() {
    const response = await fetch('/api/students');
    const data = await response.json();
    
    // Backend returns array of tuples converted to dicts
    data.students.forEach(s => {
        // s = {student_id: "...", name: "...", roll_number: "..."}
        addOptionToDropdown(s);
    });
}
```

Backend returns: `[{student_id: "student_123", name: "John", roll_number: "2301105225"}, ...]`

---

**Q7: What's the difference between entry.js and exit.js?**

A: Nearly identical code, different API endpoints:
- `entry.js` calls `/api/recognize-entry` and `/api/mark-entry`
- `exit.js` calls `/api/recognize-exit` and `/api/mark-exit`

Same camera logic, same UI patterns.

---

**Q8: How do I add a new field to registration form?**

A:
1. Add HTML input in `register.html`:
```html
<input type="email" id="email" name="email" required>
```
2. Capture in `register.js`:
```javascript
const email = document.getElementById('email').value;
formData.append('email', email);
```
3. Handle in backend `app.py`:
```python
email = request.form.get('email')
# Validate and save
```
4. Update database schema if persistent field

---

**Q9: Why does my API call return `undefined`?**

A: Check if you're awaiting the Promise:
```javascript
// WRONG
const data = apiRequest('/api/students');
console.log(data); // Promise {<pending>}

// CORRECT
const data = await apiRequest('/api/students');
console.log(data); // {success: true, students: [...]}
```

---

**Q10: How do I customize the UI theme?**

A: Modify CSS variables in `style.css`:
```css
:root {
    --primary-color: #yourColor;
    --secondary-color: #yourColor;
    /* ... */
}
```

All components inherit from these variables.

---

## 🎓 Learning Resources

**WebRTC:**
- MDN: https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API
- WebRTC Samples: https://webrtc.github.io/samples/

**Canvas API:**
- MDN: https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API
- Tutorial: https://www.w3schools.com/html/html5_canvas.asp

**Fetch API:**
- MDN: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API
- Google Guide: https://web.dev/introduction-to-fetch/

**Async/Await:**
- MDN: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/async_function
- JavaScript.info: https://javascript.info/async-await

---

## ✅ Development Checklist

**Before Starting Development:**
- [ ] Understand WebRTC camera basics
- [ ] Review existing JS files (main.js, entry.js)
- [ ] Test camera access in browser console
- [ ] Understand Flask template syntax (Jinja2)

**During Development:**
- [ ] Test on Chrome, Firefox, Edge
- [ ] Check mobile responsiveness
- [ ] Monitor browser console for errors
- [ ] Test with camera denied scenario
- [ ] Verify HTTPS works (production)

**Before Deployment:**
- [ ] Minify JavaScript files (optional)
- [ ] Compress images in static/images/
- [ ] Test on slow network (throttling)
- [ ] Verify all API endpoints work
- [ ] Test offline behavior (error messages)

---

**Need Help?**
Check the code comments in each JS file - they explain the logic step-by-step!
