import sys
import cv2
import time
import json
import threading
import requests
import pyttsx3
import os
import re
import math
import numpy as np
from datetime import datetime
from PIL import Image
from io import BytesIO

# --- CẤU HÌNH HỆ THỐNG ---
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|reconnect;1|reconnect_streamed;1|reconnect_delay_max;5|rw_timeout;10000000"

# --- AI LIBS ---
try: import face_recognition
except ImportError: face_recognition = None

from ultralytics import YOLO

# --- GOOGLE CLOUD AI ---
try: from google import genai 
except ImportError: genai = None

# --- YOUTUBE LIB ---
try: import yt_dlp
except ImportError: yt_dlp = None

# --- GUI LIBS ---
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize, QTimer, QBuffer, QIODevice, QObject
from PySide6.QtGui import QImage, QPixmap, QFont, QColor, QIcon, QPalette, QBrush
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QLineEdit, 
                               QTableWidget, QTableWidgetItem, QHeaderView, 
                               QComboBox, QMessageBox, QGroupBox, QFrame, QSizePolicy, QSplitter)

# ==============================================================================
# 1. GIAO DIỆN STYLE (MODERN PROFESSIONAL THEME)
# ==============================================================================
MODERN_THEME = """
/* GLOBAL SETTINGS */
QMainWindow { 
    background-color: #1a1b26; 
    color: #a9b1d6; 
}
QWidget { 
    font-family: 'Segoe UI', 'Roboto', sans-serif; 
    font-size: 13px; 
}

/* GROUP BOX */
QGroupBox { 
    border: 1px solid #414868; 
    border-radius: 8px; 
    margin-top: 20px; 
    background-color: #24283b; 
    font-weight: bold; 
    color: #7aa2f7; 
    padding-top: 15px;
}
QGroupBox::title { 
    subcontrol-origin: margin; 
    left: 10px; 
    padding: 0 5px; 
}

/* INPUTS */
QLineEdit, QComboBox { 
    background-color: #16161e; 
    border: 1px solid #414868; 
    border-radius: 4px; 
    padding: 8px; 
    color: #c0caf5; 
    selection-background-color: #7aa2f7;
}
QLineEdit:focus, QComboBox:focus { 
    border: 1px solid #7aa2f7; 
}
QComboBox::drop-down { border: none; }

/* BUTTONS */
QPushButton { 
    background-color: #7aa2f7; 
    color: #1a1b26; 
    border: none; 
    border-radius: 6px; 
    padding: 10px; 
    font-weight: bold; 
    font-size: 14px;
}
QPushButton:hover { background-color: #bb9af7; }
QPushButton:pressed { background-color: #3d59a1; }

QPushButton#stop_btn { 
    background-color: #f7768e; 
    color: #fff;
}
QPushButton#stop_btn:hover { background-color: #ff9e64; }

/* TABLE WIDGET (LOGS) */
QTableWidget { 
    background-color: #16161e; 
    border: 1px solid #414868; 
    border-radius: 6px; 
    gridline-color: #292e42; 
    color: #a9b1d6; 
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
}
QTableWidget::item { padding: 5px; }
QHeaderView::section { 
    background-color: #24283b; 
    color: #7aa2f7; 
    padding: 5px; 
    border: none; 
    font-weight: bold; 
}
QScrollBar:vertical {
    border: none;
    background: #16161e;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #414868;
    min-height: 20px;
    border-radius: 4px;
}

/* STATUS LABEL */
QLabel#status_lbl { 
    font-weight: 900; 
    font-size: 20px; 
    letter-spacing: 2px; 
    background-color: #16161e;
    border-radius: 8px;
    padding: 10px;
}

/* VIDEO FRAME */
QLabel#video_frame {
    background-color: #000; 
    border: 2px solid #414868;
    border-radius: 8px;
}
"""

