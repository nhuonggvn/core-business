import asyncio
import http.client
import os
import threading
import requests
import psycopg2
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mqtt_handler import start_mqtt_client, stop_mqtt_client, get_mqtt_client, publish_alert
from websocket_manager import manager as ws_manager


SERVICE_NAME = os.getenv("SERVICE_NAME", "core-business")
# Giao tiep voi A7 qua ca REST va MQTT
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.5.0")
# Token xac thuc cho A3 goi vao API cua A6
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")
# URL dich vu thong bao A7 (Radmin VPN)
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://26.19.238.62:8000")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "lab05")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "lab05pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "iotdb")


def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=3
    )


def execute_db_query(query, params=None, fetch=False):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        if fetch:
            results = cur.fetchall()
            cur.close()
            conn.close()
            return results
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Error] SQL execution failed: {e}")
        return None


def init_db_tables():
    create_tables_sql = """
    CREATE TABLE IF NOT EXISTS gates (
        gate_id VARCHAR(50) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        status VARCHAR(50) NOT NULL
    );
    CREATE TABLE IF NOT EXISTS cards (
        card_id VARCHAR(50) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        status VARCHAR(50) NOT NULL,
        expires_at VARCHAR(50) NOT NULL
    );
    CREATE TABLE IF NOT EXISTS decisions (
        decision_id VARCHAR(50) PRIMARY KEY,
        card_id VARCHAR(50) NOT NULL,
        gate_id VARCHAR(50) NOT NULL,
        allow BOOLEAN NOT NULL,
        reason_code VARCHAR(50) NOT NULL,
        timestamp VARCHAR(50) NOT NULL
    );
    """
    execute_db_query(create_tables_sql)
    
    seed_gates = """
    INSERT INTO gates (gate_id, name, status) VALUES
    ('GATE-01', 'Cong so 1', 'OPEN'),
    ('gate-a', 'Cong chinh A', 'OPEN'),
    ('lab-a101', 'Phong Lab A101', 'OPEN')
    ON CONFLICT (gate_id) DO NOTHING;
    """
    execute_db_query(seed_gates)
        
    seed_cards = """
    INSERT INTO cards (card_id, name, status, expires_at) VALUES
    ('CARD-123456', 'Nguyen Van A', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-654321', 'Tran Thi B', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000000', 'The Bi Khoa', 'BLOCKED', '2027-12-31T23:59:59Z'),
    ('CARD-000401', 'Nguyen Van An', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000402', 'Tran Thi Binh', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000403', 'Le Minh Cuong', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000404', 'Pham Thu Dung', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000405', 'Hoang Van Hieu', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000406', 'Do Thi Lan', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000407', 'Bui Quang Minh', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000408', 'Vu Thanh Nam', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000409', 'Dang Phuong Thao', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000410', 'Nguyen Minh Quan', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-999999', 'The Test Bruteforce', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-888888', 'The Het Han', 'EXPIRED', '2025-12-31T23:59:59Z'),
    ('CARD-000401', 'The RFID 401', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000404', 'The RFID 404', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000405', 'The RFID 405', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000406', 'The RFID 406', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000407', 'The RFID 407', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000408', 'The RFID 408', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000409', 'The RFID 409', 'ACTIVE', '2027-12-31T23:59:59Z'),
    ('CARD-000410', 'The RFID 410', 'ACTIVE', '2027-12-31T23:59:59Z')
    ON CONFLICT (card_id) DO UPDATE SET name = EXCLUDED.name, status = EXCLUDED.status;
    """
    execute_db_query(seed_cards)
    print("[DB Info] Seed data updated successfully into PostgreSQL.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_tables()
    loop = asyncio.get_event_loop()
    start_mqtt_client(loop)
    yield
    stop_mqtt_client()

app = FastAPI(
    title="FIT4110 Lab 04 - Core Business Service",
    version=SERVICE_VERSION,
    description="Dockerized Core Business API aligned with OpenAPI and Postman contract.",
    lifespan=lifespan,
)

# Mount thu muc frontend tinh de phuc vu Dashboard tai route /dashboard
_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/dashboard", StaticFiles(directory=_FRONTEND_DIR, html=True), name="dashboard")


class DirectionEnum(str, Enum):
    IN = "IN"
    OUT = "OUT"


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: str
    instance: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class AccessCheckRequest(BaseModel):
    requestId: str = Field(..., examples=["0196fb3d-4ad7-7d1e-9f49-5d5148d2cafe"])
    # cardId chap nhan moi dinh dang: CARD-xxxxxx, UID hex, ma sinh vien...
    cardId: str = Field(..., examples=["CARD-123456"])
    gateId: str = Field(..., examples=["GATE-01"])
    direction: DirectionEnum = Field(..., examples=["IN"])
    timestamp: str = Field(..., examples=["2026-06-01T10:00:00Z"])


class AccessCheckResponse(BaseModel):
    decisionId: str
    allow: bool
    reasonCode: str
    policyId: str
    expiresAt: str


class PolicyResponse(BaseModel):
    policyId: str
    name: str
    status: str
    description: str


class GateStatusResponse(BaseModel):
    gateId: str
    status: str


def _send_to_a7_rest(
    event_type: str,
    alert_id: str,
    severity: str,
    title: str,
    message: str,
    source: str,
    alert_level: str,
    channels: List[str],
    correlation_id: str,
    metadata: Optional[Dict] = None,
) -> None:
    """
    Gui canh bao sang A7 (Notification Service) qua REST API.
    Su dung dung format AlertEventPayload theo OpenAPI cua A7.
    """
    if not NOTIFICATION_SERVICE_URL:
        print("[A7] NOTIFICATION_SERVICE_URL chua duoc cau hinh, bo qua.")
        return

    # Xac dinh endpoint phu hop voi loai su kien
    endpoint_map = {
        "alert.created": "/events/alert.created",
        "alert.escalated": "/events/alert.escalated",
        "alert.resolved": "/events/alert.resolved",
    }
    path = endpoint_map.get(event_type, "/events/alert.created")
    url = f"{NOTIFICATION_SERVICE_URL.rstrip('/')}{path}"

    payload = {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "alertId": alert_id[:100],
        "correlationId": correlation_id[:100],
        "source": source,
        "severity": severity,
        "alertVersion": 1,
        "occurredAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data": {
            "title": title,
            "message": message,
            "source": source,
            "alertLevel": alert_level,
        },
        "channels": channels[:4],
        "metadata": metadata or {},
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {AUTH_TOKEN}"},
            timeout=3.0,
        )
        if resp.status_code == 202:
            print(f"[A7] Da gui thanh cong sang A7: {event_type} | alert_id={alert_id}")
        else:
            print(f"[A7] A7 tra ve ma {resp.status_code}: {resp.text[:200]}")
    except requests.exceptions.Timeout:
        print(f"[A7] Timeout khi gui sang A7 ({url})")
    except requests.exceptions.RequestException as e:
        print(f"[A7] Loi ket noi A7: {e}")


def _publish_security_alert(reason_code: str, card_id: str, gate_id: str) -> None:
    """
    Xu ly canh bao bao mat khi co vi pham quet the:
    - Publish len MQTT de broadcast noi bo va Dashboard.
    - Gui REST sang A7 voi dung format AlertEventPayload.
    """
    alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
    correlation_id = str(uuid.uuid4())

    # Phan loai muc do nghiem trong theo loai vi pham
    severity_map = {
        "CARD_NOT_FOUND": "MEDIUM",
        "CARD_BLOCKED": "HIGH",
        "CARD_EXPIRED": "HIGH",
        "GATE_LOCKED": "HIGH",
        "OUT_OF_SCHEDULE": "MEDIUM",
    }
    severity = severity_map.get(reason_code, "MEDIUM")

    title_map = {
        "CARD_NOT_FOUND": "The khong ton tai",
        "CARD_BLOCKED": "The bi khoa",
        "CARD_EXPIRED": "The da het han",
        "GATE_LOCKED": "Cong dang khoa",
        "OUT_OF_SCHEDULE": "Quet the ngoai gio cho phep",
    }
    title = title_map.get(reason_code, "Vi pham bao mat")
    message = f"Vi pham quet the ({reason_code}) cho the {card_id} tai cong {gate_id}"

    # 1. Publish MQTT noi bo de Dashboard nhan real-time
    mqtt_payload = {
        "event_type": "core.alert.created",
        "source_service": "team-core",
        "alert_id": alert_id,
        "alert_type": "access_violation",
        "reason_code": reason_code,
        "severity": severity.lower(),
        "message": message,
        "card_id": card_id,
        "gate_id": gate_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    publish_alert(mqtt_payload)

    # 2. Gui REST sang A7 (background, khong block response tra ve cho A3)
    thread = threading.Thread(
        target=_send_to_a7_rest,
        kwargs={
            "event_type": "alert.created",
            "alert_id": alert_id,
            "severity": severity,
            "title": title,
            "message": message,
            "source": "core-business-service",
            "alert_level": severity,
            "channels": ["telegram"],
            "correlation_id": correlation_id,
            "metadata": {"card_id": card_id, "gate_id": gate_id, "reason_code": reason_code},
        },
        daemon=True,
    )
    thread.start()
    print(f"[Alert] Sent security alert: reason={reason_code} card={card_id} gate={gate_id}")


def build_problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "about:blank",
) -> Dict:
    problem = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        problem["instance"] = instance
    return problem


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        problem = build_problem(
            status_code=exc.status_code,
            title=http.client.responses.get(exc.status_code, "HTTP Error"),
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    problem.setdefault("status", exc.status_code)
    problem.setdefault("title", http.client.responses.get(exc.status_code, "HTTP Error"))
    problem.setdefault("type", "about:blank")
    problem.setdefault("detail", "Request failed")
    problem.setdefault("instance", str(request.url.path))

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = first_error.get("msg", "Request validation error")
    detail = f"{location}: {message}" if location else message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation error",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://smart-campus.local/problems/validation-error",
        ),
        media_type="application/problem+json",
    )


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Missing Authorization header",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )

    expected = f"Bearer {AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Invalid bearer token",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )


