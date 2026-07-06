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

  const categoriesPanel = document.getElementById("tab-pricing");
  const categoryForm = document.getElementById("category-form");
  const categoryFormTitle = document.getElementById("category-form-title");
  const categoryFormId = document.getElementById("category-form-id");
  const categoryName = document.getElementById("category-name");
  const categoryDescription = document.getElementById("category-description");
  const categoryPrice = document.getElementById("category-price");
  const newCategoryBtn = document.getElementById("new-category-btn");
  const categoryFormCancel = document.getElementById("category-form-cancel");
  let editingCategoryUrl = null;

  function showCategoryForm(mode, row) {
    if (!categoryForm) return;
    categoryForm.style.display = "block";
    if (mode === "edit" && row) {
      categoryFormTitle.textContent = "Edit category";
      categoryFormId.value = row.dataset.categoryId;
      editingCategoryUrl = row.dataset.updateUrl;
      categoryName.value = row.querySelector(".category-row__name")?.textContent.trim() || "";
      categoryDescription.value = row.querySelector(".category-row__desc")?.textContent.trim() || "";
      const priceText = row.querySelector(".category-row__price")?.textContent || "";
      categoryPrice.value = priceText.replace(/[^\d.]/g, "");
    } else {
      categoryFormTitle.textContent = "New category";
      categoryFormId.value = "";
      editingCategoryUrl = null;
      categoryName.value = "";
      categoryDescription.value = "";
      categoryPrice.value = "";
    }
    categoryName.focus();
  }

  function hideCategoryForm() {
    if (categoryForm) categoryForm.style.display = "none";
    editingCategoryUrl = null;
  }

  if (newCategoryBtn) {
    newCategoryBtn.addEventListener("click", () => showCategoryForm("new"));
  }
  if (categoryFormCancel) {
    categoryFormCancel.addEventListener("click", hideCategoryForm);
  }

  document.querySelectorAll(".edit-category-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const row = button.closest(".category-row");
      if (row) showCategoryForm("edit", row);
    });
  });

  document.querySelectorAll(".delete-category-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const row = button.closest(".category-row");
      if (!row) return;
      const sunbedCount = Number(row.dataset.sunbedCount || "0");
      if (sunbedCount > 0) {
        alert("Remove all sunbeds from this category on the layout before deleting it.");
        return;
      }
      if (!window.confirm("Delete this category?")) return;
      button.disabled = true;
      try {
        await postJson(row.dataset.deleteUrl, {});
        window.location.href = `${window.location.pathname}?tab=pricing`;
      } catch (error) {
        console.error(error);
        alert(error.message || "Could not delete category.");
        button.disabled = false;
      }
    });
  });

  if (categoryForm && categoriesPanel) {
    categoryForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = {
        name: categoryName.value.trim(),
        description: categoryDescription.value.trim(),
        price: categoryPrice.value,
      };
      const submitBtn = categoryForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      try {
        const url = editingCategoryUrl || categoriesPanel.dataset.createCategoryUrl;
        await postJson(url, payload);
        window.location.href = `${window.location.pathname}?tab=pricing`;
      } catch (error) {
        console.error(error);
        alert(error.message || "Could not save category.");
        submitBtn.disabled = false;
      }
    });
  }
})();