# ==============================================================================
# 2. TELEGRAM WORKER
# ==============================================================================
def telegram_worker(token, chat_id, text=None, img_bytes=None, video_path=None):
    def _run():
        if not token or not chat_id: return
        url = f"https://api.telegram.org/bot{token}"
        try:
            if text: requests.post(f"{url}/sendMessage", json={"chat_id": chat_id, "text": f"🛡️ {text}"}, timeout=10)
            if img_bytes is not None:
                real_bytes = bytes(img_bytes) if not isinstance(img_bytes, bytes) else img_bytes
                files = {'photo': ('alert.jpg', real_bytes, 'image/jpeg')}
                requests.post(f"{url}/sendPhoto", data={"chat_id": chat_id}, files=files, timeout=20)
            if video_path and os.path.exists(video_path):
                time.sleep(2.0)
                if os.path.getsize(video_path) > 0:
                    with open(video_path, 'rb') as f:
                        requests.post(f"{url}/sendVideo", data={"chat_id": chat_id}, files={'video': f}, timeout=120)
        except Exception as e: print(f"❌ [TELEGRAM ERROR] {e}")
    threading.Thread(target=_run).start()

# ==============================================================================
# 3. CLOUD VERIFIER
# ==============================================================================
class CloudVerifier(QObject):
    result_signal = Signal(bool, str, str, object)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key
        try: self.client = genai.Client(api_key=self.api_key) if genai else None
        except: self.client = None

    def verify(self, img, alert_type):
        if not self.client: return
        threading.Thread(target=self._run_verify, args=(img, alert_type)).start()

    def _run_verify(self, img, alert_type):
        try:
            h, w = img.shape[:2]
            scale = 640 / w
            new_h = int(h * scale)
            resized_img = cv2.resize(img, (640, new_h))
            pil_img = Image.fromarray(cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB))
            
            if alert_type == "WEAPON":
                prompt = """Security Check. LETHAL WEAPON (Gun/Knife) visible? 
                Ignore: Phone, Tools, Toys. JSON: {"risk": "DANGER"/"SAFE", "reason": "VN string (No AI mention)"}"""
            elif alert_type == "ACCIDENT":
                prompt = """Traffic Check. REAL ACCIDENT (Crash/Fire)? 
                Ignore: Parked, Normal riding. JSON: {"risk": "DANGER"/"SAFE", "reason": "VN string (No AI mention)"}"""
            elif alert_type == "FIRE":
                prompt = """Fire Check. REAL FIRE/SMOKE visible? 
                Ignore: Lights, Sunset. JSON: {"risk": "DANGER"/"SAFE", "reason": "VN string (No AI mention)"}"""
            elif alert_type == "HEALTH":
                prompt = """Medical Emergency Check. 
                Is the person UNCONSCIOUS, COLLAPSED, or HAVING A STROKE on the floor?
                Output JSON: {"risk": "DANGER" (Emergency) or "SAFE" (Normal Activity), "reason": "Explain in Vietnamese"}"""
            else: return

            res = self.client.models.generate_content(model="gemini-flash-latest", contents=[prompt, pil_img])
            
            if res.text:
                match = re.search(r'\{.*\}', res.text, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    is_danger = data.get("risk") == "DANGER"
                    reason = data.get("reason", "Unknown")
                    self.result_signal.emit(is_danger, alert_type, reason, img)
        except Exception as e:
            print(f"Cloud API Error: {e}")

# ==============================================================================
# 4. LOCAL AI GUARD
# ==============================================================================
class LocalObjectGuard:
    def __init__(self):
        self.pose_model = None; self.models = []
        self.back_sub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=False)
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
        
        print("⚡ [INIT] Loading Security Models...")
        
        base_model = "yolov8s"
        ov_model_dir = f"{base_model}_openvino_model"
        use_model = ""
        if os.path.exists(ov_model_dir): use_model = ov_model_dir
        else:
            try:
                temp_model = YOLO(f"{base_model}.pt") 
                temp_model.export(format="openvino") 
                use_model = ov_model_dir
            except: use_model = "yolov8n.pt"

        vehicles_map = {2: "Car", 3: "Motorbike", 5: "Bus", 7: "Truck", 1: "Bike"}
        human_proxies = [0] 

        configs = [
            { 
                "path": use_model, "task": "detect", "dangerous": [], 
                "vehicles": list(vehicles_map.keys()), 
                "human_proxies": human_proxies, "safe": [67, 73],
                "conf": 0.25, "imgsz": 640 
            } 
        ]
        
        if os.path.exists("weapon.pt"):
            try:
                w_model = YOLO("weapon.pt", task="detect")
                weapon_classes = list(w_model.names.keys())
                configs.append({
                    "path": "weapon.pt", "model_obj": w_model, "task": "detect",
                    "dangerous": weapon_classes, "vehicles": [], "safe": [], "human_proxies": [],
                    "conf": 0.55, "imgsz": 640
                })
            except: pass
        
        for cfg in configs:
            try: 
                m = cfg.get("model_obj", YOLO(cfg["path"], task="detect"))
                self.models.append({"m": m, "c": cfg})
            except: pass
            
        try: self.pose_model = YOLO("yolov8n-pose.pt"); self.pose_model.verbose = False
        except: pass
        self.vehicles_map = vehicles_map

    def calculate_iou(self, box1, box2):
        x1 = max(box1[0], box2[0]); y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2]); y2 = min(box1[3], box2[3])
        if x2 < x1 or y2 < y1: return 0.0
        inter = (x2 - x1) * (y2 - y1)
        area1 = (box1[2]-box1[0])*(box1[3]-box1[1])
        area2 = (box2[2]-box2[0])*(box2[3]-box2[1])
        return inter / float(area1 + area2 - inter)

    def is_inside(self, small_box, big_box):
        sx1, sy1, sx2, sy2 = small_box
        bx1, by1, bx2, by2 = big_box
        ix1 = max(sx1, bx1); iy1 = max(sy1, by1)
        ix2 = min(sx2, bx2); iy2 = min(sy2, by2)
        if ix2 < ix1 or iy2 < iy1: return False
        inter_area = (ix2 - ix1) * (iy2 - iy1)
        small_area = (sx2 - sx1) * (sy2 - sy1)
        if small_area > 0 and (inter_area / small_area) > 0.8: return True
        return False

    def check_fire_color(self, frame, motion_mask):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 150, 150]); upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 150, 150]); upper_red2 = np.array([180, 255, 255])
        lower_orange = np.array([11, 150, 150]); upper_orange = np.array([30, 255, 255])
        mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2) | cv2.inRange(hsv, lower_orange, upper_orange)
        dynamic_fire = cv2.bitwise_and(mask, mask, mask=motion_mask)
        return cv2.countNonZero(dynamic_fire) > 1000, dynamic_fire

    def check_fallen(self, kps):
        if len(kps) < 13: return False
        if kps[5][2] > 0.5 and kps[6][2] > 0.5:
            mid_sh_x = (kps[5][0] + kps[6][0]) / 2
            mid_sh_y = (kps[5][1] + kps[6][1]) / 2
        else: return False
        if kps[11][2] > 0.5 and kps[12][2] > 0.5:
            mid_hip_x = (kps[11][0] + kps[12][0]) / 2
            mid_hip_y = (kps[11][1] + kps[12][1]) / 2
        else: return False
        dx = mid_sh_x - mid_hip_x; dy = mid_sh_y - mid_hip_y 
        if abs(dy) < abs(dx) * 0.8: return True
        return False

    def scan(self, frame):
        annotated = frame.copy(); persons_analysis = []
        all_vehicles = [] 
        suspected_threats = []; detected_safe_objects = []
        suspected_crash = False; suspected_fire = False
        h_img, w_img = frame.shape[:2]
        min_object_area = (h_img * w_img) * 0.015 

        mask = self.back_sub.apply(frame)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        motion_boxes = []
        for cnt in contours:
            if cv2.contourArea(cnt) > min_object_area:
                x, y, w, h = cv2.boundingRect(cnt)
                motion_boxes.append([x, y, x+w, y+h])

        for item in self.models:
            conf_t = item["c"].get("conf", 0.25); sz = item["c"].get("imgsz", 640)
            res = item["m"].predict(frame, conf=conf_t, imgsz=sz, verbose=False, iou=0.45)[0]
            for box in res.boxes:
                cls = int(box.cls[0]); label = item["m"].names[cls]
                x1,y1,x2,y2 = map(int, box.xyxy[0]); b_area = (x2-x1)*(y2-y1)

                if "vehicles" in item["c"] and cls in item["c"]["vehicles"]:
                    if b_area > min_object_area:
                        v_name = self.vehicles_map.get(cls, label)
                        all_vehicles.append({"box": [x1,y1,x2,y2], "label": v_name})
                elif "dangerous" in item["c"] and cls in item["c"]["dangerous"]:
                    if b_area > min_object_area:
                        suspected_threats.append({"box": [x1,y1,x2,y2], "label": label})
                elif "safe" in item["c"] and cls in item["c"]["safe"]:
                    detected_safe_objects.append({"box": [x1,y1,x2,y2], "label": label})

        suspected_health = False
        if self.pose_model:
            results = self.pose_model.predict(frame, conf=0.35, verbose=False)
            for result in results:
                if result.keypoints is not None and result.boxes is not None:
                    kps = result.keypoints.data.cpu().numpy() 
                    boxes = result.boxes.xyxy.cpu().numpy()
                    for i, kp in enumerate(kps):
                        box = boxes[i]
                        is_fallen = self.check_fallen(kp)
                        status = "NORMAL"; color = (0, 255, 0)
                        if is_fallen:
                            status = "FALLEN"; color = (0, 0, 255)
                            is_moving = False
                            for m_box in motion_boxes:
                                if self.calculate_iou(box, m_box) > 0.1: is_moving = True; break
                            if not is_moving:
                                status = "UNCONSCIOUS?"; suspected_health = True
                        
                        persons_analysis.append({"box": box, "status": status})
                        cv2.rectangle(annotated, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), color, 2)
                        cv2.putText(annotated, status, (int(box[0]), int(box[1])-10), 0, 0.6, color, 2)

        moving_vehicles = []
        for v in all_vehicles:
            is_moving = False
            for m_box in motion_boxes:
                if self.calculate_iou(v["box"], m_box) > 0.1: is_moving = True; break
            
            bx = v["box"]
            if is_moving:
                moving_vehicles.append(v)
                cv2.rectangle(annotated, (bx[0],bx[1]), (bx[2],bx[3]), (0,255,255), 2)
            else:
                cv2.rectangle(annotated, (bx[0],bx[1]), (bx[2],bx[3]), (100,100,100), 1)

        is_fire, fire_mask_vis = self.check_fire_color(frame, mask)
        if is_fire:
            contours_fire, _ = cv2.findContours(fire_mask_vis, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours_fire:
                if cv2.contourArea(cnt) > 500:
                    x, y, w, h = cv2.boundingRect(cnt)
                    fire_box = [x, y, x+w, y+h]
                    is_fake = False
                    for v in all_vehicles:
                        if self.is_inside(fire_box, v["box"]): is_fake = True; break
                    if not is_fake:
                        for p in persons_analysis:
                            if self.is_inside(fire_box, p["box"]): is_fake = True; break
                    if not is_fake:
                        suspected_fire = True
                        cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 0, 255), 2)

        final_threats = []
        for threat in suspected_threats:
            is_mistake = False
            for safe_obj in detected_safe_objects:
                if self.calculate_iou(threat["box"], safe_obj["box"]) > 0.05: is_mistake = True; break
            if not is_mistake:
                for v in all_vehicles:
                    if self.calculate_iou(threat["box"], v["box"]) > 0.35: is_mistake = True; break
            if not is_mistake:
                final_threats.append(threat["label"])
                bx = threat["box"]
                cv2.rectangle(annotated, (bx[0],bx[1]), (bx[2],bx[3]), (0,165,255), 3)

        for v in moving_vehicles:
            for p in persons_analysis:
                iou = self.calculate_iou(v["box"], p["box"])
                if iou > 0.1: 
                    inter_w = min(v["box"][2], p["box"][2]) - max(v["box"][0], p["box"][0])
                    inter_h = min(v["box"][3], p["box"][3]) - max(v["box"][1], p["box"][1])
                    if inter_w > 0 and inter_h > 0:
                        p_area = (p["box"][2]-p["box"][0])*(p["box"][3]-p["box"][1])
                        if (inter_w * inter_h) / p_area > 0.6: continue 
                if iou > 0.35:
                    suspected_crash = True
                    bx = v["box"]
                    cv2.rectangle(annotated, (bx[0],bx[1]), (bx[2],bx[3]), (0,165,255), 3)

        return list(set(final_threats)), annotated, suspected_crash, suspected_fire, suspected_health

