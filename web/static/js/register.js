/**
 * Show an extended notification with longer display time for detailed messages
 * @param {string} message - The message to display
 * @param {string} type - The notification type (info, success, error, warning)
 */
function showExtendedNotification(message, type = "info") {
    const host = document.body;
    const node = document.createElement("div");
    node.className = `toast toast-${type}`;
    node.style.whiteSpace = "pre-line"; // Allow line breaks in message
    node.style.maxWidth = "500px"; // Wider for detailed messages
    node.textContent = message;
    host.appendChild(node);

    requestAnimationFrame(() => node.classList.add("show"));

    // Extended timeout for error messages with detailed guidance (8 seconds instead of 3.5)
    const timeout = type === "error" ? 8000 : 3500;
    setTimeout(() => {
        node.classList.remove("show");
        setTimeout(() => node.remove(), 400);
    }, timeout);
}

let stream = null;
let autoCaptureTimer = null;
let capturedImages = [];

const captureState = {
    running: false,
};

document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("registerRoot");
    if (!root) {
        return;
    }

    const totalImages = Number(root.dataset.totalImages || 20);
    const video = document.getElementById("videoPreview");
    const canvas = document.getElementById("captureCanvas");
    const nameInput = document.getElementById("nameInput");
    const rollInput = document.getElementById("rollInput");
    const startBtn = document.getElementById("startCameraBtn");
    const stopBtn = document.getElementById("stopCameraBtn");
    const autoBtn = document.getElementById("autoCaptureBtn");
    const clearBtn = document.getElementById("clearCaptureBtn");
    const submitBtn = document.getElementById("submitBtn");
    const captureCount = document.getElementById("captureCount");
    const capturedGrid = document.getElementById("capturedGrid");
    const form = document.getElementById("registerForm");

    const setCaptureCount = () => {
        captureCount.textContent = `${capturedImages.length} / ${totalImages}`;
        submitBtn.disabled = capturedImages.length < totalImages;
    };

    const stopAutoCapture = () => {
        captureState.running = false;
        if (autoCaptureTimer) {
            clearInterval(autoCaptureTimer);
            autoCaptureTimer = null;
        }
        autoBtn.textContent = "Auto Capture";
    };

    const stopCamera = () => {
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
        }
        stream = null;
        video.srcObject = null;
        stopAutoCapture();
        startBtn.disabled = false;
        stopBtn.disabled = true;
        autoBtn.disabled = true;
    };

    const captureFrame = () => {
        if (!stream || capturedImages.length >= totalImages) {
            return;
        }
        if (!video.videoWidth || !video.videoHeight) {
            return;
        }

        const width = 640;
        const height = 480;
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, width, height);
        const imageData = canvas.toDataURL("image/jpeg", 0.9);
        capturedImages.push(imageData);

        const thumb = document.createElement("img");
        thumb.src = imageData;
        thumb.alt = `capture-${capturedImages.length}`;
        capturedGrid.appendChild(thumb);

        setCaptureCount();
        if (capturedImages.length >= totalImages) {
            stopAutoCapture();
            showNotification("All samples captured", "success");
        }
    };

    startBtn.addEventListener("click", async () => {
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: "user",
                },
                audio: false,
            });
            video.srcObject = stream;
            startBtn.disabled = true;
            stopBtn.disabled = false;
            autoBtn.disabled = false;
            showNotification("Camera started", "success");
        } catch (error) {
            showNotification(error.message, "error");
        }
    });

    stopBtn.addEventListener("click", () => {
        stopCamera();
        showNotification("Camera stopped", "info");
    });

    autoBtn.addEventListener("click", () => {
        if (!stream) {
            showNotification("Start camera first", "warning");
            return;
        }
        if (capturedImages.length >= totalImages) {
            showNotification("Target image count already reached", "info");
            return;
        }
        if (captureState.running) {
            stopAutoCapture();
            showNotification("Auto capture paused", "info");
            return;
        }

        captureState.running = true;
        autoBtn.textContent = "Pause Capture";
        autoCaptureTimer = setInterval(() => {
            captureFrame();
            if (capturedImages.length >= totalImages) {
                stopAutoCapture();
            }
        }, 300);
    });

    clearBtn.addEventListener("click", () => {
        capturedImages = [];
        capturedGrid.innerHTML = "";
        setCaptureCount();
        stopAutoCapture();
    });

    // Auto-format roll number as user types (matches backend logic)
    rollInput.addEventListener("input", () => {
        const original = rollInput.value;
        if (!original) {
            rollInput.style.borderColor = '';
            rollInput.title = '';
            return;
        }
        
        // Simulate backend formatting logic
        let cleaned = original.toUpperCase();
        
        // Remove separators first
        cleaned = cleaned.replace(/[\s\-_/.,:\(\)\[\]]+/g, '');
        
        // Remove common prefixes (same order as backend)
        const prefixes = [
            'ROLLNUMBER', 'ROLLNO',
            'STUDENTNUMBER', 'STUDENTID', 'STUDENTNO', 'STUDENT',
            'REGISTRATIONNO', 'REGISTRATION',
            'REGNUMBER', 'REGNO', 'REG',
            'IDNUMBER', 'IDNO', 'ID',
            'ROLL', 'NUMBER', 'NO',
        ];
        
        for (const prefix of prefixes) {
            if (cleaned.startsWith(prefix)) {
                cleaned = cleaned.substring(prefix.length);
                break;
            }
        }
        
        // Remove any remaining non-alphanumeric
        cleaned = cleaned.replace(/[^A-Z0-9]/g, '');
        
        // Show helpful hint if formatting occurred
        if (cleaned !== original.toUpperCase() && cleaned.length > 0) {
            rollInput.style.borderColor = '#4CAF50';
            rollInput.style.borderWidth = '2px';
            rollInput.title = `Will be formatted as: ${cleaned}`;
        } else {
            rollInput.style.borderColor = '';
            rollInput.style.borderWidth = '';
            rollInput.title = '';
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const name = (nameInput.value || "").trim();
        const rollNumber = (rollInput.value || "").trim();

        if (!name || !rollNumber) {
            showNotification("Name and roll number are required", "warning");
            return;
        }
        if (capturedImages.length < totalImages) {
            showNotification(`Capture ${totalImages} images before submitting`, "warning");
            return;
        }

        const studentId = `student_${rollNumber}_${name.replace(/\s+/g, "_")}`;

        submitBtn.disabled = true;
        submitBtn.textContent = "Registering...";

        try {
            await apiRequest("/api/register-student", {
                method: "POST",
                body: JSON.stringify({
                    student_id: studentId,
                    name,
                    roll_number: rollNumber,
                }),
            });

            // Update progress message
            submitBtn.textContent = "Validating images...";
            
            const saveResult = await apiRequest("/api/save-face-images", {
                method: "POST",
                body: JSON.stringify({
                    student_id: studentId,
                    images: capturedImages,
                }),
            });

            // Show detailed validation results if available
            if (saveResult.details) {
                console.log("Face validation results:", saveResult.details);
            }

            // Update progress message
            submitBtn.textContent = "Generating encodings...";
            
            // Encode only this student's faces (much faster than re-encoding all students)
            await apiRequest(`/api/encode-student/${studentId}`, { method: "POST" });

            showNotification("Student registered successfully", "success");

            form.reset();
            capturedImages = [];
            capturedGrid.innerHTML = "";
            setCaptureCount();
            stopCamera();
        } catch (error) {
            // Show extended notification for detailed error messages (e.g., face detection failures)
            showExtendedNotification(error.message, "error");
        } finally {
            submitBtn.textContent = "Register Student";
            submitBtn.disabled = capturedImages.length < totalImages;
        }
    });

    window.addEventListener("beforeunload", stopCamera);
    setCaptureCount();
});
