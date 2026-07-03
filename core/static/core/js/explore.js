(function () {
  const app = document.getElementById("explore-app");
  if (!app) return;

  const apiUrl = app.dataset.apiUrl;
  const today = app.dataset.today;
  const form = document.getElementById("explore-filters");
  const resultsEl = document.getElementById("explore-results");
  const countEl = document.getElementById("explore-count");
  const emptyEl = document.getElementById("explore-empty");
  const sortEl = document.getElementById("explore-sort");
  const applyBtn = document.getElementById("explore-apply");
  const clearBtn = document.getElementById("explore-clear");
  const emptyClearBtn = document.getElementById("explore-empty-clear");

  if (!apiUrl || !form || !resultsEl) return;

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function selectedAmenityIds() {
    return [...form.querySelectorAll(".explore-amenity:checked")].map((input) => input.value);
  }

  function buildQueryParams() {
    const params = new URLSearchParams();
    const city = form.querySelector("#filter-loc")?.value.trim() || "";
    const date = form.querySelector("#filter-date")?.value || "";
    const minPrice = form.querySelector("#price-min")?.value || "";
    const maxPrice = form.querySelector("#price-max")?.value || "";
    const sort = sortEl?.value || "name";

    if (city) params.set("city", city);
    if (date) params.set("date", date);
    if (minPrice !== "") params.set("min_price", minPrice);
    if (maxPrice !== "") params.set("max_price", maxPrice);
    if (sort && sort !== "name") params.set("sort", sort);

    const amenityIds = selectedAmenityIds();
    if (amenityIds.length) {
      params.set("amenity_ids", amenityIds.join(","));
    }
    return params;
  }

  function syncUrl(params) {
    const query = params.toString();
    const next = query ? `${window.location.pathname}?${query}` : window.location.pathname;
    window.history.replaceState({}, "", next);
  }

  function renderCard(bar, filterDate) {
    const price = bar.min_price != null
      ? `&euro;${Number(bar.min_price).toFixed(0)} <small>/spot</small>`
      : `<small>Price TBA</small>`;
    const rating = bar.avg_rating
      ? `<div class="card__stars"><svg viewBox="0 0 24 24"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg>${escapeHtml(bar.avg_rating)}</div>`
      : "";
    const todayLabel = filterDate === today ? " today" : "";
    const spots = `${bar.free_spots} spot${bar.free_spots === 1 ? "" : "s"} left${todayLabel}`;

    return `
      <a href="${escapeHtml(bar.url)}" class="card">
        <div class="card__img">
          <img src="${escapeHtml(bar.image_url)}" alt="${escapeHtml(bar.name)}">
          <div class="card__img-gradient"></div>
          <button class="card__fav" type="button" onclick="event.preventDefault()"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg></button>
        </div>
        <div class="card__body">
          <div class="card__name">${escapeHtml(bar.name)}</div>
          <div class="card__loc"><svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>${escapeHtml(bar.city)}, Montenegro</div>
          <div class="card__avail"><svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg>${escapeHtml(spots)}</div>
          <div class="card__foot">
            <div class="card__price">${price}</div>
            ${rating}
          </div>
        </div>
      </a>
    `;
  }

  function renderResults(data) {
    const bars = data.bars || [];
    const count = data.count || 0;
    const filterDate = data.date || today;

    if (countEl) {
      countEl.innerHTML = `<strong>${count}</strong> beach bar${count === 1 ? "" : "s"} found`;
    }

    if (!bars.length) {
      resultsEl.innerHTML = "";
      if (emptyEl) emptyEl.style.display = "";
      return;
    }

    if (emptyEl) emptyEl.style.display = "none";
    resultsEl.innerHTML = bars.map((bar) => renderCard(bar, filterDate)).join("");
  }

  async function fetchBars() {
    const params = buildQueryParams();
    syncUrl(params);
    if (applyBtn) applyBtn.disabled = true;
    try {
      const response = await fetch(`${apiUrl}?${params.toString()}`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Could not load beach bars.");
      }
      renderResults(data);
    } catch (error) {
      console.error(error);
      alert(error.message || "Could not load beach bars.");
    } finally {
      if (applyBtn) applyBtn.disabled = false;
    }
  }

  function clearFilters() {
    const cityInput = form.querySelector("#filter-loc");
    const dateInput = form.querySelector("#filter-date");
    const minInput = form.querySelector("#price-min");
    const maxInput = form.querySelector("#price-max");
    if (cityInput) cityInput.value = "";
    if (dateInput) dateInput.value = today || "";
    if (minInput) minInput.value = "";
    if (maxInput) maxInput.value = "";
    form.querySelectorAll(".explore-amenity").forEach((input) => {
      input.checked = false;
    });
    if (sortEl) sortEl.value = "name";
    fetchBars();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    fetchBars();
  });

  if (clearBtn) clearBtn.addEventListener("click", clearFilters);
  if (emptyClearBtn) emptyClearBtn.addEventListener("click", clearFilters);
  if (sortEl) {
    sortEl.addEventListener("change", () => {
      fetchBars();
    });
  }
})();