# ==============================================================================
# 5. CONTROL CENTER
# ==============================================================================
class AIWorker(QThread):
    log_signal = Signal(str, str, str)
    frame_signal = Signal(object)
    
    def __init__(self, key):
        super().__init__()
        self.key = key; self.running = True
        self.guard = LocalObjectGuard()
        self.verifier = CloudVerifier(key)
        self.verifier.result_signal.connect(self.handle_verification_result)
        
        self.frame = None
        self.verifying_weapon = False
        self.verifying_crash = False
        self.verifying_fire = False
        self.verifying_health = False
        
        self.last_weapon_check = 0
        self.last_crash_check = 0
        self.last_fire_check = 0
        self.last_health_check = 0
        
        self.fall_counter = 0 
        self.COOLDOWN = 8.0 

    def set_frame(self, f):
        if self.frame is None: self.frame = f

    def handle_verification_result(self, is_danger, alert_type, reason, img):
        if alert_type == "WEAPON": self.verifying_weapon = False
        if alert_type == "ACCIDENT": self.verifying_crash = False
        if alert_type == "FIRE": self.verifying_fire = False
        if alert_type == "HEALTH": self.verifying_health = False
        
        if is_danger:
            self.log_signal.emit("DANGER", "SYSTEM", f"Hệ thống xác nhận: {reason}")
            try:
                b = QBuffer(); b.open(QIODevice.ReadWrite)
                q_img = QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QImage.Format_BGR888)
                q_img.save(b, "JPG", quality=80)
            except: pass
        else:
            self.log_signal.emit("SAFE", "INFO", f"Hệ thống loại trừ: {reason}")

    def run(self):
        while self.running:
            if self.frame is not None:
                img = self.frame.copy(); curr_time = time.time()
                try:
                    threats, drawn, crash_detected, fire_detected, health_issue = self.guard.scan(img)
                    
                    if threats and not self.verifying_weapon:
                        if (curr_time - self.last_weapon_check) > self.COOLDOWN:
                            self.verifying_weapon = True
                            self.last_weapon_check = curr_time
                            self.log_signal.emit("WARNING", "SYSTEM", "Phát hiện VŨ KHÍ. Đang xác minh AI...")
                            self.verifier.verify(img.copy(), "WEAPON")
                        
                    elif crash_detected and not self.verifying_crash:
                        if (curr_time - self.last_crash_check) > self.COOLDOWN:
                            self.verifying_crash = True
                            self.last_crash_check = curr_time
                            self.log_signal.emit("WARNING", "SYSTEM", "Phát hiện TAI NẠN. Đang xác minh AI...")
                            self.verifier.verify(img.copy(), "ACCIDENT")

                    elif fire_detected and not self.verifying_fire:
                         if (curr_time - self.last_fire_check) > self.COOLDOWN:
                            self.verifying_fire = True
                            self.last_fire_check = curr_time
                            self.log_signal.emit("WARNING", "SYSTEM", "Phát hiện CHÁY. Đang xác minh AI...")
                            self.verifier.verify(img.copy(), "FIRE")

                    if health_issue:
                        self.fall_counter += 1
                    else:
                        self.fall_counter = max(0, self.fall_counter - 1)

                    if self.fall_counter > 50: 
                        if not self.verifying_health and (curr_time - self.last_health_check) > self.COOLDOWN:
                            self.verifying_health = True
                            self.last_health_check = curr_time
                            self.log_signal.emit("WARNING", "SYSTEM", "Phát hiện NGƯỜI BẤT TỈNH. Đang xác minh AI...")
                            self.verifier.verify(img.copy(), "HEALTH")
                        self.fall_counter = 0 

                    if any([self.verifying_weapon, self.verifying_crash, self.verifying_fire, self.verifying_health]):
                        cv2.putText(drawn, "CLOUD AI PROCESSING...", (30, 60), 0, 1.2, (0,255,255), 3)

                    self.frame_signal.emit(drawn)
                except Exception as e: print(f"Loop: {e}")
                finally: self.frame = None
            time.sleep(0.02)

    def stop(self): self.running = False; self.wait()

