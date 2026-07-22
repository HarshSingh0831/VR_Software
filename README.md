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