@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict:
    mqtt_client = get_mqtt_client()
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "mqtt_connected": mqtt_client.is_connected() if mqtt_client else False,
    }


def check_gate_policy(gate_id: str, card_id: str) -> Optional[str]:
    # Kiem tra trang thai cong tu PostgreSQL
    rows = execute_db_query("SELECT status FROM gates WHERE gate_id = %s;", (gate_id,), fetch=True)
    if not rows:
        return "GATE_NOT_FOUND"
    status_str = rows[0][0]
    if status_str == "LOCKED":
        _publish_security_alert("GATE_LOCKED", card_id, gate_id)
        return "GATE_LOCKED"
    return None


def check_card_validity(card_id: str, gate_id: str) -> Optional[str]:
    # Kiem tra the co ton tai trong DB khong
    rows = execute_db_query("SELECT 1 FROM cards WHERE card_id = %s;", (card_id,), fetch=True)
    if not rows:
        _publish_security_alert("CARD_NOT_FOUND", card_id, gate_id)
        return "CARD_NOT_FOUND"
    return None


def check_card_expiration(card_id: str, gate_id: str, timestamp: str) -> Optional[str]:
    # Kiem tra han su dung cua the
    rows = execute_db_query("SELECT expires_at, status FROM cards WHERE card_id = %s;", (card_id,), fetch=True)
    if not rows:
        return None
    expires_at_str, status_str = rows[0]
    try:
        expires_str = expires_at_str.replace("Z", "+00:00")
        expires_dt = datetime.fromisoformat(expires_str)

        event_str = timestamp.replace("Z", "+00:00") if timestamp.endswith("Z") else timestamp
        event_dt = datetime.fromisoformat(event_str)

        if event_dt > expires_dt or status_str == "EXPIRED":
            _publish_security_alert("CARD_EXPIRED", card_id, gate_id)
            return "CARD_EXPIRED"
    except Exception as e:
        print(f"[Error] Loi phan tich han su dung: {e}")
    return None


