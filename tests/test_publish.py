import os
import json
import time
import ssl
import paho.mqtt.client as mqtt

# Doc file .env thu cong de tranh loi thieu thu vien python-dotenv
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(dotenv_path):
    with open(dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip()

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

TOPIC_ACCESS = "smart-campus/events/access"

def test_bruteforce_flow():
    # Khoi tao MQTT client ho tro SSL/TLS khi ket noi HiveMQ Cloud
    client = mqtt.Client(protocol=mqtt.MQTTv5)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    if MQTT_PORT == 8883:
        client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

    print(f"[Test] Connecting to broker {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"[Error] Failed to connect: {e}")
        return

    # Gia lap 3 lan quet the that bai lien tiep cua cung 1 the tai cung 1 cua
    # de kich hoat thuat toan Bruteforce tren Core Business
    card_id = "CARD-999999"
    gate_id = "GATE-99"
    location = "lab-a101"

    print(f"[Test] Starting to publish 3 denied events for {card_id}...")
    for i in range(3):
        payload = {
            "uid": card_id,
            "access_result": "denied",
            "door_id": gate_id,
            "location": location,
            "direction": "IN",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        raw_message = json.dumps(payload)
        client.publish(TOPIC_ACCESS, raw_message)
        print(f"[Published {i+1}/3] {raw_message}")
        time.sleep(1.5) # Cho giua cac lan quet the de he thong ghi nhan dung sliding window

    time.sleep(2)
    client.loop_stop()
    client.disconnect()
    print("[Test] Finished publishing test events.")

if __name__ == "__main__":
    test_bruteforce_flow()
