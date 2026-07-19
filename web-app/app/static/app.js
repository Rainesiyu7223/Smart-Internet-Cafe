async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

const seatUpdateChannel = typeof BroadcastChannel === "function"
  ? new BroadcastChannel("smart-internet-cafe-seat-updates")
  : null;

function announceSeatUpdate() {
  seatUpdateChannel?.postMessage({ updatedAt: Date.now() });
  try {
    window.localStorage.setItem("smart-internet-cafe-seat-updated", String(Date.now()));
  } catch (_error) {
    // The BroadcastChannel notification is enough when storage is unavailable.
  }
}

const reservationForm = document.querySelector("#reservation-form");
if (reservationForm) {
  reservationForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = document.querySelector("#reservation-result");
    const formData = new FormData(reservationForm);
    result.textContent = "Saving reservation...";
    result.dataset.state = "loading";

    try {
      const data = await postJson("/api/reservations", {
        name: formData.get("name"),
        phone: formData.get("phone"),
      });
      result.textContent = `Reservation saved for ${data.reservation.name}. Please check in when you arrive.`;
      result.dataset.state = "success";
      reservationForm.reset();
    } catch (error) {
      result.textContent = error.message;
      result.dataset.state = "error";
    }
  });
}

const checkinForm = document.querySelector("#checkin-form");
if (checkinForm) {
  checkinForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = document.querySelector("#checkin-result");
    const formData = new FormData(checkinForm);
    result.textContent = "Checking reservation...";
    result.dataset.state = "loading";

    try {
      const data = await postJson("/api/checkin", {
        name: formData.get("name"),
      });
      result.textContent = "Check-in successful. Loading seats...";
      result.dataset.state = "success";
      window.location.href = data.redirect_url;
    } catch (error) {
      result.textContent = error.message;
      result.dataset.state = "error";
    }
  });
}

const dashboardGrid = document.querySelector("#dashboard-grid");
if (dashboardGrid) {
  const onlineCount = document.querySelector("#dashboard-online-count");
  const adminCallModal = document.querySelector("#admin-call-modal");
  const adminCallDismiss = document.querySelector("#admin-call-dismiss");
  let activeAdminCallId = null;
  let handledAdminCallId = null;

  if (adminCallDismiss && adminCallModal) {
    adminCallDismiss.addEventListener("click", () => {
      handledAdminCallId = activeAdminCallId;
      adminCallModal.hidden = true;
    });
  }

  dashboardGrid.addEventListener("click", async (event) => {
    const button = event.target.closest(".release-seat");
    if (!button) {
      return;
    }
    button.disabled = true;
    try {
      await postJson(`/api/seats/${encodeURIComponent(button.dataset.seatCode)}/release`, {});
      announceSeatUpdate();
      await refreshDashboard();
    } catch (error) {
      button.disabled = false;
      window.alert(error.message);
    }
  });

  async function refreshDashboard() {
    try {
      const response = await fetch("/api/dashboard", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Dashboard request failed");
      }

      if (onlineCount) {
        onlineCount.textContent = `${data.online_count} live seats`;
      }
      dashboardGrid.innerHTML = data.seats.length
        ? data.seats.map(renderTelemetryCard).join("")
        : renderTelemetryEmpty(data.data_source_error);
      handleAdminCall(data.seats);
    } catch (error) {
      console.error(error);
    }
  }

  seatUpdateChannel?.addEventListener("message", refreshDashboard);
  window.addEventListener("storage", (event) => {
    if (event.key === "smart-internet-cafe-seat-updated") {
      refreshDashboard();
    }
  });

  refreshDashboard();
  window.setInterval(refreshDashboard, 1000);

  function handleAdminCall(seats) {
    if (!adminCallModal) {
      return;
    }
    const a01 = Array.isArray(seats)
      ? seats.find((seat) => seat.code === "A01")
      : null;
    const isCallingAdmin = Boolean(a01 && (a01.admin_call || a01.button_pressed));
    const callId = a01 && a01.admin_call_id
      ? String(a01.admin_call_id)
      : isCallingAdmin
        ? "active-call"
        : null;

    if (!isCallingAdmin) {
      if (adminCallModal.hidden) {
        activeAdminCallId = null;
      }
      return;
    }

    activeAdminCallId = callId;
    if (callId !== handledAdminCallId) {
      adminCallModal.hidden = false;
    }
  }
}