def check_card_status(card_id: str, gate_id: str) -> Optional[str]:
    # Kiem tra the bi khoa
    rows = execute_db_query("SELECT status FROM cards WHERE card_id = %s;", (card_id,), fetch=True)
    if not rows:
        return None
    status_str = rows[0][0]
    if status_str == "BLOCKED":
        _publish_security_alert("CARD_BLOCKED", card_id, gate_id)
        return "CARD_BLOCKED"
    return None


def check_schedule_policy(card_id: str, gate_id: str, timestamp: str) -> Optional[str]:
    # Kiem tra gio ra vao co hop le khong
    from event_handlers import is_outside_hours
    if is_outside_hours(timestamp):
        _publish_security_alert("OUT_OF_SCHEDULE", card_id, gate_id)
        return "OUT_OF_SCHEDULE"
    return None


@app.post(
    "/access/check",
    response_model=AccessCheckResponse,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        401: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
def access_check(
    payload: AccessCheckRequest,
    prefer: Optional[str] = Header(default=None),
) -> AccessCheckResponse:
    print(f"\n[INFO] === RECEIVED ACCESS CHECK REQUEST ===")
    print(f"[INFO] Request ID: {payload.requestId}")
    print(f"[INFO] Card ID:    {payload.cardId}")
    print(f"[INFO] Gate ID:    {payload.gateId}")
    print(f"[INFO] Direction:  {payload.direction}")
    print(f"[INFO] Timestamp:  {payload.timestamp}")
    print(f"[INFO] =====================================\n")

    err = None
    
    # 1. Kiem tra cong
    err = check_gate_policy(payload.gateId, payload.cardId)
    if err == "GATE_NOT_FOUND":
        raise HTTPException(status_code=404, detail=f"Gate {payload.gateId} not found")
        
    # 2. Kiem tra the hop le
    if not err:
        err = check_card_validity(payload.cardId, payload.gateId)
    # 3. Kiem tra the het han
    if not err:
        err = check_card_expiration(payload.cardId, payload.gateId, payload.timestamp)
    # 4. Kiem tra the bi khoa
    if not err:
        err = check_card_status(payload.cardId, payload.gateId)
    # 5. Kiem tra gio ra vao
    if not err:
        err = check_schedule_policy(payload.cardId, payload.gateId, payload.timestamp)

    # Ghi nhan ket qua vao DB
    insert_sql = """
    INSERT INTO decisions (decision_id, card_id, gate_id, allow, reason_code, timestamp)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (decision_id) DO UPDATE 
    SET allow = EXCLUDED.allow, reason_code = EXCLUDED.reason_code, timestamp = EXCLUDED.timestamp;
    """
    
    if err:
        execute_db_query(insert_sql, (payload.requestId, payload.cardId, payload.gateId, False, err, payload.timestamp))
        return AccessCheckResponse(decisionId=payload.requestId, allow=False, reasonCode=err, policyId="POL-101", expiresAt="2026-06-01T10:00:05Z")

    execute_db_query(insert_sql, (payload.requestId, payload.cardId, payload.gateId, True, "ALLOWED", payload.timestamp))
    return AccessCheckResponse(
        decisionId=payload.requestId,
        allow=True,
        reasonCode="ALLOWED",
        policyId="POL-101",
        expiresAt="2026-06-01T10:00:05Z",
    )


@app.get(
    "/policies/access/{policy_id}",
    response_model=PolicyResponse,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        401: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
    },
)
def get_policy(
    policy_id: str,
    prefer: Optional[str] = Header(default=None),
) -> PolicyResponse:
    if policy_id == "POL-999" or (prefer and "code=404" in prefer):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Not Found",
                detail=f"Policy {policy_id} does not exist",
                instance=f"/policies/access/{policy_id}",
                problem_type="https://smart-campus.local/problems/not-found",
            ),
        )

    return PolicyResponse(
        policyId=policy_id,
        name="Chính sách ra vào thông thường",
        status="ACTIVE",
        description="Chính sách cho phép ra vào giờ hành chính",
    )


