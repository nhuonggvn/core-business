import time
import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional
import uuid
from datetime import datetime, timezone, time as datetime_time

from ai_client import call_ai_vision_detect
from redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Bộ đếm dự phòng trong RAM — dùng khi Redis không khả dụng (Fallback)
# Key: f"bruteforce:{uid}:{door_id}"
# Value: List[float] — danh sách timestamp các lần quẹt thẻ thất bại
access_denied_timestamps: Dict[str, List[float]] = defaultdict(list)

# Lưu lịch sử sự kiện gần đây (tối đa 500 sự kiện)
recent_events: deque = deque(maxlen=500)

ALLOWED_HOURS = (datetime_time(6, 0), datetime_time(22, 0))
BRUTEFORCE_THRESHOLD = 3
BRUTEFORCE_WINDOW_SECONDS = 60


def is_outside_hours(timestamp_str: str) -> bool:
    """
    Kiểm tra xem timestamp truyền vào có nằm ngoài giờ cho phép (06:00 - 22:00) hay không.
    """
    try:
        if timestamp_str.endswith("Z"):
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(timestamp_str)
        ev_time = dt.time()
        return not (ALLOWED_HOURS[0] <= ev_time <= ALLOWED_HOURS[1])
    except Exception:
        now_time = datetime.now().time()
        return not (ALLOWED_HOURS[0] <= now_time <= ALLOWED_HOURS[1])


def make_alert(
    origin_event: Dict,
    alert_type: str,
    severity: str,
    message: str,
    target: str = "security_team",
) -> Dict:
    return {
        "event_type": "core.alert.created",
        "source_service": "team-core",
        "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "origin_event_id": (
            origin_event.get("raw_event_id")
            or origin_event.get("request_id")
            or origin_event.get("event_id")
        ),
        "target": target,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _bruteforce_denied_redis(key: str, now: float, location: str) -> Optional[Dict]:
    """
    Xử lý sự kiện quẹt thẻ thất bại bằng Redis Sliding Window.
    Trả về None nếu chua dat nguong, tra ve alert dict neu phat hien bruteforce.
    Raise Exception neu Redis bi loi de caller fallback sang RAM.
    """
    r = get_redis_client()
    if r is None:
        raise ConnectionError("Redis not available")

    r.rpush(key, str(now))
    r.expire(key, BRUTEFORCE_WINDOW_SECONDS)

    timestamps_str = r.lrange(key, 0, -1)
    valid_timestamps = [float(t) for t in timestamps_str if now - float(t) <= BRUTEFORCE_WINDOW_SECONDS]

    if len(valid_timestamps) < len(timestamps_str):
        r.delete(key)
        if valid_timestamps:
            r.rpush(key, *[str(t) for t in valid_timestamps])
            r.expire(key, BRUTEFORCE_WINDOW_SECONDS)

    failures_count = len(valid_timestamps)
    logger.info(f"[Access] [Redis] Denied | key={key} sliding_count={failures_count} loc={location}")
    return failures_count


def _bruteforce_denied_ram(key: str, now: float, location: str) -> int:
    """
    Xử lý sự kiện quẹt thẻ thất bại bằng RAM Sliding Window (Fallback).
    Tra ve so lan that bai trong cua so BRUTEFORCE_WINDOW_SECONDS giay gan nhat.
    """
    access_denied_timestamps[key].append(now)
    access_denied_timestamps[key] = [
        t for t in access_denied_timestamps[key]
        if now - t <= BRUTEFORCE_WINDOW_SECONDS
    ]
    failures_count = len(access_denied_timestamps[key])
    logger.info(f"[Access] [RAM] Denied | key={key} sliding_count={failures_count} loc={location}")
    return failures_count


def handle_sensor_event(event: Dict) -> Optional[Dict]:
    """
    Xu ly su kien cam bien moi truong.
    Tra ve alert payload hoac None.
    """
    s = event.get("status")
    location = event.get("location", "unknown")
    reason = event.get("reason", "")

    if s == "danger":
        return make_alert(event, "fire", "critical", f"Nguy hiem tai {location}: {reason}")
    elif s == "warning":
        return make_alert(event, "environment_warning", "medium", f"Canh bao tai {location}: {reason}")
    return None


