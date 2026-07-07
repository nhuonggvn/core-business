import json
import time
import ssl
import paho.mqtt.client as mqtt

MQTT_BROKER = "26.79.10.201"
MQTT_PORT = 1883
MQTT_USERNAME = ""
MQTT_PASSWORD = ""

TOPIC_SENSOR = "smart-campus/events/sensor"
TOPIC_ACCESS = "smart-campus/events/access"
TOPIC_CAMERA = "smart-campus/events/camera"

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected to HiveMQ with result code {rc}")
    # Đăng ký nhận Alert ngược lại từ Core Business để kiểm tra
    client.subscribe("smart-campus/events/alert")
    client.subscribe("smart-campus/events/alerts")
    print("Listening for Core Business Alerts on smart-campus/events/alert...\n")

def on_message(client, userdata, msg):
    print(f"\n[ALERT RECEIVED] Topic: {msg.topic}")
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        print(json.dumps(data, indent=4, ensure_ascii=False))
    except Exception as e:
        print(f"Error parsing alert: {e}")

client = mqtt.Client(protocol=mqtt.MQTTv5)
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
# client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
client.on_connect = on_connect
client.on_message = on_message

print("Connecting to HiveMQ Cloud...")
client.connect(MQTT_BROKER, MQTT_PORT)
client.loop_start()

time.sleep(2)  # Chờ kết nối ổn định

print("\n--- BẮT ĐẦU CHẠY THỬ CÁC KỊCH BẢN ---")

# Kịch bản 1: Cảnh báo cảm biến nguy hiểm (Khói vượt ngưỡng)
print("\n[Kịch bản 1] Gửi sự kiện Sensor Danger (Phát hiện khói)...")
sensor_payload = {
    "event_type": "sensor.reading.processed",
    "source_service": "team-iot",
    "raw_event_id": "raw-sensor-999",
    "device_id": "esp32-sensor-smoke",
    "location": "Phòng thực hành Lab A101",
    "temperature_c": 45.0,
    "humidity_percent": 90.0,
    "motion_detected": False,
    "co2_ppm": 2000,
    "smoke_ppm": 1.5,
    "battery_percent": 80,
    "status": "danger",
    "alert_level": "high",
    "reason": "smoke_too_high"
}
client.publish(TOPIC_SENSOR, json.dumps(sensor_payload), qos=1)
time.sleep(3)

# Kịch bản 2: Bruteforce quẹt thẻ lỗi 3 lần
print("\n[Kịch bản 2] Gửi 3 lần quẹt thẻ thất bại liên tiếp của UID USER-999...")
access_payload = {
    "event_type": "access.swipe.processed",
    "source_service": "team-gate",
    "raw_event_id": "raw-rfid-777",
    "uid": "USER-999",
    "student_id": None,
    "full_name": None,
    "class_name": None,
    "door_id": "gate-main",
    "location": "Main Entrance",
    "direction": "in",
    "access_result": "denied",
    "reason": "uid_not_found",
    "cardId": "CARD-999999"
}
for i in range(1, 4):
    print(f"Gửi lần thứ {i}...")
    client.publish(TOPIC_ACCESS, json.dumps(access_payload), qos=1)
    time.sleep(1)
time.sleep(3)

# Kịch bản 3: Camera phát hiện người lạ ngoài giờ (02:15:00 sáng)
print("\n[Kịch bản 3] Gửi sự kiện Camera phát hiện chuyển động ngoài giờ...")
camera_payload = {
    "request_id": "cam-req-101",
    "event_type": "camera.motion.triggered",
    "source_service": "team-camera",
    "camera_id": "camera-gate-b",
    "timestamp": "2026-07-07T02:15:00Z",  # 2:15 AM (ngoài khung giờ 6:00 - 22:00)
    "location": "Main Entrance",
    "motion_detected": True,
    "motion_score": 0.95,
    "snapshot_url": "http://example.com/snapshot.jpg"
}
client.publish(TOPIC_CAMERA, json.dumps(camera_payload), qos=1)
time.sleep(22)

client.loop_stop()
client.disconnect()
print("\n--- KẾT THÚC THỬ NGHIỆM ---")