const selectableSeatGrid = document.querySelector("#selectable-seat-grid");
if (selectableSeatGrid) {
  const result = document.querySelector("#seat-selection-result");
  const confirmationModal = document.querySelector("#seat-confirm-modal");
  const confirmationDetails = document.querySelector("#seat-confirm-details");
  const confirmationCancel = document.querySelector("#seat-confirm-cancel");
  const confirmationSubmit = document.querySelector("#seat-confirm-submit");
  let pendingSeatButton = null;

  function closeSeatConfirmation() {
    if (pendingSeatButton) {
      pendingSeatButton.classList.remove("is-selected");
    }
    pendingSeatButton = null;
    confirmationModal.hidden = true;
  }

  selectableSeatGrid.addEventListener("click", async (event) => {
    const button = event.target.closest(".selectable-seat");
    if (!button || button.disabled) {
      return;
    }
    const seatCode = button.dataset.seatCode;
    selectableSeatGrid.querySelectorAll(".selectable-seat").forEach((seat) => seat.classList.remove("is-selected"));
    button.classList.add("is-selected");
    if (result) {
      result.textContent = "";
    }
    pendingSeatButton = button;
    confirmationDetails.textContent = `${seatCode} · ${formatMetric(button.dataset.temperature, "°C")} · Humidity: ${formatHumidity(button.dataset.humidity)} · Noise ${formatMetric(button.dataset.noiseLevel, "")}`;
    confirmationModal.hidden = false;
  });

  confirmationCancel.addEventListener("click", closeSeatConfirmation);

  confirmationSubmit.addEventListener("click", async () => {
    if (!pendingSeatButton) {
      return;
    }
    const button = pendingSeatButton;
    const seatCode = button.dataset.seatCode;
    confirmationSubmit.disabled = true;
    button.disabled = true;
    try {
      await postJson(`/api/reservations/${encodeURIComponent(recommendationShell.dataset.reservationId)}/seat`, {
        seat_code: seatCode,
      });
      announceSeatUpdate();
      const detailUrl = new URL(`/seat/${encodeURIComponent(seatCode)}`, window.location.origin);
      detailUrl.searchParams.set("snapshot", "true");
      ["temperature", "humidity", "noiseLevel"].forEach((key) => {
        const value = button.dataset[key];
        if (value !== undefined && value !== "") {
          detailUrl.searchParams.set(key === "noiseLevel" ? "noise_level" : key, value);
        }
      });
      detailUrl.searchParams.set("occupied", "true");
      detailUrl.searchParams.set("reservation_id", recommendationShell.dataset.reservationId);
      window.location.href = `${detailUrl.pathname}${detailUrl.search}`;
    } catch (error) {
      button.disabled = false;
      button.classList.remove("is-selected");
      if (result) {
        result.textContent = error.message;
        result.dataset.state = "error";
      }
      confirmationSubmit.disabled = false;
      closeSeatConfirmation();
    }
  });
}

