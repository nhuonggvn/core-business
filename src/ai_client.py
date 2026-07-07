import httpx
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
MAX_RETRIES = 2

async def call_ai_vision_detect(
    request_id: str,
    camera_id: str,
    timestamp: str,
    location: str,
    motion_score: float,
    snapshot_url: str,
    ai_vision_base_url: str,
) -> Optional[Dict]:
    """
    Gọi AI Vision REST API để phân tích hình ảnh khi phát hiện chuyển động.
    Tự động retry tối đa 2 lần nếu gặp lỗi server (5xx) hoặc timeout.
    """
    payload = {
        "request_id": request_id,
        "camera_id": camera_id,
        "timestamp": timestamp,
        "location": location,
        "motion_score": motion_score,
        "snapshot_url": snapshot_url,
    }
    
    url = f"{ai_vision_base_url.rstrip('/')}/api/v1/detect"
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)
                
            if response.status_code == 200:
                result = response.json()
                logger.info(
                    f"[AI Vision] OK | request_id={request_id} "
                    f"risk_level={result.get('risk_level')} "
                    f"label={result.get('label')}"
                )
                return result
                
            elif response.status_code >= 500:
                logger.warning(
                    f"[AI Vision] Server error {response.status_code} "
                    f"attempt={attempt}/{MAX_RETRIES} request_id={request_id}"
                )
                
            else:
                logger.error(
                    f"[AI Vision] Client error {response.status_code} "
                    f"body={response.text} request_id={request_id}"
                )
                return None
                
        except httpx.TimeoutException:
            logger.warning(
                f"[AI Vision] Timeout attempt={attempt}/{MAX_RETRIES} request_id={request_id}"
            )
        except httpx.ConnectError:
            logger.error(f"[AI Vision] Cannot connect to {url}")
            return None
            
    logger.error(f"[AI Vision] Exceeded max retries, dropping request_id={request_id}")
    return None
