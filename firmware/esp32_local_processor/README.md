# ESP32-S3 local face processor

This Arduino firmware scaffold targets the DFRobot DFR1154 ESP32-S3 AI Camera.

Install these Arduino libraries:

- ArduinoJson
- WebSockets by Markus Sattler

Copy `secrets.example.h` to `secrets.h`, then set Wi-Fi and host values. Build one firmware with `DEVICE_ROLE_UPPER` and another with `DEVICE_ROLE_LOWER`.

The current implementation deliberately reports uncalibrated semantic features as `null`. Brightness and frame-motion measurements are real. Eye/mouth measurements must be implemented after collecting labeled headset frames and fixing the camera ROIs.

