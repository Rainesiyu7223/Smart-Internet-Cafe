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
