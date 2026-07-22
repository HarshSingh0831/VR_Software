<<<<<<< HEAD
# Adaptive VR Learning System

Adaptive smartphone-VR learning prototype for a DC motor lesson. The system combines:

- Raspberry Pi 4 and DFRobot ESP32-S3 upper-face camera integration
- CNN-based upper-face expression inference
- continuous English, Hindi, and Hinglish voice commands
- eight timed supporting videos with understanding verification
- seven midpoint and seven final quiz questions
- synchronized laptop and smartphone Streamlit dashboards
- multimodal camera, speech, quiz, help, and replay analytics
- Unity/VR communication utilities

## Start here

Read [the project handoff](output/pdf/Adaptive_VR_Project_Handoff.pdf) for the architecture, completed work, local asset requirements, current limitations, and remaining roadmap.

The main learning dashboard is `learning_app.py`. Content and quiz definitions are in `config/learning_content.json` and `config/learning_quiz.json`.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m streamlit run learning_app.py
```

Large video files, Vosk models, trained weights, recordings, certificates, credentials, and hardware secrets are intentionally excluded from Git. See the handoff PDF for their expected local locations and provisioning steps.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
```
=======
# VR Voice Control System

A modular voice-controlled Virtual Reality software platform that enables hands-free interaction with VR applications using Raspberry Pi, ESP32, and Python.

---

## Features

- 🎤 Real-time voice command recognition
- 🥽 VR application control
- 📡 ESP32 communication
- 🍓 Raspberry Pi edge processing
- 🖥️ Streamlit monitoring dashboard
- ⚡ Low latency command execution
- 🔌 Modular architecture
- 📈 Real-time logs and diagnostics

---

## System Architecture

```
Voice Input
      │
      ▼
Speech Recognition
      │
      ▼
Command Processing
      │
      ├────────► ESP32
      │
      ├────────► Raspberry Pi
      │
      ▼
VR Application
```

---

## Project Structure

```
config/
docs/
firmware/
host/
models/
raspberry-pi/
scripts/
tests/
streamlit_app.py
```

---

## Technologies

- Python
- Streamlit
- Raspberry Pi
- ESP32
- Speech Recognition
- PySerial
- WebSocket
- MQTT (optional)

---

## Installation

```bash
git clone https://github.com/USERNAME/VR-Voice-Control-System.git

cd VR-Voice-Control-System

pip install -r requirements.txt

streamlit run streamlit_app.py
```

---

## Hardware

- Raspberry Pi
- ESP32
- USB Microphone
- VR Headset
- Speakers

---

## Future Improvements

- Gesture Recognition
- Eye Tracking
- Facial Expression Detection
- Local LLM Integration
- Emotion Recognition
- AI Assistant Mode

---

## License

MIT
>>>>>>> 152293acfec66f24026926bb8f824b0a9f4e1524
