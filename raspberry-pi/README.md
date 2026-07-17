# Adaptive VR Raspberry Pi setup

This Raspberry Pi is prepared as the lower-face camera and sensor node.

## Image configuration

- OS: Raspberry Pi OS Lite 64-bit
- Hostname: `adaptive-vr-pi`
- User: `vrpi`
- Time zone: `Asia/Kolkata`
- Wi-Fi: `Vivo v40` on 2.4 GHz
- Remote access: SSH enabled
- Interfaces: I2C and SPI enabled
- Camera stack: modern `libcamera` / `rpicam`

## First boot

1. Insert the flashed microSD card into the powered-off Raspberry Pi.
2. Start the `Vivo v40` hotspot.
3. Power the Raspberry Pi with a suitable power supply.
4. Allow up to 15 minutes for the initial boot, package installation, and
   network connection.
5. From a Windows PowerShell window on the same hotspot, connect with:

   ```powershell
   ssh vrpi@adaptive-vr-pi.local
   ```

6. Change the temporary password immediately:

   ```bash
   passwd
   ```

If the `.local` name does not resolve, use the Raspberry Pi IP address shown
in the phone's connected-device list:

```powershell
ssh vrpi@PI_IP_ADDRESS
```

## Camera check after connecting the hardware

On the Raspberry Pi:

```bash
rpicam-hello --list-cameras
rpicam-still -o camera-test.jpg
```

## Lower-face service

The production lower-face node is `lower_face_node.py`. It captures the OV5647
camera at 640x480, converts frames to grayscale, extracts mouth-region quality,
motion, mouth-opening, speaking-motion, and yawn signals, and sends protocol-v1
WebSocket packets to the central receiver on the same Pi at 10 Hz.

The systemd unit `adaptive-vr-lower-face.service` runs the node automatically
after networking becomes available. `adaptive-vr-receiver.service` accepts the
Pi lower-face stream and the ESP32 upper-face stream on TCP port 8765.

## Calibration recording

Both cameras send lossless 320x240 grayscale calibration frames at 10 FPS while
their normal 10 Hz feature packets continue. Frames are discarded unless a
session is active.

From the Windows project directory:

```powershell
scripts\start_calibration_session.ps1 -Participant P001 -Label focused
scripts\set_calibration_label.ps1 -Label thinking
scripts\set_calibration_label.ps1 -Label confused
scripts\stop_calibration_session.ps1
scripts\calibration_status.ps1
```

Download a completed session with:

```powershell
scripts\download_calibration_session.ps1 -Session P001_YYYYMMDD_HHMMSS
```

Each session contains lossless PGM images under `images/upper_face` and
`images/lower_face`, plus `frames.jsonl` with participant, label, role,
sequence, device timestamp, receiver timestamp, and dimensions.

The initial provisioning logs are:

```text
/var/log/adaptive-vr-firstrun.log
/var/log/adaptive-vr-bootstrap.log
```
