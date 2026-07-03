(function () {
  const form = document.getElementById("bar-setup-form");
  if (!form) return;

  const setupUrl = form.dataset.setupUrl;
  const redirectUrl = form.dataset.redirectUrl || "/owner/?tab=settings";
  const submitBtn = document.getElementById("setup-submit-btn");
  if (!setupUrl) return;

  function getCookie(name) {
    const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
    return match ? decodeURIComponent(match[2]) : "";
  }

  function selectedAmenityIds() {
    return [...form.querySelectorAll(".setup-amenity:checked")].map((input) =>
      Number(input.value)
    );
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitBtn) submitBtn.disabled = true;
    try {
      const response = await fetch(setupUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          name: form.querySelector("#setup-name").value,
          description: form.querySelector("#setup-desc").value,
          opening_time: form.querySelector("#setup-open").value,
          closing_time: form.querySelector("#setup-close").value,
          address: form.querySelector("#setup-address").value,
          city: form.querySelector("#setup-city").value,
          map_url: form.querySelector("#setup-maps").value,
          amenity_ids: selectedAmenityIds(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Could not create beach bar.");
      }
      window.location.href = data.redirect_url || redirectUrl;
    } catch (error) {
      console.error(error);
      alert(error.message || "Could not create beach bar.");
      if (submitBtn) submitBtn.disabled = false;
    }
  });
})();
