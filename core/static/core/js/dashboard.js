(function () {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
    return match ? decodeURIComponent(match[2]) : "";
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify(payload || {}),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Request failed.");
    }
    return data;
  }

  document.querySelectorAll(".owner-cancel-reservation").forEach((button) => {
    button.addEventListener("click", async () => {
      const reservationId = button.dataset.reservationId;
      if (!reservationId) return;
      if (!window.confirm("Cancel this guest booking?")) return;

      button.disabled = true;
      try {
        await postJson(`/api/reservations/${reservationId}/cancel/`, {});
        window.location.reload();
      } catch (error) {
        console.error(error);
        alert(error.message || "Could not cancel booking.");
        button.disabled = false;
      }
    });
  });

  const pricingPanel = document.getElementById("tab-pricing");
  const savePricingBtn = document.getElementById("save-pricing-btn");
  if (pricingPanel && savePricingBtn) {
    savePricingBtn.addEventListener("click", async () => {
      const prices = [...pricingPanel.querySelectorAll(".pricing-category-price")].map(
        (input) => ({
          category_id: Number(input.dataset.categoryId),
          price: input.value,
        })
      );
      savePricingBtn.disabled = true;
      try {
        await postJson(pricingPanel.dataset.pricingUrl, { prices });
        alert("Prices saved.");
      } catch (error) {
        console.error(error);
        alert(error.message || "Could not save prices.");
      } finally {
        savePricingBtn.disabled = false;
      }
    });
  }

  const bundlesPanel = document.getElementById("tab-bundles");
  const bundleForm = document.getElementById("bundle-form");
  const bundleFormTitle = document.getElementById("bundle-form-title");
  const bundleFormId = document.getElementById("bundle-form-id");
  const bundleName = document.getElementById("bundle-name");
  const bundleDescription = document.getElementById("bundle-description");
  const bundlePrice = document.getElementById("bundle-price");
  const newBundleBtn = document.getElementById("new-bundle-btn");
  const bundleFormCancel = document.getElementById("bundle-form-cancel");
  let editingUpdateUrl = null;

  function showBundleForm(mode, row) {
    if (!bundleForm) return;
    bundleForm.style.display = "block";
    if (mode === "edit" && row) {
      bundleFormTitle.textContent = "Edit bundle";
      bundleFormId.value = row.dataset.bundleId;
      editingUpdateUrl = row.dataset.updateUrl;
      bundleName.value = row.querySelector(".bundle-row__name")?.textContent.trim() || "";
      bundleDescription.value = row.querySelector(".bundle-row__desc")?.textContent.trim() || "";
      bundlePrice.value = row.querySelector(".bundle-row__price")?.textContent.replace(/[^\d.]/g, "") || "";
    } else {
      bundleFormTitle.textContent = "New bundle";
      bundleFormId.value = "";
      editingUpdateUrl = null;
      bundleName.value = "";
      bundleDescription.value = "";
      bundlePrice.value = "";
    }
    bundleName.focus();
  }

  function hideBundleForm() {
    if (bundleForm) bundleForm.style.display = "none";
    editingUpdateUrl = null;
  }

  if (newBundleBtn) {
    newBundleBtn.addEventListener("click", () => showBundleForm("new"));
  }
  if (bundleFormCancel) {
    bundleFormCancel.addEventListener("click", hideBundleForm);
  }

  document.querySelectorAll(".edit-bundle-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const row = button.closest(".bundle-row");
      if (row) showBundleForm("edit", row);
    });
  });

  document.querySelectorAll(".bundle-active-toggle").forEach((toggle) => {
    toggle.addEventListener("change", async () => {
      const row = toggle.closest(".bundle-row");
      if (!row) return;
      toggle.disabled = true;
      try {
        await postJson(row.dataset.toggleUrl, { is_active: toggle.checked });
        row.classList.toggle("bundle-row--off", !toggle.checked);
      } catch (error) {
        console.error(error);
        toggle.checked = !toggle.checked;
        alert(error.message || "Could not update bundle.");
      } finally {
        toggle.disabled = false;
      }
    });
  });

  if (bundleForm && bundlesPanel) {
    bundleForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = {
        name: bundleName.value.trim(),
        description: bundleDescription.value.trim(),
        price: bundlePrice.value,
      };
      const submitBtn = bundleForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      try {
        const url = editingUpdateUrl || bundlesPanel.dataset.createBundleUrl;
        await postJson(url, payload);
        window.location.href = `${window.location.pathname}?tab=bundles`;
      } catch (error) {
        console.error(error);
        alert(error.message || "Could not save bundle.");
        submitBtn.disabled = false;
      }
    });
  }
})();
