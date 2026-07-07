import os
import json
import logging
import asyncio
import paho.mqtt.client as mqtt

from event_handlers import handle_sensor_event, handle_access_event, handle_camera_event

logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
AI_VISION_URL = os.getenv("AI_VISION_URL", "http://localhost:9000")

TOPIC_SENSOR = "smart-campus/events/sensor"
TOPIC_ACCESS = "smart-campus/events/access"
TOPIC_CAMERA = "smart-campus/events/camera"
TOPIC_ALERT = "smart-campus/events/alert"
TOPIC_POLICY = "smart-campus/events/policy"

_mqtt_client = None
_event_loop = None

def publish_alert(alert: dict) -> None:
    if _mqtt_client and _mqtt_client.is_connected():
        payload = json.dumps(alert)
        _mqtt_client.publish(TOPIC_ALERT, payload)
        _mqtt_client.publish(TOPIC_POLICY, payload)
        logger.info(f"[MQTT] Published alert: {alert.get('alert_type')}")

def on_mqtt_connect(client, userdata, flags, rc):
    logger.info(f"[MQTT] Connected with result code {rc}")
    client.subscribe([
        (TOPIC_SENSOR, 0),
        (TOPIC_ACCESS, 0),
        (TOPIC_CAMERA, 0),
    ])

def on_mqtt_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except Exception:
        logger.warning(f"[MQTT] Bad payload on topic {msg.topic}")
        return

    logger.debug(f"[MQTT] Received on {msg.topic}: {data}")

    alert = None
    if msg.topic == TOPIC_SENSOR:
        alert = handle_sensor_event(data)
    elif msg.topic == TOPIC_ACCESS:
        alert = handle_access_event(data)
    elif msg.topic == TOPIC_CAMERA:
        # handle_camera_event là hàm async (do gọi htppx), cần đặt nó vào event loop chính
        global _event_loop
        if _event_loop and _event_loop.is_running():
            asyncio.run_coroutine_threadsafe(_process_camera_event(data), _event_loop)
        else:
            logger.error("[MQTT] Event loop not running for camera event")
        return

    if alert:
        publish_alert(alert)

async def _process_camera_event(data: dict):
    alert = await handle_camera_event(data, AI_VISION_URL)
    if alert:
        publish_alert(alert)

def start_mqtt_client(loop: asyncio.AbstractEventLoop) -> mqtt.Client:
    global _mqtt_client, _event_loop
    _event_loop = loop
    
    client = mqtt.Client()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        _mqtt_client = client
        logger.info(f"[MQTT] Started client connecting to {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        logger.error(f"[MQTT] Failed to connect: {e}")
        
    return client

def stop_mqtt_client() -> None:
    global _mqtt_client
    if _mqtt_client:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
            logger.info("[MQTT] Stopped client")
        except Exception:
            pass
        _mqtt_client = None

def get_mqtt_client():
    return _mqtt_client
