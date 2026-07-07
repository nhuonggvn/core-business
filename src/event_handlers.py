import time
import logging
from collections import defaultdict, deque
from typing import Dict, Optional
import uuid
from datetime import datetime, timezone, time as datetime_time

from ai_client import call_ai_vision_detect

logger = logging.getLogger(__name__)

# Bộ đếm trong RAM chống Bruteforce
access_denied_counter: Dict[str, int] = defaultdict(int)
# Lưu lịch sử sự kiện gần đây (tối đa 500 sự kiện)
recent_events: deque = deque(maxlen=500)

ALLOWED_HOURS = (datetime_time(6, 0), datetime_time(22, 0))

def is_outside_hours(timestamp_str: str) -> bool:
    """
    Kiểm tra xem timestamp truyền vào có nằm ngoài giờ cho phép (06:00 - 22:00) hay không.
    """
    try:
        # Hỗ trợ phân tích timestamp dạng ISO 8601
        if timestamp_str.endswith('Z'):
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(timestamp_str)
        ev_time = dt.time()
        return not (ALLOWED_HOURS[0] <= ev_time <= ALLOWED_HOURS[1])
    except Exception:
        # Fallback về giờ hiện tại nếu lỗi định dạng
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

def handle_sensor_event(event: Dict) -> Optional[Dict]:
    """
    Xử lý sự kiện cảm biến môi trường.
    Trả về alert payload hoặc None.
    """
    s = event.get("status")
    location = event.get("location", "unknown")
    reason = event.get("reason", "")
    
    if s == "danger":
        return make_alert(event, "fire", "critical", f"Nguy hiểm tại {location}: {reason}")
    elif s == "warning":
        return make_alert(event, "environment_warning", "medium", f"Cảnh báo tại {location}: {reason}")
    return None

def handle_access_event(event: Dict) -> Optional[Dict]:
    """
    Xử lý sự kiện quẹt thẻ. Tăng bộ đếm khi denied, reset khi granted.
    Trả về alert payload nếu phát hiện bruteforce, ngược lại None.
    """
    uid = event.get("uid", "unknown")
    result = event.get("access_result")
    location = event.get("location", "unknown")
    
    # Lưu vào lịch sử sự kiện (cho việc kiểm tra chéo sau này)
    recent_events.append((time.time(), event))
    
    if result == "denied":
        access_denied_counter[uid] += 1
        logger.info(f"[Access] Denied | uid={uid} count={access_denied_counter[uid]} loc={location}")
        
        if access_denied_counter[uid] >= 3:
            return make_alert(
                event, "access_bruteforce", "medium",
                f"Quẹt thẻ thất bại nhiều lần: UID={uid} tại {location}"
            )
    elif result in ("granted", "true"):
        access_denied_counter[uid] = 0
        logger.info(f"[Access] Granted | uid={uid} loc={location}")
        
    return None

async def handle_camera_event(event: Dict, ai_vision_url: str) -> Optional[Dict]:
    """
    Xử lý sự kiện camera.
    Gọi AI Vision nếu có motion. Nếu phát hiện người lạ + risk medium/high,
    đối chiếu với sự kiện access gần nhất để cảnh báo đột nhập.
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
        return make_alert(event, "camera_vision_unavailable", "low", f"Camera {camera_id} phát hiện chuyển động nhưng AI Vision không phản hồi")
        
    risk_level = vision_result.get("risk_level", "low")
    label = vision_result.get("label", "")
    confidence = vision_result.get("confidence", 0.0)
    unknown_person = vision_result.get("unknown_person", False)
    
    # 1. Phát hiện người lạ ngoài giờ -> Cảnh báo xâm nhập mức khẩn cấp (critical)
    is_outside = is_outside_hours(event.get("timestamp", ""))
    if (unknown_person or label == "person") and confidence >= 0.8 and is_outside:
        return make_alert(
            event, "intrusion", "critical",
            f"Phát hiện xâm nhập ngoài giờ tại {location} (confidence={confidence:.2f})"
        )
    
    # 2. Nghi đột nhập: người lạ xuất hiện + có sự kiện quẹt thẻ thất bại gần đây cùng khu vực
    now = time.time()
    has_denied_nearby = any(
        ev.get("access_result") == "denied" and ev.get("location") == location
        for ts, ev in list(recent_events)
        if now - ts <= 30
    )
    
    if (unknown_person or label == "person") and confidence >= 0.8 and risk_level in ("medium", "high") and has_denied_nearby:
        return make_alert(
            event, "intrusion", "critical",
            f"Nghi đột nhập: người lạ + quẹt thẻ thất bại gần đây tại {location} (confidence={confidence:.2f})"
        )
    
    # 3. Người lạ xuất hiện trong giờ -> Cảnh báo người đáng ngờ mức cao (high)
    elif (unknown_person or label == "person") and confidence >= 0.8 and risk_level in ("medium", "high"):
        return make_alert(
            event, "suspicious_person", "high",
            f"Phát hiện người đáng ngờ tại {location} (risk={risk_level})"
        )
        
    # 4. Hoạt động đáng ngờ (risk cao nhưng độ tin cậy thấp) -> Cảnh báo mức trung bình (medium)
    elif risk_level == "high" and confidence < 0.8:
        return make_alert(
            event, "suspicious_activity", "medium",
            f"Hoạt động đáng ngờ tại {location} (confidence thấp={confidence:.2f})"
        )
        
    return None