@app.get(
    "/decisions/{decision_id}",
    dependencies=[Depends(verify_bearer_token)],
    responses={
        401: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
    },
)
def get_decision(decision_id: str) -> Dict:
    rows = execute_db_query("SELECT card_id, gate_id, allow, reason_code FROM decisions WHERE decision_id = %s;", (decision_id,), fetch=True)
    if rows:
        card_id, gate_id, allow, reason_code = rows[0]
        return {
            "decisionId": decision_id,
            "cardId": card_id,
            "gateId": gate_id,
            "allow": allow,
            "reasonCode": reason_code,
        }
    raise HTTPException(status_code=404, detail="Decision not found")


@app.get(
    "/gates/{gate_id}/status",
    response_model=GateStatusResponse,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        401: {"model": ProblemDetails},
    },
)
def get_gate_status(gate_id: str) -> GateStatusResponse:
    return GateStatusResponse(
        gateId=gate_id,
        status="OPEN",
    )


@app.post("/emergency/evacuate")
def trigger_evacuation() -> Dict:
    """
    Kich hoat lenh so tan khan cap toan Campus.
    - Publish MQTT voi severity CRITICAL.
    - Gui REST sang A7 de phat tin hieu Telegram ngay lap tuc.
    - Broadcast xuong Dashboard qua WebSocket.
    """
    alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
    correlation_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # 1. Tao payload canh bao so tan
    evacuation_alert = {
        "event_type": "core.alert.created",
        "source_service": "team-core",
        "alert_id": alert_id,
        "alert_type": "evacuation_initiated",
        "severity": "critical",
        "message": "LENH SO TAN KHAN CAP TOAN TRAM A6 DA PHAT DONG!",
        "timestamp": now_iso,
    }

    # 2. Publish MQTT noi bo va broadcast Dashboard
    publish_alert(evacuation_alert)

    # 3. Gui sang A7 REST voi format AlertEventPayload (background thread)
    thread = threading.Thread(
        target=_send_to_a7_rest,
        kwargs={
            "event_type": "alert.escalated",
            "alert_id": alert_id,
            "severity": "CRITICAL",
            "title": "LENH SO TAN KHAN CAP",
            "message": "LENH SO TAN KHAN CAP TOAN TRAM A6 DA PHAT DONG! Tat ca moi nguoi hay roi khoi toa nha ngay lap tuc!",
            "source": "core-business-service",
            "alert_level": "CRITICAL",
            "channels": ["telegram"],
            "correlation_id": correlation_id,
            "metadata": {"triggered_by": "dashboard_operator", "location": "Smart Campus A6"},
        },
        daemon=True,
    )
    thread.start()

    print(f"[EVACUATE] Lenh so tan da phat dong! alert_id={alert_id}")
    return {"status": "ok", "message": "Lenh so tan da gui di", "alertId": alert_id}


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """
    WebSocket endpoint cho phep giao dien Dashboard ket noi nhan du lieu real-time.
    Moi su kien MQTT hoac Alert se duoc broadcast xuong tat ca client dang ket noi.
    """
    await ws_manager.connect(websocket)
    try:
        # Gui tin hieu chao mung khi client vua ket noi thanh cong
        await websocket.send_text('{"type":"connected","message":"Smart Campus Dashboard connected"}')
        while True:
            # Giu ket noi song bang cach cho tin hieu ping tu client
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
