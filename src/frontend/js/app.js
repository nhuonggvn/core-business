/**
 * Core Business A6 - Smart Campus (app.js)
 * Script xử lý dữ liệu WebSocket, Form gửi yêu cầu và render luồng sự kiện trực tiếp
 */

(function () {
    "use strict";

    const WS_URL = `ws://${location.host}/ws/dashboard`;
    const API_ACCESS_CHECK = `/access/check`;
    const AUTH_TOKEN = `local-dev-token`;
    const ITEMS_PER_PAGE = 8;

    let ws = null;
    let allEvents = [];
    let filteredEvents = [];
    let currentPage = 1;
    
    // Filters
    let currentFilterGate = "all";
    let currentFilterType = "all";
    let currentFilterFire = false;

    // Metrics
    let countTotal = 0;
    let countBlocked = 0;
    let countEmergency = 0;

    // DOM Refs
    const eventFeed = document.getElementById("event-feed");
    const metricTotal = document.getElementById("metric-total");
    const metricServices = document.getElementById("metric-services");
    const metricBlocked = document.getElementById("metric-blocked");
    const metricEmergency = document.getElementById("metric-emergency");
    
    const jsonModal = document.getElementById("json-modal");
    const jsonCodeBlock = document.getElementById("json-code-block");
    const btnCloseModal = document.getElementById("btn-close-modal");

    const formAccess = document.getElementById("form-access-check");
    const formResult = document.getElementById("form-result");

    const btnPrev = document.getElementById("btn-prev-events");
    const btnNext = document.getElementById("btn-next-events");
    const pageInfo = document.getElementById("info-events");

    // Theme Toggle
    const btnTheme = document.getElementById("btn-theme");
    if (btnTheme) {
        const savedTheme = localStorage.getItem("a6-theme") || "light";
        if (savedTheme === "dark") {
            document.body.className = "dark-theme";
            btnTheme.textContent = "Chế độ sáng";
        }
        btnTheme.addEventListener("click", () => {
            const isDark = document.body.classList.toggle("dark-theme");
            document.body.classList.remove(isDark ? "light-theme" : "dark-theme");
            btnTheme.textContent = isDark ? "Chế độ sáng" : "Chế độ tối";
            localStorage.setItem("a6-theme", isDark ? "dark" : "light");
        });
    }

    // Tiện ích
    function formatTime(isoStr) {
        try {
            const d = isoStr ? new Date(isoStr) : new Date();
            return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        } catch (_) {
            return new Date().toLocaleTimeString("vi-VN");
        }
    }

    function escapeHtml(str) {
        if (typeof str !== "string") return String(str ?? "");
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    // Logic Lọc & Phân trang
    function applyFilters() {
        filteredEvents = allEvents.filter(ev => {
            if (currentFilterFire) {
                const isFireAlert = ev.topic === "smart-campus/events/alert" && (ev.data.severity === "critical" || ev.data.severity === "high");
                const isFireSensor = ev.topic === "smart-campus/events/sensor" && ev.data.status === "danger";
                if (!isFireAlert && !isFireSensor) return false;
            }
            if (currentFilterType !== "all") {
                if (currentFilterType === "access" && ev.topic !== "smart-campus/events/access") return false;
                if (currentFilterType === "sensor" && ev.topic !== "smart-campus/events/sensor") return false;
                if (currentFilterType === "camera" && ev.topic !== "smart-campus/events/camera") return false;
                if (currentFilterType === "alert" && ev.topic !== "smart-campus/events/alert") return false;
            }
            if (currentFilterGate !== "all") {
                const itemGate = (ev.data.gate_id || ev.data.location || "").toLowerCase();
                if (!itemGate.includes(currentFilterGate.toLowerCase())) return false;
            }
            return true;
        });

        currentPage = 1;
        renderFeed();
    }

    function renderFeed() {
        eventFeed.innerHTML = "";
        const totalItems = filteredEvents.length;
        const totalPages = Math.max(1, Math.ceil(totalItems / ITEMS_PER_PAGE));
        if (currentPage > totalPages) currentPage = totalPages;

        const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
        const pageItems = filteredEvents.slice(startIndex, startIndex + ITEMS_PER_PAGE);

        if (pageItems.length === 0) {
            eventFeed.innerHTML = `<div class="empty-feed">Chưa có bản ghi hoạt động nào...</div>`;
            btnPrev.disabled = true;
            btnNext.disabled = true;
            pageInfo.textContent = `Trang 1 / 1`;
            return;
        }

        pageItems.forEach((item, index) => {
            const meta = getEventMeta(item);
            const rawJson = JSON.stringify(item.data, null, 4);
            const globalIndex = startIndex + index;
            
            const row = document.createElement("div");
            row.className = "event-row";
            row.innerHTML = `
                <div class="event-time">${meta.time}</div>
                <div class="event-content">
                    <span class="event-tag ${meta.tagClass}">${meta.tagText}</span>
                    <span class="event-desc">${meta.desc}</span>
                </div>
                <div>
                    <button class="btn-json" data-idx="${globalIndex}">Xem JSON</button>
                </div>
            `;
            eventFeed.appendChild(row);
        });

        document.querySelectorAll(".btn-json").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const idx = e.target.getAttribute("data-idx");
                const evt = filteredEvents[idx];
                jsonCodeBlock.textContent = JSON.stringify(evt, null, 4);
                jsonModal.classList.add("show");
            });
        });

        btnPrev.disabled = currentPage === 1;
        btnNext.disabled = currentPage === totalPages;
        pageInfo.textContent = `Trang ${currentPage} / ${totalPages}`;
    }

    // Format Meta Data Feed
    function getEventMeta(evt) {
        const topic = evt.topic;
        const d = evt.data;
        const time = formatTime(d.timestamp || evt.localTimestamp);

        if (topic === "smart-campus/events/access") {
            const isGranted = (d.access_result === "granted" || d.access_result === "true");
            return {
                time: time,
                tagClass: isGranted ? "tag-success" : "tag-danger",
                tagText: "[A6_ACCESS]",
                desc: isGranted ? `Xác thực thành công. Mã định danh: ${d.uid}` : `Xác thực thất bại. Cảnh báo thẻ: ${d.uid}`
            };
        }
        if (topic === "smart-campus/events/sensor") {
            const status = d.status || "unknown";
            let tClass = status === "danger" ? "tag-danger" : (status === "warning" ? "tag-warning" : "tag-success");
            return {
                time: time,
                tagClass: tClass,
                tagText: "[A6_SENSOR]",
                desc: `Trạng thái môi trường: ${status.toUpperCase()} (${d.location || 'N/A'}) - ${d.reason || ''}`
            };
        }
        if (topic === "smart-campus/events/camera") {
            return {
                time: time,
                tagClass: "tag-success",
                tagText: "[A6_VISION]",
                desc: `Phát hiện vật thể/người qua vùng quét: ${d.location || 'N/A'}`
            };
        }
        if (topic === "smart-campus/events/alert") {
            const sev = (d.severity || "low").toLowerCase();
            let tClass = sev === "critical" ? "tag-danger" : (sev === "high" ? "tag-warning" : "tag-default");
            return {
                time: time,
                tagClass: tClass,
                tagText: "[CORE_ALERT]",
                desc: `TÍN HIỆU ${sev.toUpperCase()}: ${d.message || d.alert_type}`
            };
        }

        return { time: time, tagClass: "tag-default", tagText: "[SYSTEM]", desc: escapeHtml(d.event_type || "Sự kiện ngoại vi") };
    }

    // Nhận Dữ Liệu
    function addEvent(topic, data) {
        countTotal++;
        metricTotal.textContent = countTotal;

        if (topic === "smart-campus/events/access" && (data.access_result === "denied" || data.access_result === "false")) {
            countBlocked++;
            metricBlocked.textContent = countBlocked;
        }
        if ((topic === "smart-campus/events/sensor" && data.status === "danger") || 
            (topic === "smart-campus/events/alert" && (data.severity === "critical" || data.severity === "high"))) {
            countEmergency++;
            metricEmergency.textContent = countEmergency;
        }

        allEvents.unshift({ topic, data, localTimestamp: new Date() });
        applyFilters();
    }

    // Xử lý Gửi Form
    if (formAccess) {
        formAccess.addEventListener("submit", async (e) => {
            e.preventDefault();
            const uid = document.getElementById("input-uid").value;
            const gate_id = document.getElementById("input-gate").value;
            const direction = document.getElementById("input-direction").value;
            const btnSubmit = formAccess.querySelector(".btn-submit-a6");

            formResult.style.display = "block";
            formResult.style.background = "var(--bg-card)";
            formResult.style.color = "var(--text-primary)";
            formResult.textContent = "Đang kết nối API A6...";
            btnSubmit.disabled = true;

            try {
                const response = await fetch(API_ACCESS_CHECK, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${AUTH_TOKEN}` },
                    body: JSON.stringify({ uid, gate_id, direction })
                });

                const data = await response.json();
                
                if (response.ok) {
                    formResult.style.background = "rgba(20, 184, 166, 0.2)";
                    formResult.style.color = "var(--brand-teal)";
                    formResult.textContent = `OK: Cửa Mở (${data.accessResult})`;
                } else {
                    formResult.style.background = "rgba(225, 29, 72, 0.2)";
                    formResult.style.color = "var(--color-red)";
                    formResult.textContent = `CẢNH BÁO: Bị chặn (${data.detail || data.accessResult})`;
                }
            } catch (err) {
                formResult.style.background = "rgba(234, 88, 12, 0.2)";
                formResult.style.color = "var(--color-orange)";
                formResult.textContent = `Lỗi mạng: Mất kết nối Backend.`;
            } finally {
                btnSubmit.disabled = false;
                setTimeout(() => { formResult.style.display = "none"; }, 4000);
            }
        });
    }

    // Modal
    btnCloseModal.addEventListener("click", () => jsonModal.classList.remove("show"));
    jsonModal.addEventListener("click", (e) => { if (e.target === jsonModal) jsonModal.classList.remove("show"); });

    // Lọc Dữ liệu
    document.getElementById("filter-gate").addEventListener("change", (e) => { currentFilterGate = e.target.value; applyFilters(); });
    document.getElementById("filter-type").addEventListener("change", (e) => { currentFilterType = e.target.value; applyFilters(); });
    document.getElementById("filter-fire").addEventListener("click", (e) => { 
        currentFilterFire = !currentFilterFire; 
        e.target.style.background = currentFilterFire ? "var(--color-red)" : "";
        e.target.style.color = currentFilterFire ? "white" : "";
        applyFilters(); 
    });
    document.getElementById("btn-clear-feed").addEventListener("click", () => { allEvents = []; applyFilters(); });

    // Pagination
    btnPrev.addEventListener("click", () => { if (currentPage > 1) { currentPage--; renderFeed(); } });
    btnNext.addEventListener("click", () => { const totalPages = Math.ceil(filteredEvents.length / ITEMS_PER_PAGE); if (currentPage < totalPages) { currentPage++; renderFeed(); } });

    document.getElementById("btn-evacuate").addEventListener("click", () => {
        addEvent("smart-campus/events/alert", { alert_type: "evacuation_initiated", severity: "critical", message: "LỆNH SƠ TÁN TOÀN TRẠM A6 ĐÃ PHÁT ĐỘNG!" });
    });

    // WebSocket Conn
    const connBadge = document.getElementById("conn-badge");
    const connText = document.getElementById("conn-text");

    function updateServiceStatus(isOnline) {
        const els = document.querySelectorAll(".srv-badge");
        els.forEach(el => {
            if (el.id === "status-b4") return; // B4 fake offline
            el.className = `srv-badge ${isOnline ? "online" : "offline"}`;
            el.textContent = isOnline ? "BÌNH THƯỜNG" : "MẤT KẾT NỐI";
        });
        metricServices.textContent = isOnline ? "5/6" : "0/6";

        if (connBadge) {
            connBadge.className = `ws-status ${isOnline ? "connected" : "disconnected"}`;
            connText.textContent = isOnline ? "Cổng WebSocket Mở" : "Sever Mất Kết Nối";
        }
    }

    function connect() {
        updateServiceStatus(false);
        ws = new WebSocket(WS_URL);
        ws.onopen = function () { updateServiceStatus(true); };
        ws.onmessage = function (event) {
            if (event.data === "ping") { ws.send("pong"); return; }
            let msg;
            try { msg = JSON.parse(event.data); } catch (_) { return; }
            if (msg.type === "event" || msg.type === "alert") {
                const topic = msg.topic || (msg.type === "alert" ? "smart-campus/events/alert" : "unknown");
                addEvent(topic, msg.data || {});
            }
        };
        ws.onclose = function () { updateServiceStatus(false); setTimeout(connect, 3000); };
    }

    connect();
    applyFilters();

})();
