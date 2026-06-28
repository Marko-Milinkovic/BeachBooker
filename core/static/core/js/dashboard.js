(function () {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
    return match ? decodeURIComponent(match[2]) : "";
  }

  document.querySelectorAll(".owner-cancel-reservation").forEach((button) => {
    button.addEventListener("click", async () => {
      const reservationId = button.dataset.reservationId;
      if (!reservationId) return;
      if (!window.confirm("Cancel this guest booking?")) return;

      button.disabled = true;
      try {
        const response = await fetch(`/api/reservations/${reservationId}/cancel/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
          },
          body: "{}",
        });
        const data = await response.json();
        if (!response.ok) {
          alert(data.error || "Could not cancel booking.");
          button.disabled = false;
          return;
        }
        window.location.reload();
      } catch (error) {
        console.error(error);
        alert("Could not cancel booking.");
        button.disabled = false;
      }
    });
  });
})();
