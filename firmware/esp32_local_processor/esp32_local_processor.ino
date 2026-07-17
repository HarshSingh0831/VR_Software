#include <Arduino.h>
#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include "secrets.h"

// Build exactly one role per device.
#define DEVICE_ROLE_UPPER
// #define DEVICE_ROLE_LOWER

#if defined(DEVICE_ROLE_UPPER) && defined(DEVICE_ROLE_LOWER)
#error "Select only one device role"
#endif

#if !defined(DEVICE_ROLE_UPPER) && !defined(DEVICE_ROLE_LOWER)
#error "Select a device role"
#endif

#ifdef DEVICE_ROLE_UPPER
static const char *DEVICE_ROLE = "upper_face";
static const char *DEVICE_ID = "upper-face-01";
#else
static const char *DEVICE_ROLE = "lower_face";
static const char *DEVICE_ID = "lower-face-01";
#endif
static constexpr uint32_t SEND_INTERVAL_MS = 100;  // 10 Hz
static constexpr uint32_t CALIBRATION_FRAME_INTERVAL = 1;  // 10 FPS at the 10 Hz send rate
static constexpr uint8_t SAMPLE_STEP = 8;
static constexpr size_t CALIBRATION_HEADER_SIZE = 21;

WebSocketsClient websocket;
uint32_t sequenceNumber = 0;
uint32_t lastSendMs = 0;
float previousMean = NAN;

// DFR1154 OV3660 camera pins from the official DFRobot example.
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 5
#define SIOD_GPIO_NUM 8
#define SIOC_GPIO_NUM 9
#define Y9_GPIO_NUM 4
#define Y8_GPIO_NUM 6
#define Y7_GPIO_NUM 7
#define Y6_GPIO_NUM 14
#define Y5_GPIO_NUM 17
#define Y4_GPIO_NUM 21
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 16
#define VSYNC_GPIO_NUM 1
#define HREF_GPIO_NUM 2
#define PCLK_GPIO_NUM 15

struct ImageMetrics {
  float brightness;
  float motion;
  bool valid;
};

bool initializeCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_GRAYSCALE;
  config.frame_size = FRAMESIZE_QVGA;
  config.fb_count = 2;
  config.grab_mode = CAMERA_GRAB_LATEST;
  const esp_err_t result = esp_camera_init(&config);
  if (result != ESP_OK) {
    Serial.printf("Camera initialization failed: 0x%x\n", result);
    return false;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  if (sensor && sensor->id.PID == OV3660_PID) {
    sensor->set_vflip(sensor, 1);
    sensor->set_brightness(sensor, 1);
    sensor->set_saturation(sensor, -2);
  }
  Serial.printf("Camera initialized, sensor PID: 0x%x\n", sensor ? sensor->id.PID : 0);
  return true;
}

ImageMetrics calculateImageMetrics(const camera_fb_t *frame) {
  if (!frame || !frame->buf || frame->len == 0) return {0.0f, 0.0f, false};
  uint64_t sum = 0;
  uint32_t samples = 0;
  for (size_t i = 0; i < frame->len; i += SAMPLE_STEP) {
    sum += frame->buf[i];
    samples++;
  }
  float mean = samples ? static_cast<float>(sum) / samples : 0.0f;
  float brightness = mean / 255.0f;
  float motion = isnan(previousMean) ? 0.0f : min(1.0f, fabsf(mean - previousMean) / 64.0f);
  previousMean = mean;
  return {brightness, motion, true};
}

void addUncalibratedFeatures(JsonObject features, float motion) {
#ifdef DEVICE_ROLE_UPPER
  features["left_eye_open"] = nullptr;
  features["right_eye_open"] = nullptr;
  features["blink"] = nullptr;
  features["gaze_x"] = nullptr;
  features["gaze_y"] = nullptr;
  features["eyebrow_raise"] = nullptr;
  features["motion"] = motion;
#else
  features["mouth_open"] = nullptr;
  features["lip_corner_raise"] = nullptr;
  features["lip_compression"] = nullptr;
  features["jaw_motion"] = motion;
  features["speaking_motion"] = nullptr;
  features["yawn"] = nullptr;
#endif
}

void sendFeaturePacket(const ImageMetrics &metrics) {
  JsonDocument document;
  document["protocol_version"] = 1;
  document["device"] = DEVICE_ROLE;
  document["device_id"] = DEVICE_ID;
  document["timestamp_ms"] = millis();
  document["sequence"] = sequenceNumber++;

  JsonObject features = document["features"].to<JsonObject>();
  addUncalibratedFeatures(features, metrics.motion);

  JsonObject quality = document["quality"].to<JsonObject>();
  quality["brightness"] = metrics.brightness;
  quality["region_valid"] = metrics.valid;
  quality["confidence"] = metrics.valid ? 0.25f : 0.0f;

  String payload;
  serializeJson(document, payload);
  websocket.sendTXT(payload);
}

void sendCalibrationFrame(const camera_fb_t *frame, uint32_t sequence) {
  if (!frame || !frame->buf || frame->len != frame->width * frame->height) return;
  const size_t packetLength = CALIBRATION_HEADER_SIZE + frame->len;
  uint8_t *packet = static_cast<uint8_t *>(
      heap_caps_malloc(packetLength, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (!packet) return;

  memcpy(packet, "AVF1", 4);
  packet[4] = 0;  // upper_face
  const uint16_t width = frame->width;
  const uint16_t height = frame->height;
  const uint64_t timestamp = millis();
  memcpy(packet + 5, &width, sizeof(width));
  memcpy(packet + 7, &height, sizeof(height));
  memcpy(packet + 9, &sequence, sizeof(sequence));
  memcpy(packet + 13, &timestamp, sizeof(timestamp));
  memcpy(packet + CALIBRATION_HEADER_SIZE, frame->buf, frame->len);
  websocket.sendBIN(packet, packetLength);
  heap_caps_free(packet);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Connecting to Wi-Fi: %s\n", WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print('.');
  }
  Serial.printf("\nWi-Fi connected. IP: %s\n", WiFi.localIP().toString().c_str());
}

void setup() {
  Serial.begin(115200);
  if (!initializeCamera()) {
    while (true) delay(1000);
  }
  connectWiFi();
  websocket.begin(HOST_IP, HOST_PORT, HOST_PATH);
  Serial.printf("WebSocket target: ws://%s:%u%s\n", HOST_IP, HOST_PORT, HOST_PATH);
  websocket.setReconnectInterval(2000);
  websocket.enableHeartbeat(10000, 3000, 2);
}

void loop() {
  websocket.loop();
  const uint32_t now = millis();
  if (now - lastSendMs < SEND_INTERVAL_MS) return;
  lastSendMs = now;

  camera_fb_t *frame = esp_camera_fb_get();
  ImageMetrics metrics = calculateImageMetrics(frame);
  const uint32_t currentSequence = sequenceNumber;
  sendFeaturePacket(metrics);
  if (frame && currentSequence % CALIBRATION_FRAME_INTERVAL == 0) {
    sendCalibrationFrame(frame, currentSequence);
  }
  if (frame) esp_camera_fb_return(frame);
}
