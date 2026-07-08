import os
import json
import logging
import asyncio
import ssl
import uuid
import threading
import requests
import paho.mqtt.client as mqtt

from event_handlers import handle_sensor_event, handle_access_event, handle_camera_event
from websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
AI_VISION_URL = os.getenv("AI_VISION_URL", "http://localhost:9000")
# URL A7 de gui canh bao nguon tu MQTT (bruteforce, fire, camera)
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://26.19.238.62:8000")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")

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


def _send_alert_to_a7(alert: dict) -> None:
    """
    Gui alert dict tu event_handlers sang A7 qua REST API.
    Chuyen doi format noi bo thanh AlertEventPayload chuan cua A7.
    Phuong thuc nay duoc goi tu mqtt_handler, khong phai tu main.py.
    """
    if not NOTIFICATION_SERVICE_URL:
        return

    alert_type = alert.get("alert_type", "unknown")
    severity_raw = alert.get("severity", "medium").upper()
    alert_id = alert.get("alert_id", f"ALT-{uuid.uuid4().hex[:8].upper()}")[:100]
    correlation_id = str(uuid.uuid4())

    # Map alert_type sang ten title de hien thi tren A7
    title_map = {
        "fire": "Canh bao chay/nguy hiem",
        "environment_warning": "Canh bao moi truong",
        "access_bruteforce": "Phat hien tan cong Bruteforce",
        "intrusion": "Phat hien xam nhap",
        "suspicious_person": "Phat hien nguoi dang ngo",
        "suspicious_activity": "Hoat dong dang ngo",
        "camera_vision_unavailable": "Camera mat ket noi AI Vision",
    }
    title = title_map.get(alert_type, f"Canh bao: {alert_type}")
    message = alert.get("message", "Khong co mo ta")
    source = alert.get("source_service", "core-business-service")

    url = f"{NOTIFICATION_SERVICE_URL.rstrip('/')}/events/alert.created"
    payload = {
        "eventId": str(uuid.uuid4()),
        "eventType": "alert.created",
        "alertId": alert_id,
        "correlationId": correlation_id,
        "source": source,
        "severity": severity_raw,
        "alertVersion": 1,
        "occurredAt": alert.get("timestamp", ""),
        "payload": {
            "title": title,
            "message": message,
            "source": source,
            "alertLevel": severity_raw,
        },
        "data": {
            "title": title,
            "message": message,
            "source": source,
            "alertLevel": severity_raw,
        },
        "channels": ["telegram"],
        "metadata": {
            "alert_type": alert_type,
            "origin_event_id": alert.get("origin_event_id", ""),
        },
    }
    try:
        resp = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/events/alert.created",
            json=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {AUTH_TOKEN}"},
            timeout=10.0,
        )
        if resp.status_code == 202:
            logger.info(f"[A7] Gui thanh cong: alert_type={alert_type} alert_id={alert_id}")
        else:
            logger.warning(f"[A7] Ma phan hoi {resp.status_code}: {resp.text[:200]}")
    except requests.exceptions.Timeout:
        logger.warning(f"[A7] Timeout khi gui canh bao {alert_type}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"[A7] Loi ket noi: {e}")


def publish_alert(alert: dict) -> None:
    """Publish canh bao len topic MQTT chuan va dong thoi gui sang A7 REST."""
    if _mqtt_client and _mqtt_client.is_connected():
        raw = json.dumps(alert)
        # Chi publish dung topic chuan, tranh gay nhieu cho Analytics
        _mqtt_client.publish(TOPIC_ALERT, raw)
        logger.info(f"[MQTT] Published alert: {alert.get('alert_type')}")

    # Broadcast alert len Dashboard real-time
    _broadcast({"type": "alert", "topic": TOPIC_ALERT, "data": alert})

    # Gui dong thoi sang A7 Notification Service qua REST (background, khong block)
    thread = threading.Thread(target=_send_alert_to_a7, args=(alert,), daemon=True)
    thread.start()


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
