(function () {
  const panel = document.getElementById("tab-settings");
  const form = document.getElementById("bar-settings-form");
  if (!panel || !form) return;

  const settingsUrl = panel.dataset.settingsUrl;
  const saveBtn = document.getElementById("save-settings-btn");
  if (!settingsUrl) return;

  function getCookie(name) {
    const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
    return match ? decodeURIComponent(match[2]) : "";
  }

  function selectedAmenityIds() {
    return [...form.querySelectorAll(".bar-amenity:checked")].map((input) =>
      Number(input.value)
    );
  }

  function applyPayload(settings) {
    form.querySelector("#bar-name").value = settings.name || "";
    form.querySelector("#bar-desc").value = settings.description || "";
    form.querySelector("#bar-open").value = settings.opening_time || "";
    form.querySelector("#bar-close").value = settings.closing_time || "";
    form.querySelector("#bar-address").value = settings.address || "";
    form.querySelector("#bar-city").value = settings.city || "";
    form.querySelector("#bar-maps").value = settings.map_url || "";

    const selected = new Set(
      (settings.amenities || [])
        .filter((item) => item.selected)
        .map((item) => String(item.id))
    );
    form.querySelectorAll(".bar-amenity").forEach((input) => {
      input.checked = selected.has(input.value);
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saveBtn) saveBtn.disabled = true;
    try {
      const response = await fetch(settingsUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          name: form.querySelector("#bar-name").value,
          description: form.querySelector("#bar-desc").value,
          opening_time: form.querySelector("#bar-open").value,
          closing_time: form.querySelector("#bar-close").value,
          address: form.querySelector("#bar-address").value,
          city: form.querySelector("#bar-city").value,
          map_url: form.querySelector("#bar-maps").value,
          amenity_ids: selectedAmenityIds(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Could not save settings.");
      }
      applyPayload(data.settings);
      alert("Settings saved.");
    } catch (error) {
      console.error(error);
      alert(error.message || "Could not save settings.");
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  });
})();
