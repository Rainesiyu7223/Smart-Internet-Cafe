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

  async function refreshDashboard() {
    try {
      const response = await fetch("/api/dashboard");
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Dashboard request failed");
      }

      if (onlineCount) {
        onlineCount.textContent = `${data.online_count} live seats`;
      }
      dashboardGrid.innerHTML = data.seats.map(renderTelemetryCard).join("");
      handleAdminCall(data.seats);
    } catch (error) {
      console.error(error);
    }
  }

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

const selectableSeats = document.querySelectorAll(".selectable-seat");
if (selectableSeats.length > 0) {
  const result = document.querySelector("#seat-selection-result");
  selectableSeats.forEach((button) => {
    button.addEventListener("click", () => {
      const seatCode = button.dataset.seatCode;
      selectableSeats.forEach((seat) => seat.classList.remove("is-selected"));
      button.classList.add("is-selected");
      if (result) {
        result.textContent = `${seatCode} selected successfully. Loading current seat data...`;
        result.dataset.state = "success";
      }
      window.setTimeout(() => {
        window.location.href = `/seat/${encodeURIComponent(seatCode)}`;
      }, 900);
    });
  });
}

const seatDetail = document.querySelector(".seat-detail-shell");
if (seatDetail) {
  const seatCode = seatDetail.dataset.seatCode;
  const occupied = document.querySelector("#seat-detail-occupied");
  const temperature = document.querySelector("#seat-detail-temperature");
  const humidity = document.querySelector("#seat-detail-humidity");
  const noise = document.querySelector("#seat-detail-noise");
  const alert = document.querySelector("#seat-detail-alert");

  async function refreshSeatDetail() {
    try {
      const response = await fetch(`/api/seats/${encodeURIComponent(seatCode)}/telemetry`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Seat request failed");
      }

      occupied.textContent = formatOccupancy(data.seat.occupied);
      temperature.textContent = formatMetric(data.seat.temperature, "C");
      humidity.textContent = formatMetric(data.seat.humidity, "%");
      noise.textContent = formatMetric(data.seat.noise_level, "");

      if (alert) {
        alert.textContent = data.data_source_error || "";
        alert.hidden = !data.data_source_error;
      }
    } catch (error) {
      if (alert) {
        alert.textContent = error.message;
        alert.hidden = false;
      }
    }
  }

  refreshSeatDetail();
  window.setInterval(refreshSeatDetail, 5000);
}

function renderTelemetryCard(seat) {
  const hasData = Boolean(seat.received_at);
  const temperature = formatMetric(seat.temperature, "C");
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
      <footer>${hasData ? `Received ${seat.received_at}` : "Waiting for Raspberry Pi data"}</footer>
    </article>
  `;
}

function formatOccupancy(value) {
  if (value === null || value === undefined) {
    return "Unknown";
  }
  return value ? "Occupied" : "Vacant";
}

function formatMetric(value, unit) {
  if (value === null || value === undefined) {
    return "--";
  }
  const number = Number(value);
  if (Number.isNaN(number)) {
    return "--";
  }
  return `${number.toFixed(1)}${unit}`;
}
