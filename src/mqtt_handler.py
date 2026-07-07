import os
import json
import logging
import asyncio
import ssl
import paho.mqtt.client as mqtt

from event_handlers import handle_sensor_event, handle_access_event, handle_camera_event
from websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
AI_VISION_URL = os.getenv("AI_VISION_URL", "http://localhost:9000")

TOPIC_SENSOR = "smart-campus/events/sensor"
TOPIC_ACCESS = "smart-campus/events/access"
TOPIC_CAMERA = "smart-campus/events/camera"
TOPIC_ALERT  = "smart-campus/events/alert"
TOPIC_POLICY = "smart-campus/events/policy"

_mqtt_client = None
_event_loop  = None


def _broadcast(payload: dict) -> None:
    """
    Ham tien ich noi bo: broadcast payload JSON xuong tat ca WebSocket client.
    An toan khi goi tu thread cua paho-mqtt (khac thread cua asyncio event loop).
    """
    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast(payload), _event_loop
        )


def publish_alert(alert: dict) -> None:
    if _mqtt_client and _mqtt_client.is_connected():
        raw = json.dumps(alert)
        _mqtt_client.publish(TOPIC_ALERT, raw)
        # Publish dong thoi len topic co chu s cho Analytics (A5)
        _mqtt_client.publish("smart-campus/events/alerts", raw)
        _mqtt_client.publish(TOPIC_POLICY, raw)
        logger.info(f"[MQTT] Published alert: {alert.get('alert_type')}")

    # Broadcast alert len Dashboard
    _broadcast({"type": "alert", "data": alert})


def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    logger.info(f"[MQTT] Connected with result code {rc}")
    client.subscribe([
        (TOPIC_SENSOR, 0),
        (TOPIC_ACCESS, 0),
        (TOPIC_CAMERA, 0),
    ])


def on_mqtt_message(client, userdata, msg):
    # Khai bao global o dau ham, truoc moi thao tac su dung bien nay
    global _event_loop

    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except Exception:
        logger.warning(f"[MQTT] Bad payload on topic {msg.topic}")
        return

    logger.debug(f"[MQTT] Received on {msg.topic}: {data}")

    # Broadcast raw event len Dashboard ngay khi nhan duoc, truoc khi xu ly logic
    _broadcast({"type": "event", "topic": msg.topic, "data": data})

    alert = None
    if msg.topic == TOPIC_SENSOR:
        alert = handle_sensor_event(data)
    elif msg.topic == TOPIC_ACCESS:
        alert = handle_access_event(data)
    elif msg.topic == TOPIC_CAMERA:
        # handle_camera_event la ham async (goi httpx), can dat vao event loop chinh
        if _event_loop and _event_loop.is_running():
            asyncio.run_coroutine_threadsafe(_process_camera_event(data), _event_loop)
        else:
            logger.error("[MQTT] Event loop not running for camera event")
        return

    if alert:
        publish_alert(alert)


async def _process_camera_event(data: dict) -> None:
    alert = await handle_camera_event(data, AI_VISION_URL)
    if alert:
        publish_alert(alert)


def start_mqtt_client(loop: asyncio.AbstractEventLoop) -> mqtt.Client:
    global _mqtt_client, _event_loop
    _event_loop = loop

    # Khoi tao MQTT client ho tro SSL/TLS khi ket noi dam may
    client = mqtt.Client(protocol=mqtt.MQTTv5)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    if MQTT_PORT == 8883:
        client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

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


def get_mqtt_client() -> mqtt.Client:
    return _mqtt_client
