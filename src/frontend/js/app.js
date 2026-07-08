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

    // Cấu hình giám sát hoạt động dịch vụ (A1..A7)
    const TIMEOUT_LIMIT = 20000; // Dịch vụ offline nếu quá 20s không có tin nhắn MQTT
    let lastActive = {
        a1: Date.now(),
        a2: Date.now(),
        a3: Date.now(),
        a4: Date.now(),
        a5: Date.now(),
        a7: Date.now()
    };

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
        const savedTheme = localStorage.getItem("a6-theme") || "dark";
        if (savedTheme === "dark") {
            document.body.className = "dark-theme";
            btnTheme.textContent = "Chế độ sáng";
        } else {
            document.body.className = "light-theme";
            btnTheme.textContent = "Chế độ tối";
        }
        btnTheme.addEventListener("click", () => {
            const isDark = document.body.classList.toggle("dark-theme");
            if (isDark) {
                document.body.classList.remove("light-theme");
                btnTheme.textContent = "Chế độ sáng";
                localStorage.setItem("a6-theme", "dark");
            } else {
                document.body.classList.add("light-theme");
                btnTheme.textContent = "Chế độ tối";
                localStorage.setItem("a6-theme", "light");
            }
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
                const itemGate = (
                    ev.data.gate_id || 
                    ev.data.gateId || 
                    ev.data.door_id || 
                    ev.data.location || 
                    ""
                ).toLowerCase();
                
                const filter = currentFilterGate.toLowerCase();
                
                // Chuan hoa xoa khoang trang va ky tu dac biet de so sanh
                const normItem = itemGate.replace(/[\s_-]/g, "");
                const normFilter = filter.replace(/[\s_-]/g, "");
                
                let isMatch = normItem.includes(normFilter);
                
                // Anh xa tu dong nghia cho Cong A
                if (!isMatch) {
                    if (filter === "gate-a") {
                        isMatch = itemGate.includes("cổng chính a") || 
                                  itemGate.includes("main gate a") || 
                                  itemGate.includes("gate a") || 
                                  itemGate.includes("gate-01");
                    }
                }
                
                if (!isMatch) return false;
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
            row.className = `event-row ${meta.rowClass || 'row-default'}`;
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
            const isGranted = (d.access_result === "granted" || d.access_result === "true" || d.allow === true || d.accessResult === "ALLOWED");
            return {
                time: time,
                tagClass: isGranted ? "tag-success" : "tag-danger",
                rowClass: isGranted ? "row-success" : "row-danger",
                tagText: "[A6_ACCESS]",
                desc: isGranted ? `Xác thực thành công. Mã định danh: <strong>${d.uid || d.cardId || 'N/A'}</strong>` : `Xác thực thất bại. Cảnh báo thẻ: <strong>${d.uid || d.cardId || 'N/A'}</strong>`
            };
        }
        if (topic === "smart-campus/events/sensor") {
            const status = d.status || "unknown";
            let tClass = "tag-default";
            let rClass = "row-default";
            if (status === "danger") { tClass = "tag-danger"; rClass = "row-danger"; }
            else if (status === "warning") { tClass = "tag-warning"; rClass = "row-warning"; }
            else if (status === "normal") { tClass = "tag-success"; rClass = "row-success"; }
            return {
                time: time,
                tagClass: tClass,
                rowClass: rClass,
                tagText: "[A6_SENSOR]",
                desc: `Trạng thái môi trường: <strong>${status.toUpperCase()}</strong> (${d.location || 'N/A'}) - ${d.reason || ''}`
            };
        }
        if (topic === "smart-campus/events/camera") {
            return {
                time: time,
                tagClass: "tag-success",
                rowClass: "row-success",
                tagText: "[A6_VISION]",
                desc: `Phát hiện vật thể/người qua vùng quét: <strong>${d.location || 'N/A'}</strong>`
            };
        }
        if (topic === "smart-campus/events/alert") {
            const sev = (d.severity || "low").toLowerCase();
            let tClass = "tag-default";
            let rClass = "row-default";
            if (sev === "critical") { tClass = "tag-danger"; rClass = "row-danger"; }
            else if (sev === "high") { tClass = "tag-warning"; rClass = "row-warning"; }
            return {
                time: time,
                tagClass: tClass,
                rowClass: rClass,
                tagText: "[CORE_ALERT]",
                desc: `TÍN HIỆU <strong>${sev.toUpperCase()}</strong>: ${d.message || d.alert_type}`
            };
        }

        return { time: time, tagClass: "tag-default", rowClass: "row-default", tagText: "[SYSTEM]", desc: escapeHtml(d.event_type || "Sự kiện ngoại vi") };
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

        // Cập nhật timestamp nhận sự kiện cuối cùng
        if (topic === "smart-campus/events/sensor") {
            lastActive.a1 = Date.now();
        } else if (topic === "smart-campus/events/camera") {
            lastActive.a2 = Date.now();
            lastActive.a4 = Date.now(); // AI Vision hoạt động khi camera quét
        } else if (topic === "smart-campus/events/access") {
            lastActive.a3 = Date.now();
        } else if (topic === "smart-campus/events/alert") {
            lastActive.a7 = Date.now();
        }
        // Giả lập Analytics luôn xử lý phân tích
        lastActive.a5 = Date.now();

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
                const reqId = "req-" + Math.random().toString(36).substr(2, 9);
                const isoTime = new Date().toISOString();

                const response = await fetch(API_ACCESS_CHECK, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${AUTH_TOKEN}` },
                    body: JSON.stringify({ 
                        requestId: reqId,
                        cardId: uid, 
                        gateId: gate_id, 
                        direction: direction,
                        timestamp: isoTime
                    })
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

    function checkServicesLiveness() {
        const now = Date.now();
        let onlineCount = 0;
        const isWsConnected = (ws && ws.readyState === WebSocket.OPEN);

        const services = [
            { id: "status-a1", key: "a1" },
            { id: "status-a2", key: "a2" },
            { id: "status-a3", key: "a3" },
            { id: "status-a4", key: "a4" },
            { id: "status-a5", key: "a5" },
            { id: "status-a7", key: "a7" }
        ];

        services.forEach(srv => {
            const el = document.getElementById(srv.id);
            if (!el) return;

            const isAlive = isWsConnected && (now - lastActive[srv.key] < TIMEOUT_LIMIT);
            el.className = `srv-badge ${isAlive ? "online" : "offline"}`;
            el.textContent = isAlive ? "BÌNH THƯỜNG" : "MẤT KẾT NỐI";
            if (isAlive) onlineCount++;
        });

        if (metricServices) {
            metricServices.textContent = `${onlineCount}/${services.length}`;
        }
    }

    // Chạy giám sát dịch vụ định kỳ mỗi 3 giây
    setInterval(checkServicesLiveness, 3000);

    function updateServiceStatus(isOnline) {
        if (isOnline) {
            lastActive.a1 = Date.now();
            lastActive.a2 = Date.now();
            lastActive.a3 = Date.now();
            lastActive.a4 = Date.now();
            lastActive.a5 = Date.now();
            lastActive.a7 = Date.now();
        }
        checkServicesLiveness();

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