def handle_access_event(event: Dict) -> Optional[Dict]:
    """
    Xu ly su kien quet the Access Gate.
    - Khi denied: Tang bo dem theo Sliding Window 60 giay (Redis -> RAM fallback).
      Neu dat nguong BRUTEFORCE_THRESHOLD, reset bo dem va tra ve alert.
    - Khi granted: Reset bo dem cua the do ve 0.
    Tra ve alert payload neu phat hien bruteforce, nguoc lai tra ve None.
    """
    uid = event.get("uid", "unknown")
    result = event.get("access_result")
    location = event.get("location", "unknown")
    door_id = event.get("door_id", "unknown")

    key = f"bruteforce:{uid}:{door_id}"
    recent_events.append((time.time(), event))
    now = time.time()

    if result == "denied":
        failures_count = 0

        try:
            failures_count = _bruteforce_denied_redis(key, now, location)
        except Exception as redis_error:
            logger.warning(f"[Access] Redis error ({redis_error}), switching to RAM fallback.")
            failures_count = _bruteforce_denied_ram(key, now, location)

        if failures_count >= BRUTEFORCE_THRESHOLD:
            # Reset bo dem sau khi phat hien bruteforce de tranh gui canh bao lien tuc
            r = get_redis_client()
            if r:
                try:
                    r.delete(key)
                except Exception:
                    pass
            if key in access_denied_timestamps:
                del access_denied_timestamps[key]

            logger.warning(
                f"[Access] BRUTEFORCE DETECTED | uid={uid} door={door_id} "
                f"failures={failures_count} loc={location}"
            )
            return make_alert(
                event,
                "access_bruteforce",
                "medium",
                f"Quet the that bai nhieu lan: UID={uid} tai {location} (cong {door_id})",
            )

    elif result in ("granted", "true"):
        r = get_redis_client()
        if r:
            try:
                r.delete(key)
                logger.info(f"[Access] [Redis] Granted | uid={uid} loc={location} - bo dem da reset")
            except Exception as e:
                logger.warning(f"[Access] Redis clear error: {e}. Resetting RAM fallback.")

        if key in access_denied_timestamps:
            del access_denied_timestamps[key]
            logger.info(f"[Access] [RAM] Granted | uid={uid} loc={location} - bo dem da reset")

    return None


async def handle_camera_event(event: Dict, ai_vision_url: str) -> Optional[Dict]:
    """
    Xu ly su kien camera.
    Goi AI Vision neu co motion. Neu phat hien nguoi la + risk medium/high,
    doi chieu voi su kien access gan nhat de canh bao dot nhap.
    """
    camera_id = event.get("camera_id", "unknown")
    location = event.get("location", "unknown")

    if not event.get("motion_detected", False):
        return None

    vision_result = await call_ai_vision_detect(
        request_id=event.get("request_id", str(uuid.uuid4())),
        camera_id=camera_id,
        timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
        location=location,
        motion_score=event.get("motion_score", 0.0),
        snapshot_url=event.get("snapshot_url", ""),
        ai_vision_base_url=ai_vision_url,
    )

    if vision_result is None:
        return make_alert(
            event,
            "camera_vision_unavailable",
            "low",
            f"Camera {camera_id} phat hien chuyen dong nhung AI Vision khong phan hoi",
        )

    risk_level = vision_result.get("risk_level", "low")
    label = vision_result.get("label", "")
    confidence = vision_result.get("confidence", 0.0)
    unknown_person = vision_result.get("unknown_person", False)

    # 1. Phat hien nguoi la ngoai gio -> Canh bao xam nhap muc khan cap (critical)
    is_outside = is_outside_hours(event.get("timestamp", ""))
    if (unknown_person or label == "person") and confidence >= 0.8 and is_outside:
        return make_alert(
            event,
            "intrusion",
            "critical",
            f"Phat hien xam nhap ngoai gio tai {location} (confidence={confidence:.2f})",
        )

    # 2. Nghi dot nhap: nguoi la xuat hien + co su kien quet the that bai gan day cung khu vuc
    check_now = time.time()
    has_denied_nearby = any(
        ev.get("access_result") == "denied" and ev.get("location") == location
        for ts, ev in list(recent_events)
        if check_now - ts <= 30
    )

    if (
        (unknown_person or label == "person")
        and confidence >= 0.8
        and risk_level in ("medium", "high")
        and has_denied_nearby
    ):
        return make_alert(
            event,
            "intrusion",
            "critical",
            f"Nghi dot nhap: nguoi la + quet the that bai gan day tai {location} (confidence={confidence:.2f})",
        )

    # 3. Nguoi la xuat hien trong gio -> Canh bao nguoi dang ngo muc cao (high)
    if (unknown_person or label == "person") and confidence >= 0.8 and risk_level in ("medium", "high"):
        return make_alert(
            event,
            "suspicious_person",
            "high",
            f"Phat hien nguoi dang ngo tai {location} (risk={risk_level})",
        )

    # 4. Hoat dong dang ngo (risk cao nhung do tin cay thap) -> Canh bao muc trung binh (medium)
    if risk_level == "high" and confidence < 0.8:
        return make_alert(
            event,
            "suspicious_activity",
            "medium",
            f"Hoat dong dang ngo tai {location} (confidence thap={confidence:.2f})",
        )

    return None