# ==============================================================================
# 6. VIDEO THREAD
# ==============================================================================
class VideoThread(QThread):
    raw_signal = Signal(object)
    def __init__(self, source=""):
        super().__init__(); self.source = source; self.running = True
        self.recording = False; self.writer = None; self.filename = ""; self.fixed_size = (1280, 720)
        if not os.path.exists("evidence"): os.makedirs("evidence")

    def get_stream_url(self):
        if not self.source or self.source == "0": return 0
        if "youtu" in self.source and yt_dlp:
            try:
                ydl_opts = {'format': 'best[ext=mp4]/best', 'quiet': True, 'noplaylist': True, 'socket_timeout': 10, 'extractor_args': {'youtube': {'player_client': ['android', 'web']}}}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl: return ydl.extract_info(self.source, download=False)['url']
            except: return self.source
        return self.source

    def run(self):
        current_src = self.get_stream_url()
        cap = cv2.VideoCapture(current_src, cv2.CAP_FFMPEG) if isinstance(current_src, str) else cv2.VideoCapture(current_src)
        if isinstance(current_src, str): cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        while self.running:
            ret, frame = cap.read()
            if not ret:
                if isinstance(self.source, str) and ("http" in self.source or "youtu" in self.source):
                    cap.release(); time.sleep(2); current_src = self.get_stream_url(); cap = cv2.VideoCapture(current_src, cv2.CAP_FFMPEG); continue
                else: break
            if (frame.shape[1], frame.shape[0]) != self.fixed_size: frame = cv2.resize(frame, self.fixed_size)
            self.raw_signal.emit(frame)
            if self.recording and self.writer: 
                try: self.writer.write(frame)
                except: pass
            time.sleep(0.01)
        cap.release()

    def start_rec(self, cat):
        if not self.recording:
            self.filename = f"evidence/{cat}_{datetime.now().strftime('%H%M%S')}.avi"
            self.writer = cv2.VideoWriter(self.filename, cv2.VideoWriter_fourcc(*'MJPG'), 20.0, self.fixed_size)
            self.recording = True
    def stop_rec(self): self.recording = False; self.writer.release() if self.writer else None; return self.filename
    def stop(self): self.running = False; self.stop_rec(); self.wait()