const recommendationShell = document.querySelector(".recommendation-shell");
if (recommendationShell) {
  const reservationId = recommendationShell.dataset.reservationId;
  const preview = document.querySelector("#recommendation-preview");
  const status = document.querySelector("#recommendation-status");
  const seatCount = document.querySelector("#seat-count");

  async function refreshRecommendation() {
    try {
      const response = await fetch(`/api/recommendations/${encodeURIComponent(reservationId)}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Recommendation request failed");
      }

      if (data.recommended_seat) {
        status.textContent = "Ready";
        preview.innerHTML = renderRecommendation(data.recommended_seat);
      } else {
        status.textContent = data.data_source_error ? "Connecting" : "Waiting";
      }

      if (data.seats.length) {
        seatCount.textContent = `${data.seats.length} seats`;
        selectableSeatGrid.innerHTML = data.seats.map(renderSelectableSeat).join("");
      }
    } catch (error) {
      status.textContent = "Connecting";
      console.error(error);
    }
  }

  refreshRecommendation();
  window.setInterval(refreshRecommendation, 1000);
}

const seatDetail = document.querySelector(".seat-detail-shell");
if (seatDetail) {
  const seatCode = seatDetail.dataset.seatCode;
  const occupied = document.querySelector("#seat-detail-occupied");
  const temperature = document.querySelector("#seat-detail-temperature");
  const humidity = document.querySelector("#seat-detail-humidity");
  const noise = document.querySelector("#seat-detail-noise");
  const alert = document.querySelector("#seat-detail-alert");
  let hasDisplayedLiveData = seatDetail.dataset.hasSnapshot === "true";
  let detailRefreshInFlight = false;

  async function refreshSeatDetail() {
    if (detailRefreshInFlight) {
      return;
    }
    detailRefreshInFlight = true;
    try {
      const response = await fetch(`/api/seats/${encodeURIComponent(seatCode)}/telemetry`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Seat request failed");
      }

      const hasFreshData = Boolean(data.seat.received_at);
      if (hasFreshData) {
        occupied.textContent = formatOccupancy(data.seat.occupied);
      temperature.textContent = formatMetric(data.seat.temperature, "°C");
        humidity.textContent = formatHumidity(data.seat.humidity);
        noise.textContent = formatMetric(data.seat.noise_level, "");
        hasDisplayedLiveData = true;
      }

      if (alert) {
        alert.textContent = data.data_source_error || "";
        alert.hidden = hasDisplayedLiveData || !data.data_source_error;
      }
    } catch (error) {
      if (alert) {
        alert.textContent = error.message;
        alert.hidden = false;
      }
    } finally {
      detailRefreshInFlight = false;
    }
  }

  refreshSeatDetail();
  window.setInterval(refreshSeatDetail, 1000);
}

const checkoutButton = document.querySelector("#checkout-button");
if (checkoutButton) {
  checkoutButton.addEventListener("click", async () => {
    checkoutButton.disabled = true;
    try {
      await postJson(`/api/reservations/${encodeURIComponent(checkoutButton.dataset.reservationId)}/checkout`, {});
      announceSeatUpdate();
      window.location.href = "/";
    } catch (error) {
      checkoutButton.disabled = false;
      window.alert(error.message);
    }
  });
}

function renderTelemetryCard(seat) {
  const hasData = Boolean(seat.received_at);
  const temperature = formatMetric(seat.temperature, "°C");
  const humidity = formatMetric(seat.humidity, "%");
  const noise = formatMetric(seat.noise_level, "");
  const occupied = seat.occupied === null || seat.occupied === undefined
    ? "Unknown"
    : seat.occupied
      ? "Occupied"
      : "Vacant";

  return `
    <article class="telemetry-card${hasData ? "" : " is-offline"}">
      <div class="telemetry-card-head">
        <div>
          <strong>${seat.code}</strong>
        </div>
      </div>
      <div class="metric-row">
        <div>
          <span>Temperature</span>
          <strong>${temperature}</strong>
        </div>
        <div>
          <span>Humidity</span>
          <strong>${humidity}</strong>
        </div>
      </div>
      <div class="telemetry-details">
        <span>${occupied}</span>
        <span>Noise ${noise}</span>
      </div>
      ${seat.occupied ? `<button class="release-seat" type="button" data-seat-code="${seat.code}">Release seat</button>` : ""}
      <footer>${hasData ? `Received ${seat.received_at}` : "Waiting for Raspberry Pi data"}</footer>
    </article>
  `;
}

function renderTelemetryEmpty(error) {
  const message = error
    ? "Waiting for the seat data service to reconnect…"
    : "Waiting for live seat data…";
  return `<p class="telemetry-empty">${message}</p>`;
}

function renderRecommendation(seat) {
  return `
    <article class="recommendation-card">
      <span>Recommended</span>
      <strong>${seat.code}</strong>
      <p>${formatMetric(seat.temperature, "°C")} · Humidity: ${formatHumidity(seat.humidity)} · Noise ${formatMetric(seat.noise_level, "")}</p>
    </article>
  `;
}

function renderSelectableSeat(seat) {
  const occupied = Boolean(seat.occupied);
  const temperature = formatMetric(seat.temperature, "°C");
  const humidity = formatHumidity(seat.humidity);
  const noise = formatMetric(seat.noise_level, "");
  return `
    <button class="seat-card selectable-seat" type="button" data-seat-code="${seat.code}"
      data-temperature="${seat.temperature ?? ""}" data-humidity="${seat.humidity ?? ""}"
      data-noise-level="${seat.noise_level ?? ""}" data-occupied="${occupied}"${occupied ? " disabled aria-disabled=\"true\"" : ""}>
      <div class="seat-code"><strong>${seat.code}</strong><span>${occupied ? "Occupied" : "Choose"}</span></div>
      <div class="seat-specs"><span>${seat.status}</span></div>
      <span class="seat-hover-info" role="tooltip">
        <strong>${seat.code} environment</strong>
        <span>Temperature: ${temperature}</span>
        <span>Humidity: ${humidity}</span>
        <span>Noise: ${noise}</span>
      </span>
    </button>
  `;
}

function formatOccupancy(value) {
  if (value === null || value === undefined) {
    return "Unknown";
  }
  return value ? "Occupied" : "Vacant";
}

function formatMetric(value, unit) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  const number = Number(value);
  if (Number.isNaN(number)) {
    return "--";
  }
  return `${number.toFixed(1)}${unit}`;
}

function formatHumidity(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  const humidity = Number(value);
  if (Number.isNaN(humidity)) {
    return "--";
  }
  if (humidity < 30) {
    return "Dry";
  }
  if (humidity <= 60) {
    return "Comfortable";
  }
  return "Humid";
}
