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
  const updatedAt = document.querySelector("#dashboard-updated-at");

  async function refreshDashboard() {
    try {
      const response = await fetch("/api/dashboard");
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Dashboard request failed");
      }

      onlineCount.textContent = `${data.online_count} live seats`;
      updatedAt.textContent = `Updated ${new Date().toLocaleTimeString()}`;
      dashboardGrid.innerHTML = data.seats.map(renderTelemetryCard).join("");
    } catch (error) {
      updatedAt.textContent = error.message;
      updatedAt.dataset.state = "error";
    }
  }

  refreshDashboard();
  window.setInterval(refreshDashboard, 3000);
}

function renderTelemetryCard(seat) {
  const hasData = Boolean(seat.received_at);
  const temperature = formatMetric(seat.temperature, "C");
  const humidity = formatMetric(seat.humidity, "%");
  const noise = formatMetric(seat.noise_level, "");
  const occupied = seat.motion_detected === null || seat.motion_detected === undefined
    ? "Unknown"
    : seat.motion_detected
      ? "Occupied"
      : "Vacant";

  return `
    <article class="telemetry-card${hasData ? "" : " is-offline"}">
      <div class="telemetry-card-head">
        <div>
          <strong>${seat.code}</strong>
          <span>${seat.area}</span>
        </div>
        <small>${hasData ? "Live" : "No data"}</small>
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
