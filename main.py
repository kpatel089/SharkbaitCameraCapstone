"""Mock Raspberry Pi backend for testing index.html on a laptop.

Install:  pip install flask opencv-python numpy
Run:      python mock_pi_server.py     (keep index.html in the same folder)
Open:     http://localhost:5000   (or http://<laptop-LAN-IP>:5000 on your phone)
"""
import threading
import time

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request, send_from_directory

app = Flask(__name__)

PAN_LIMIT, TILT_LIMIT = 90, 45          # simulated gimbal range (degrees)
PX_PER_DEG = 12                         # how far the image shifts per degree
SPEED_DEG_PER_S = 60                    # speed at full joystick deflection

state = {"pan": 0.0, "tilt": 0.0, "vx": 0.0, "vy": 0.0, "zoom": 1.0}
lock = threading.Lock()


def simulate_gimbal():
    last = time.time()
    while True:
        time.sleep(0.02)
        now = time.time()
        dt, last = now - last, now
        with lock:
            state["pan"] = max(-PAN_LIMIT, min(PAN_LIMIT, state["pan"] + state["vx"] * SPEED_DEG_PER_S * dt))
            state["tilt"] = max(-TILT_LIMIT, min(TILT_LIMIT, state["tilt"] + state["vy"] * SPEED_DEG_PER_S * dt))


threading.Thread(target=simulate_gimbal, daemon=True).start()

# ---- Video source: webcam if available, else a synthetic grid ----
W, H = 1280, 720   # output size; use 1920, 1080 for even sharper (needs a fast laptop)

# CAP_DSHOW is the Windows backend and usually allows HD resolutions
cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cam.isOpened():
    cam = cv2.VideoCapture(0)
cam.set(cv2.CAP_PROP_FRAME_WIDTH, W)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # MJPG gives HD at 30fps on most webcams


def synthetic_frame():
    img = np.full((H * 2, W * 2, 3), 30, np.uint8)
    for x in range(0, W * 2, 80):
        cv2.line(img, (x, 0), (x, H * 2), (70, 90, 80), 1)
    for y in range(0, H * 2, 80):
        cv2.line(img, (0, y), (W * 2, y), (70, 90, 80), 1)
    cv2.circle(img, (W, H), 120, (94, 224, 176), 3)
    cv2.putText(img, "TEST PATTERN", (W - 170, H + 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (230, 240, 236), 2)
    return img


SYNTH = synthetic_frame()


def get_base():
    if cam.isOpened():
        ok, frame = cam.read()
        if ok:
            frame = cv2.resize(frame, (W, H))
            return cv2.copyMakeBorder(frame, H // 2, H // 2, W // 2, W // 2, cv2.BORDER_REFLECT)
    return SYNTH


def frames():
    while True:
        base = get_base()
        with lock:
            pan, tilt, zoom = state["pan"], state["tilt"], state["zoom"]
        # Pan right -> view moves right; tilt up -> view moves up
        cx = base.shape[1] // 2 + int(pan * PX_PER_DEG)
        cy = base.shape[0] // 2 - int(tilt * PX_PER_DEG)
        vw, vh = int(W / zoom), int(H / zoom)
        x0 = max(0, min(base.shape[1] - vw, cx - vw // 2))
        y0 = max(0, min(base.shape[0] - vh, cy - vh // 2))
        view = cv2.resize(base[y0:y0 + vh, x0:x0 + vw], (W, H), interpolation=cv2.INTER_CUBIC)
        label = f"pan {pan:5.1f}  tilt {tilt:5.1f}  zoom {zoom:.1f}x"
        cv2.putText(view, label, (20, H - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        ok, jpg = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
        time.sleep(1 / 25)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/video_feed")
def video_feed():
    return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/move", methods=["POST"])
def move():
    data = request.get_json(silent=True) or {}
    with lock:
        state["vx"] = float(data.get("pan", 0))
        state["vy"] = float(data.get("tilt", 0))
    print(f"move  pan={state['vx']:+.2f} tilt={state['vy']:+.2f}")
    return jsonify(ok=True)


@app.route("/api/zoom", methods=["POST"])
def zoom():
    data = request.get_json(silent=True) or {}
    with lock:
        state["zoom"] = max(1.0, min(8.0, float(data.get("zoom", 1))))
    print(f"zoom  {state['zoom']:.1f}x")
    return jsonify(ok=True)


@app.route("/api/center", methods=["POST"])
def center():
    with lock:
        state.update(pan=0.0, tilt=0.0, vx=0.0, vy=0.0, zoom=1.0)
    print("center")
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