# ==============================================================================
# 7. MAIN APP (MODERN UI)
# ==============================================================================
class GuardianApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GUARDIAN SECURITY AI | PRO EDITION")
        self.resize(1400, 850)
        self.setStyleSheet(MODERN_THEME)
        self.voice = pyttsx3.init()
        self.cam = None; self.ai = None
        self.setup_ui(); self.load_config()

    def setup_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # --- LEFT PANEL: VIDEO & STATUS ---
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        # Status HUD
        self.lbl_status = QLabel("● SYSTEM READY")
        self.lbl_status.setObjectName("status_lbl")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: #7aa2f7; border: 1px solid #7aa2f7;")
        
        # Video View
        self.view = QLabel()
        self.view.setObjectName("video_frame")
        self.view.setScaledContents(True)
        self.view.setMinimumSize(960, 540)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        left_panel.addWidget(self.lbl_status)
        left_panel.addWidget(self.view, stretch=1)
        
        # --- RIGHT PANEL: CONTROLS & LOGS ---
        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)
        
        # Header Box
        header_lbl = QLabel("COMMAND CENTER")
        header_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header_lbl.setStyleSheet("color: #fff; margin-bottom: 5px;")
        right_panel.addWidget(header_lbl)

        # Source Selection
        grp_src = QGroupBox("VIDEO SOURCE")
        l_src = QVBoxLayout()
        self.cbo = QComboBox()
        self.cbo.addItems(["📷 Live Webcam (Default)", "🌐 RTSP / HTTP URL", "▶️ YouTube / Video File"])
        self.txt_url = QLineEdit(); self.txt_url.setPlaceholderText("Enter stream URL or file path...")
        l_src.addWidget(self.cbo); l_src.addWidget(self.txt_url)
        grp_src.setLayout(l_src)
        
        # Configuration
        grp_cfg = QGroupBox("SYSTEM CONFIG")
        l_cfg = QVBoxLayout()
        self.txt_key = QLineEdit(); self.txt_key.setPlaceholderText("🔑 Gemini Cloud API Key")
        self.txt_key.setEchoMode(QLineEdit.Password)
        self.txt_tok = QLineEdit(); self.txt_tok.setPlaceholderText("🤖 Telegram Bot Token")
        self.txt_cid = QLineEdit(); self.txt_cid.setPlaceholderText("🆔 Chat ID")
        l_cfg.addWidget(self.txt_key); l_cfg.addWidget(self.txt_tok); l_cfg.addWidget(self.txt_cid)
        grp_cfg.setLayout(l_cfg)

        # Action Buttons
        self.btn = QPushButton("ACTIVATE SYSTEM")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setFixedHeight(50)
        self.btn.clicked.connect(self.toggle)

        # Log Table
        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["TIME", "LEVEL", "MESSAGE"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setShowGrid(False)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)

        # Adding to Right Layout
        right_panel.addWidget(grp_src)
        right_panel.addWidget(grp_cfg)
        right_panel.addWidget(self.btn)
        right_panel.addWidget(QLabel("EVENT LOGS:"))
        right_panel.addWidget(self.tbl, stretch=1)

        # Add Layouts to Main
        main_layout.addLayout(left_panel, stretch=7)
        main_layout.addLayout(right_panel, stretch=3)

    def toggle(self):
        if not self.cam:
            self.save_config()
            src = "0" if self.cbo.currentIndex() == 0 else self.txt_url.text()
            if not src: return
            
            self.btn.setText("STOP SURVEILLANCE")
            self.btn.setObjectName("stop_btn")
            self.btn.setStyleSheet(MODERN_THEME) # Re-apply style for ID change
            
            self.lbl_status.setText("● SYSTEM ACTIVE - SCANNING...")
            self.lbl_status.setStyleSheet("color: #9ece6a; background-color: #1a1b26; border: 1px solid #9ece6a;")
            
            self.cam = VideoThread(src)
            self.ai = AIWorker(self.txt_key.text())
            
            self.cam.raw_signal.connect(self.ai.set_frame)
            self.ai.frame_signal.connect(self.update_view)
            self.ai.log_signal.connect(self.handle_log)
            
            self.cam.start(); self.ai.start()
        else:
            self.cam.stop(); self.ai.stop(); self.cam = None; self.ai = None
            self.btn.setText("ACTIVATE SYSTEM")
            self.btn.setObjectName("")
            self.btn.setStyleSheet(MODERN_THEME)
            
            self.lbl_status.setText("● SYSTEM STANDBY")
            self.lbl_status.setStyleSheet("color: #7aa2f7; background-color: #1a1b26; border: 1px solid #7aa2f7;")
            
            # Clear View
            self.view.setPixmap(QPixmap())
            self.view.setText("NO SIGNAL")
            self.view.setAlignment(Qt.AlignCenter)

    def handle_log(self, risk, cat, msg):
        row_color = "#c0caf5"
        risk_color = "#7aa2f7"
        
        if risk == "WARNING": 
            risk_color = "#e0af68" 
            self.lbl_status.setText(f"⚠ VERIFYING THREAT..."); 
            self.lbl_status.setStyleSheet(f"color: #1a1b26; background-color: {risk_color}; border: none;")
        elif risk == "DANGER":
            risk_color = "#f7768e" 
            self.lbl_status.setText(f"🚨 DANGER DETECTED"); 
            self.lbl_status.setStyleSheet(f"color: #fff; background-color: {risk_color}; font-weight: bold; border: 2px solid #fff;")
            
            self.voice.say(f"Alert. Danger detected."); self.voice.runAndWait()
            if self.view.pixmap():
                b = QBuffer(); b.open(QIODevice.ReadWrite)
                self.view.pixmap().save(b, "JPG")
                telegram_worker(self.txt_tok.text(), self.txt_cid.text(), f"🚨 {msg}", b.data())
            if self.cam: self.cam.start_rec(cat)
        elif risk == "SAFE":
            risk_color = "#9ece6a" 
            self.lbl_status.setText("● AREA SECURE"); 
            self.lbl_status.setStyleSheet(f"color: {risk_color}; background-color: #1a1b26; border: 1px solid {risk_color}")

        self.tbl.insertRow(0)
        time_item = QTableWidgetItem(datetime.now().strftime("%H:%M:%S"))
        risk_item = QTableWidgetItem(risk)
        msg_item = QTableWidgetItem(msg)
        
        risk_item.setForeground(QColor(risk_color))
        risk_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        self.tbl.setItem(0, 0, time_item)
        self.tbl.setItem(0, 1, risk_item)
        self.tbl.setItem(0, 2, msg_item)

    def update_view(self, cv_img):
        h, w, c = cv_img.shape
        # Create QImage
        qimg = QImage(cv_img.data, w, h, c*w, QImage.Format_RGB888).rgbSwapped()
        self.view.setPixmap(QPixmap.fromImage(qimg))

    def load_config(self):
        try: d = json.load(open("config.json")); self.txt_key.setText(d.get("k")); self.txt_tok.setText(d.get("t")); self.txt_cid.setText(d.get("c"))
        except: pass
    def save_config(self): json.dump({"k": self.txt_key.text(), "t": self.txt_tok.text(), "c": self.txt_cid.text()}, open("config.json", "w"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Set Fusion Theme for consistent OS look before applying Stylesheet
    app.setStyle("Fusion") 
    win = GuardianApp()
    win.show()
    sys.exit(app.exec())