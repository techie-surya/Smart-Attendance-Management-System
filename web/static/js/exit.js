let stream = null;
let monitorTimer = null;
let sessionStopTimer = null;
let isBusy = false;
let lastGrayFrame = null;
let lastManualScanTime = 0;
const MANUAL_SCAN_COOLDOWN_MS = 3000; // 3 seconds cooldown between manual scans

document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("exitRoot");
    if (!root) {
        return;
    }

    const baseScanInterval = Number(root.dataset.scanIntervalMs || 1500);
    const defaultRunInterval = Number(root.dataset.defaultRunInterval || 45);
    const defaultSessionDuration = Number(root.dataset.defaultSessionDuration || 90);
    const defaultMotionThreshold = Number(root.dataset.defaultMotionThreshold || 0.018);
    const defaultMinimumDuration = Number(root.dataset.defaultMinimumDuration || 90);

    const video = document.getElementById("liveVideo");
    const canvas = document.getElementById("frameCanvas");
    const cameraPanel = document.getElementById("cameraPanel");
    const startBtn = document.getElementById("startCameraBtn");
    const stopBtn = document.getElementById("stopCameraBtn");
    const scanBtn = document.getElementById("scanOnceBtn");
    const monitorBtn = document.getElementById("toggleMonitorBtn");
    const statusNode = document.getElementById("liveStatus");
    const resultBox = document.getElementById("resultBox");
    const resultContent = document.getElementById("resultContent");
    const recentList = document.getElementById("recentEntriesList");
    const cameraPolicy = document.getElementById("cameraPolicy");
    const useYolo = document.getElementById("useYolo");
    const activeSubject = document.getElementById("activeSubject");
    const cameraRunMode = document.getElementById("cameraRunMode");
    const runInterval = document.getElementById("runInterval");
    const sessionDuration = document.getElementById("sessionDuration");
    const motionThreshold = document.getElementById("motionThreshold");
    const minimumDuration = document.getElementById("minimumDuration");

    runInterval.value = runInterval.value || String(defaultRunInterval);
    sessionDuration.value = sessionDuration.value || String(defaultSessionDuration);
    motionThreshold.value = motionThreshold.value || String(defaultMotionThreshold);
    minimumDuration.value = minimumDuration.value || String(defaultMinimumDuration);

    const setStatus = (text) => {
        statusNode.textContent = text;
    };

    const monitorRunning = () => Boolean(monitorTimer);

    const getSelectedMode = () => (cameraRunMode.value || "once").trim();

    const getIntervalMsForMode = () => {
        const mode = getSelectedMode();
        if (mode === "interval") {
            const seconds = Math.max(3, Number(runInterval.value || defaultRunInterval));
            return Math.round(seconds * 1000);
        }
        return Math.max(600, baseScanInterval);
    };

    const updateMonitorButton = () => {
        const mode = getSelectedMode();
        if (mode === "once") {
            monitorBtn.textContent = "Run Once Mode";
            monitorBtn.disabled = true;
            return;
        }
        monitorBtn.disabled = !stream;
        monitorBtn.textContent = monitorRunning() ? "Stop Monitor" : "Start Monitor";
    };

    const updateUIFeatureAvailability = () => {
        const policy = cameraPolicy.value;
        const mode = getSelectedMode();

        // If "Always On" is selected, disable "Run Once" mode
        if (policy === "always_on") {
            Array.from(cameraRunMode.options).forEach(option => {
                if (option.value === "once") {
                    option.disabled = true;
                }
            });
            // If current mode is "once", switch to "session"
            if (mode === "once") {
                cameraRunMode.value = "session";
            }
        } else {
            // Re-enable all run mode options
            Array.from(cameraRunMode.options).forEach(option => {
                option.disabled = false;
            });
        }

        // If "Run Once" is selected, disable "Always On" policy
        if (mode === "once") {
            Array.from(cameraPolicy.options).forEach(option => {
                if (option.value === "always_on") {
                    option.disabled = true;
                }
            });
            // If current policy is "always_on", switch to "on_demand"
            if (policy === "always_on") {
                cameraPolicy.value = "on_demand";
            }
        } else {
            // Re-enable all policy options
            Array.from(cameraPolicy.options).forEach(option => {
                option.disabled = false;
            });
        }

        // Enable/disable features based on run mode
        // Session Duration: only for "session" mode
        sessionDuration.disabled = (mode !== "session");
        sessionDuration.parentElement.style.opacity = (mode === "session") ? "1" : "0.5";

        // Interval Check: only for "interval" mode
        runInterval.disabled = (mode !== "interval");
        runInterval.parentElement.style.opacity = (mode === "interval") ? "1" : "0.5";

        // Fair Motion Threshold: only for "interval" mode
        motionThreshold.disabled = (mode !== "interval");
        motionThreshold.parentElement.style.opacity = (mode === "interval") ? "1" : "0.5";
    };

    const clearSessionTimer = () => {
        if (sessionStopTimer) {
            clearTimeout(sessionStopTimer);
            sessionStopTimer = null;
        }
    };

    const stopMonitoring = () => {
        if (monitorTimer) {
            clearInterval(monitorTimer);
            monitorTimer = null;
        }
        clearSessionTimer();
        updateMonitorButton();
    };

    const stopCamera = () => {
        stopMonitoring();
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
        }
        stream = null;
        video.srcObject = null;
        lastGrayFrame = null;
        startBtn.disabled = false;
        stopBtn.disabled = true;
        scanBtn.disabled = true;
        monitorBtn.disabled = true;
        setStatus("Idle");
    };

    const captureFrame = () => {
        if (!video.videoWidth || !video.videoHeight) {
            return null;
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const context = canvas.getContext("2d");
        context.drawImage(video, 0, 0);
        const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
        return {
            jpeg: canvas.toDataURL("image/jpeg", 0.85),
            pixels: imageData.data,
        };
    };

    const computeMotionScore = (pixelBuffer) => {
        const sampleStep = 16;
        const current = [];

        for (let i = 0; i < pixelBuffer.length; i += sampleStep) {
            const r = pixelBuffer[i] || 0;
            const g = pixelBuffer[i + 1] || 0;
            const b = pixelBuffer[i + 2] || 0;
            current.push((r + g + b) / 3);
        }

        if (!lastGrayFrame) {
            lastGrayFrame = current;
            return 1;
        }

        let moved = 0;
        const threshold = 22;
        const size = Math.min(lastGrayFrame.length, current.length);
        for (let idx = 0; idx < size; idx += 1) {
            if (Math.abs(current[idx] - lastGrayFrame[idx]) > threshold) {
                moved += 1;
            }
        }
        lastGrayFrame = current;
        return size ? moved / size : 0;
    };

    const renderRecent = (entries) => {
        if (!entries.length) {
            recentList.innerHTML = '<p class="meta-note">No entries yet.</p>';
            return;
        }

        recentList.innerHTML = entries
            .map(
                (entry) => `
                    <article class="activity-item">
                        <div>
                            <strong>${entry.name}</strong>
                            <p>${entry.student_id}</p>
                        </div>
                        <time>${formatDateTime(entry.exit_time)}</time>
                    </article>
                `
            )
            .join("");
    };

    const loadRecent = async () => {
        try {
            const payload = await apiRequest("/api/recent-exits");
            renderRecent(payload.entries || []);
        } catch (error) {
            recentList.innerHTML = `<p class="meta-note">${error.message}</p>`;
        }
    };

    const persistSettings = async () => {
        const settingsPayload = {
            camera_policy: cameraPolicy.value,
            camera_run_mode: cameraRunMode.value,
            active_subject: activeSubject.value,
            run_interval_seconds: Number(runInterval.value || defaultRunInterval),
            session_duration_minutes: Number(sessionDuration.value || defaultSessionDuration),
            fair_motion_threshold: Number(motionThreshold.value || defaultMotionThreshold),
            minimum_duration_minutes: Number(minimumDuration.value || defaultMinimumDuration),
            use_yolo: useYolo.checked,
        };

        const payload = await apiRequest("/api/settings", {
            method: "POST",
            body: JSON.stringify(settingsPayload),
        });

        if (payload.settings && payload.settings.yolo_supported === false) {
            useYolo.checked = false;
            useYolo.disabled = true;
        }
    };

    const showResult = (data) => {
        resultBox.hidden = false;
        resultContent.innerHTML = `
            <dl class="result-grid">
                <dt>Student</dt><dd>${data.student_name}</dd>
                <dt>ID</dt><dd>${data.student_id}</dd>
                <dt>Confidence</dt><dd>${data.confidence}%</dd>
                <dt>Entry Time</dt><dd>${formatDateTime(data.exit_time)}</dd>
                <dt>Subject</dt><dd>${activeSubject.value}</dd>
            </dl>
        `;
    };

    const scanOnce = async (isAutoScan = false) => {
        if (isBusy || !stream) {
            return;
        }

        // Rate limiting for manual scans (not auto-monitoring)
        if (!isAutoScan) {
            const now = Date.now();
            const timeSinceLastScan = now - lastManualScanTime;
            if (timeSinceLastScan < MANUAL_SCAN_COOLDOWN_MS) {
                const remainingSeconds = Math.ceil((MANUAL_SCAN_COOLDOWN_MS - timeSinceLastScan) / 1000);
                showNotification(`Please wait ${remainingSeconds}s before scanning again`, "warning");
                return;
            }
            lastManualScanTime = now;
        }

        const capture = captureFrame();
        if (!capture) {
            return;
        }

        const mode = getSelectedMode();
        if (mode === "interval") {
            const motionScore = computeMotionScore(capture.pixels);
            const requiredMotion = Math.max(0, Number(motionThreshold.value || defaultMotionThreshold));
            if (motionScore < requiredMotion) {
                setStatus("Fair Check: no movement");
                return;
            }
        }

        isBusy = true;
        setStatus("Scanning...");

        try {
            const requestBody = {
                image: capture.jpeg,
                subject: activeSubject.value
            };

            const data = await apiRequest("/api/recognize-exit", {
                method: "POST",
                body: JSON.stringify(requestBody),
            });

            showResult(data);
            setStatus("Matched");
            showNotification(`${data.student_name} marked as exited`, "success");
            await loadRecent();
        } catch (error) {
            setStatus("No Match");
            showNotification(error.message, "warning");
        } finally {
            isBusy = false;
        }
    };

    const startMonitoringForMode = () => {
        const mode = getSelectedMode();
        if (mode === "once") {
            updateMonitorButton();
            return;
        }

        stopMonitoring();
        const intervalMs = getIntervalMsForMode();
        // Pass true to indicate auto-scan (apply motion check)
        monitorTimer = setInterval(() => scanOnce(true), intervalMs);

        if (mode === "session") {
            const totalMinutes = Math.max(1, Number(sessionDuration.value || defaultSessionDuration));
            sessionStopTimer = setTimeout(() => {
                stopMonitoring();
                setStatus("Session completed");
                showNotification("Class session monitor completed", "info");
            }, totalMinutes * 60 * 1000);
        }

        updateMonitorButton();
    };

    startBtn.addEventListener("click", async () => {
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
                audio: false,
            });
            video.srcObject = stream;
            lastGrayFrame = null;
            startBtn.disabled = true;
            stopBtn.disabled = false;
            scanBtn.disabled = false;
            setStatus("Camera On");
            updateMonitorButton();
            showNotification("Exit camera started", "success");

            if (cameraPolicy.value === "always_on" && getSelectedMode() !== "once") {
                startMonitoringForMode();
            }
        } catch (error) {
            showNotification(error.message, "error");
        }
    });

    stopBtn.addEventListener("click", () => {
        stopCamera();
        showNotification("Camera stopped", "info");
    });

    scanBtn.addEventListener("click", scanOnce);

    monitorBtn.addEventListener("click", () => {
        if (!stream) {
            showNotification("Start camera first", "warning");
            return;
        }
        if (getSelectedMode() === "once") {
            showNotification("Run Once mode uses the Scan Once button", "info");
            return;
        }
        if (monitorRunning()) {
            stopMonitoring();
            showNotification("Monitoring stopped", "info");
            return;
        }
        startMonitoringForMode();
        showNotification("Monitoring started", "success");
    });

    const onSettingsChanged = async () => {
        try {
            updateUIFeatureAvailability();
            await persistSettings();
            updateMonitorButton();
            showNotification("Teacher settings updated", "success");

            if (!monitorRunning()) {
                return;
            }
            if (getSelectedMode() === "once") {
                stopMonitoring();
                return;
            }
            startMonitoringForMode();
        } catch (error) {
            showNotification(error.message, "error");
        }
    };

    cameraPolicy.addEventListener("change", onSettingsChanged);
    useYolo.addEventListener("change", onSettingsChanged);
    activeSubject.addEventListener("change", onSettingsChanged);
    cameraRunMode.addEventListener("change", onSettingsChanged);
    runInterval.addEventListener("change", onSettingsChanged);
    sessionDuration.addEventListener("change", onSettingsChanged);
    motionThreshold.addEventListener("change", onSettingsChanged);
    minimumDuration.addEventListener("change", onSettingsChanged);

    // Manual attendance handling
    const manualStudentSelect = document.getElementById("manualStudentSelect");
    const manualExitBtn = document.getElementById("manualExitBtn");

    const loadStudents = async () => {
        try {
            const data = await apiRequest("/api/students");
            const students = data.students || [];
            
            manualStudentSelect.innerHTML = '<option value="">-- Select Student --</option>';
            students.forEach(student => {
                const option = document.createElement("option");
                option.value = student.student_id;
                option.textContent = `${student.name} (${student.roll_number})`;
                option.dataset.name = student.name;
                manualStudentSelect.appendChild(option);
            });
        } catch (error) {
            showNotification("Failed to load students: " + error.message, "error");
        }
    };

    manualStudentSelect.addEventListener("change", () => {
        manualExitBtn.disabled = !manualStudentSelect.value;
    });

    manualExitBtn.addEventListener("click", async () => {
        const studentId = manualStudentSelect.value;
        if (!studentId) {
            showNotification("Please select a student", "warning");
            return;
        }

        const selectedOption = manualStudentSelect.options[manualStudentSelect.selectedIndex];
        const studentName = selectedOption.dataset.name;

        if (!activeSubject.value) {
            showNotification("Please select an active subject", "warning");
            return;
        }

        try {
            manualExitBtn.disabled = true;
            const data = await apiRequest("/api/mark-exit", {
                method: "POST",
                body: JSON.stringify({
                    student_id: studentId,
                    name: studentName,
                    subject: activeSubject.value
                })
            });

            showNotification(`${studentName} marked as exited manually`, "success");
            showResult(data);
            await loadRecent();
            manualStudentSelect.value = "";
        } catch (error) {
            showNotification("Manual exit failed: " + error.message, "error");
            manualExitBtn.disabled = false;
        }
    });

    window.addEventListener("beforeunload", stopCamera);
    updateUIFeatureAvailability();
    updateMonitorButton();
    loadRecent();
    loadStudents();
});
