let cameras = [];
let streams = {};

/* ---------- CHECK CAMERA API ---------- */
function checkMedia() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("Camera not available. Check browser permissions.");
        throw new Error("Camera API unavailable");
    }
}

/* ---------- LOAD CAMERAS ---------- */
async function loadCameras() {
    checkMedia();

    await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    const devices = await navigator.mediaDevices.enumerateDevices();
    cameras = devices.filter(d => d.kind === "videoinput");
}

/* ---------- POPULATE DROPDOWNS ---------- */
function populate(selectId) {
    const select = document.getElementById(selectId);
    select.innerHTML = "";
    cameras.forEach((cam, i) => {
        const opt = document.createElement("option");
        opt.value = cam.deviceId;
        opt.text = cam.label || `Camera ${i + 1}`;
        select.appendChild(opt);
    });
}

/* ---------- STOP STREAM ---------- */
function stopStream(videoId) {
    if (streams[videoId]) {
        streams[videoId].getTracks().forEach(t => t.stop());
    }
}

/* ---------- START CAMERA ---------- */
async function startCamera(selectId, videoId) {
    stopStream(videoId);

    const select = document.getElementById(selectId);
    const video = document.getElementById(videoId);

    const stream = await navigator.mediaDevices.getUserMedia({
        video: { deviceId: { exact: select.value } },
        audio: false
    });

    streams[videoId] = stream;
    video.srcObject = stream;
}

/* ---------- WEBSOCKET ---------- */
function startWS(videoId, resultId, camType) {
    const ws = new WebSocket(`ws://${location.host}/ws/${camType}`);
    const video = document.getElementById(videoId);
    const result = document.getElementById(resultId);

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    ws.onopen = () => {
        setInterval(() => {
            if (video.videoWidth === 0) return;

            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0);

            ws.send(canvas.toDataURL("image/jpeg", 0.7).split(",")[1]);
        }, 200); // 5 FPS
    };

    ws.onmessage = (e) => {
        result.src = "data:image/jpeg;base64," + e.data;
    };
}

/* ---------- INIT ---------- */
window.addEventListener("load", async () => {
    try {
        await loadCameras();

        populate("inSelect");
        populate("outSelect");

        if (cameras.length > 1)
            document.getElementById("outSelect").selectedIndex = 1;

        await startCamera("inSelect", "inVideo");
        await startCamera("outSelect", "outVideo");

        startWS("inVideo", "inResult", "in");
        startWS("outVideo", "outResult", "out");

        document.getElementById("inSelect").onchange =
            () => startCamera("inSelect", "inVideo");

        document.getElementById("outSelect").onchange =
            () => startCamera("outSelect", "outVideo");

    } catch (err) {
        console.error(err);
    }
});
