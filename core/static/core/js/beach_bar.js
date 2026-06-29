(function () {
  function initBeachBarBooking() {
    const root = document.getElementById("beach-bar-booking");
    if (!root) return;

    const apiUrl = root.dataset.apiUrl;
    const todayIso = root.dataset.today;
    let currentDate = root.dataset.initialDate;
    const isAuthenticated = root.dataset.isAuthenticated === "true";
    const loginUrl = root.dataset.loginUrl;
    const bookUrl = root.dataset.bookUrl;
    const bookingsUrl = root.dataset.bookingsUrl;
    const selected = new Map();

    const gridEl = document.getElementById("sunbed-grid");
    const dateInput = document.getElementById("bp-date");
    const dateStrip = document.getElementById("date-strip");
    const infoAvailability = document.getElementById("info-availability");
    const selDisplay = document.getElementById("sel-display");
    const sumBed = document.getElementById("sum-bed");
    const sumPrice = document.getElementById("sum-price");
    const sumExtras = document.getElementById("sum-extras");
    const sumExtrasRow = document.getElementById("sum-extras-row");
    const sumTotal = document.getElementById("sum-total");
    const reserveBtn = document.getElementById("reserve-btn");
    const bundleAddons = document.getElementById("bundle-addons");
    const selectedBundles = new Set();

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function formatAvailability(freeSpots, dateIso) {
      if (dateIso === todayIso) {
        return `${freeSpots} available today`;
      }
      const formatted = new Date(dateIso + "T12:00:00").toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      });
      return `${freeSpots} available on ${formatted}`;
    }

    function updateUrl(dateIso) {
      const url = new URL(window.location.href);
      url.searchParams.set("date", dateIso);
      window.history.replaceState({}, "", url);
    }

    function updateDateUi(dateIso) {
      currentDate = dateIso;
      if (dateInput) dateInput.value = dateIso;
      if (dateStrip) {
        dateStrip.querySelectorAll(".date-chip").forEach((chip) => {
          chip.classList.toggle("on", chip.dataset.date === dateIso);
        });
      }
      updateUrl(dateIso);
    }

    function clearBundleSelection() {
      selectedBundles.clear();
      if (bundleAddons) {
        bundleAddons.querySelectorAll(".addon").forEach((el) => {
          el.classList.remove("on");
          el.setAttribute("aria-pressed", "false");
        });
      }
    }

    function clearSelection() {
      selected.clear();
      clearBundleSelection();
      updateSummary();
      if (gridEl) {
        gridEl.querySelectorAll(".sb--pick").forEach((el) => {
          el.classList.remove("sb--pick");
          el.classList.add("sb--free");
        });
      }
    }

    function getCookie(name) {
      const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
      return match ? decodeURIComponent(match[2]) : "";
    }

    function updateSummary() {
      const spots = [...selected.values()];
      const spotTotal = spots.reduce((sum, spot) => sum + parseFloat(spot.price), 0);
      let extrasTotal = 0;
      if (bundleAddons) {
        bundleAddons.querySelectorAll(".addon.on").forEach((el) => {
          extrasTotal += parseFloat(el.dataset.price);
        });
      }
      if (selDisplay) {
        selDisplay.value = spots.map((s) => s.label).join(", ");
      }
      if (sumBed) sumBed.textContent = String(spots.length);
      if (sumPrice) sumPrice.textContent = `€${spotTotal}`;
      if (sumExtras) sumExtras.textContent = `€${extrasTotal}`;
      if (sumExtrasRow) {
        sumExtrasRow.style.display = bundleAddons ? "" : "none";
      }
      if (sumTotal) sumTotal.textContent = `€${spotTotal + extrasTotal}`;
      if (reserveBtn) {
        reserveBtn.disabled = spots.length === 0;
        reserveBtn.style.opacity = spots.length > 0 ? "1" : "0.5";
      }
    }

    function toggleBundle(el) {
      const bundleId = Number(el.dataset.bundleId);
      if (!bundleId) return;

      if (selectedBundles.has(bundleId)) {
        selectedBundles.delete(bundleId);
        el.classList.remove("on");
        el.setAttribute("aria-pressed", "false");
      } else {
        selectedBundles.add(bundleId);
        el.classList.add("on");
        el.setAttribute("aria-pressed", "true");
      }
      updateSummary();
    }

    function bindBundleClicks() {
      if (!bundleAddons) return;
      bundleAddons.addEventListener("click", (event) => {
        const addon = event.target.closest(".addon");
        if (!addon || !bundleAddons.contains(addon)) return;
        event.preventDefault();
        toggleBundle(addon);
      });
      bundleAddons.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        const addon = event.target.closest(".addon");
        if (!addon || !bundleAddons.contains(addon)) return;
        event.preventDefault();
        toggleBundle(addon);
      });
    }

    function renderCell(cell) {
      const clickable = !cell.is_taken;
      const classes = `sb ${cell.css_classes}${clickable ? " sb--clickable" : ""}`;
      const price = Math.round(parseFloat(cell.price));
      const tooltip = clickable
        ? `<span class="sb-tooltip">${escapeHtml(cell.category)} &middot; &euro;${price}</span>`
        : "";
      const attrs = clickable
        ? ` data-sunbed-id="${cell.id}" data-label="${escapeHtml(cell.label)}" data-price="${cell.price}" role="button" tabindex="0"`
        : ` data-sunbed-id="${cell.id}" data-label="${escapeHtml(cell.label)}" data-price="${cell.price}"`;

      return `<div class="${classes}"${attrs}>${escapeHtml(cell.label)}${tooltip}</div>`;
    }

    function renderGrid(rows) {
      if (!gridEl) return;
      gridEl.innerHTML = rows
        .map(
          (row) =>
            `<div class="bmap__seats">${row.map((cell) => renderCell(cell)).join("")}</div>`
        )
        .join("");
      bindSpotClicks();
      restoreSelection();
    }

    function restoreSelection() {
      if (!gridEl) return;
      gridEl.querySelectorAll(".sb--clickable").forEach((el) => {
        const id = Number(el.dataset.sunbedId);
        if (selected.has(id)) {
          el.classList.remove("sb--free");
          el.classList.add("sb--pick");
        }
      });
    }

    function toggleSpot(el) {
      if (el.classList.contains("sb--taken")) return;

      const id = Number(el.dataset.sunbedId);
      if (selected.has(id)) {
        selected.delete(id);
        el.classList.remove("sb--pick");
        el.classList.add("sb--free");
      } else {
        selected.set(id, {
          id,
          label: el.dataset.label,
          price: el.dataset.price,
        });
        el.classList.remove("sb--free");
        el.classList.add("sb--pick");
      }
      updateSummary();
    }

    function bindSpotClicks() {
      if (!gridEl) return;
      gridEl.querySelectorAll(".sb--clickable").forEach((el) => {
        el.addEventListener("click", () => toggleSpot(el));
        el.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleSpot(el);
          }
        });
      });
    }

    async function loadMap(dateIso) {
      const response = await fetch(`${apiUrl}?date=${encodeURIComponent(dateIso)}`);
      if (!response.ok) throw new Error("Failed to load sunbed map");
      const data = await response.json();
      updateDateUi(data.date);
      if (infoAvailability) {
        infoAvailability.textContent = formatAvailability(data.free_spots, data.date);
      }
      renderGrid(data.rows);
    }

    async function changeDate(dateIso) {
      if (dateIso === currentDate) return;
      clearSelection();
      try {
        await loadMap(dateIso);
      } catch (error) {
        console.error(error);
      }
    }

    if (dateStrip) {
      dateStrip.querySelectorAll(".date-chip").forEach((chip) => {
        chip.addEventListener("click", (event) => {
          event.preventDefault();
          changeDate(chip.dataset.date);
        });
      });
    }

    if (dateInput) {
      dateInput.addEventListener("change", () => {
        if (dateInput.value) changeDate(dateInput.value);
      });
    }

    if (reserveBtn) {
      reserveBtn.addEventListener("click", async () => {
        if (selected.size === 0) return;
        if (!isAuthenticated) {
          const next = encodeURIComponent(
            window.location.pathname + window.location.search
          );
          window.location.href = `${loginUrl}?next=${next}`;
          return;
        }

        reserveBtn.disabled = true;
        reserveBtn.textContent = "Booking…";
        try {
          const response = await fetch(bookUrl, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({
              date: currentDate,
              sunbed_ids: [...selected.keys()],
              bundle_ids: [...selectedBundles],
            }),
          });
          const data = await response.json();
          if (!response.ok) {
            alert(data.error || "Booking failed. Please try again.");
            await loadMap(currentDate);
            clearSelection();
            return;
          }
          window.location.href = bookingsUrl;
        } catch (error) {
          console.error(error);
          alert("Booking failed. Please try again.");
        } finally {
          reserveBtn.textContent = "Book now";
          updateSummary();
        }
      });
    }

    bindSpotClicks();
    bindBundleClicks();
    updateSummary();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initBeachBarBooking);
  } else {
    initBeachBarBooking();
  }
})();
