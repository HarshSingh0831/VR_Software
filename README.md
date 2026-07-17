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
