🛡️ Guardian Security AI - Pro Edition
Guardian Security AI is a professional-grade intelligent surveillance system. It leverages YOLOv8 deep learning models for real-time object detection and integrates Cloud Generative AI for secondary verification of critical events (Weapons, Accidents, Fire, Falls), significantly reducing false alarms.

✨ Key Features
🔍 Real-time Detection: Instantly identifies persons, vehicles (cars, bikes, trucks), and potential threats with high accuracy.

🧠 Behavior Analysis:

Fall Detection: Uses Pose Estimation to detect collapsed individuals (e.g., stroke or accidents).

Crash Detection: Analyzes interactions between vehicles and pedestrians/riders.

☁️ Cloud Verification: When a threat is detected, the system sends a snapshot to Cloud AI to "double-check" the context (e.g., distinguishing a toy gun from a real weapon) before alerting.

🔥 Multi-Channel Alerts:

Telegram: Sends instant notifications with photos/videos of the incident.

Audio: Text-to-Speech voice warnings on-site.

Evidence: Automatically records video clips to the evidence/ folder.

🚀 Performance: Optimized with OpenVINO for faster inference on standard hardware.

🛠️ Installation
1. Prerequisites
Ensure you have Python 3.9 or higher installed.

2. Install Dependencies
Open your terminal in the project directory and run:

Bash

pip install opencv-python ultralytics PySide6 google-genai requests pyttsx3 yt-dlp Pillow numpy
(Optional) For Face ID features (if using known_faces):

Bash

pip install face_recognition
3. Model Preparation
The system requires specific model files. Based on your structure, ensure these files exist in the root directory:

yolov8s.pt (Standard detection)

yolov8n-pose.pt (Pose/Fall detection)

weapon.pt (Custom weapon detection model)

🚀 Usage Guide
Step 1: Launch the Application
Run the main script:

Bash

python smart_guardian.py
Step 2: System Configuration
On the right panel of the GUI, enter the required credentials:

Cloud API Key: Required for the AI Verification feature (Get it from Google AI Studio).

Telegram Bot Token & Chat ID: Required for receiving mobile alerts.

💡 Note: Settings are automatically saved to config.json.

Step 3: Select Video Source
Webcam: Select "Live Webcam" or input 0.

IP Camera: Input RTSP URL (e.g., rtsp://admin:12345@192.168.1.50...).

Video File: Path to a local video or a YouTube URL.

Step 4: Activate
Click ACTIVATE SYSTEM to begin surveillance.

📂 Project Structure
This structure reflects the current development environment:

Plaintext

Guardian-Security/
├── known_faces/                # Database for Face Recognition images
├── yolov8s_openvino_model/     # Optimized OpenVINO model folder
├── evidence/                   # Auto-saved videos of detected incidents
├── smart_guardian.py           # Main application entry point
├── guardian_logs.db            # SQLite database for activity logs
├── config.json                 # Configuration file (API keys, Tokens)
├── weapon.pt                   # Custom trained model for Weapon Detection
├── weapons.pt                  # (Backup) Custom model
├── yolov8n-pose.pt             # Pose Estimation model (Fall detection)
├── yolov8n.pt                  # YOLOv8 Nano model (Lightweight)
├── yolov8s.pt                  # YOLOv8 Small model (Standard)
├── requirements.txt            # Python dependencies
└── README.md                   # Documentation
👥 Credits & Developers
This project is proudly developed and maintained by:

Lead Developer: Nguyễn Đức Mạnh

Assistant Developer: Nguyễn Văn An

⚠️ Disclaimer
This software is developed for educational and research purposes. The developers are not responsible for any liability or damage caused by the use of this software. The accuracy of the AI depends on environmental conditions and hardware performance.
