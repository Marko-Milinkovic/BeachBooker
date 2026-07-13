(function () {
  const root = document.getElementById("admin-app");
  if (!root) return;

  const usersUrl = root.dataset.usersUrl;
  const msgEl = document.getElementById("admin-users-msg");
  const dialog = document.getElementById("admin-user-dialog");
  const form = document.getElementById("admin-user-form");
  const formError = document.getElementById("admin-form-error");
  const csrfToken = getCookie("csrftoken");

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? match[2] : "";
  }

  function showMsg(text, isError) {
    if (!msgEl) return;
    msgEl.style.display = "block";
    msgEl.textContent = text;
    msgEl.style.color = isError ? "var(--rose)" : "var(--green)";
  }

  async function api(url, method, body) {
    const options = {
      method: method,
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
    };
    if (body !== undefined) options.body = JSON.stringify(body);
    const response = await fetch(url, options);
    const data = await response.json().catch(function () {
      return { error: "Something went wrong. Please try again." };
    });
    if (!response.ok) {
      const err = new Error(data.error || "Request failed");
      err.code = data.code;
      throw err;
    }
    return data;
  }

  function openCreate() {
    document.getElementById("admin-user-dialog-title").textContent = "Add user";
    document.getElementById("admin-user-id").value = "";
    document.getElementById("admin-first-name").value = "";
    document.getElementById("admin-last-name").value = "";
    document.getElementById("admin-email").value = "";
    document.getElementById("admin-role").value = "registered";
    document.getElementById("admin-password").value = "";
    document.getElementById("admin-password").required = true;
    formError.style.display = "none";
    dialog.showModal();
  }

  function openEdit(btn) {
    document.getElementById("admin-user-dialog-title").textContent = "Edit user";
    document.getElementById("admin-user-id").value = btn.dataset.id;
    document.getElementById("admin-first-name").value = btn.dataset.firstName;
    document.getElementById("admin-last-name").value = btn.dataset.lastName;
    document.getElementById("admin-email").value = btn.dataset.email;
    document.getElementById("admin-role").value = btn.dataset.role;
    document.getElementById("admin-password").value = "";
    document.getElementById("admin-password").required = false;
    formError.style.display = "none";
    dialog.showModal();
  }

  document.getElementById("admin-add-user")?.addEventListener("click", openCreate);
  document.getElementById("admin-user-cancel")?.addEventListener("click", function () {
    dialog.close();
  });

  root.addEventListener("click", async function (event) {
    const editBtn = event.target.closest(".admin-edit-user");
    if (editBtn) {
      openEdit(editBtn);
      return;
    }
    const blockBtn = event.target.closest(".admin-block-user");
    if (blockBtn) {
      try {
        await api(usersUrl + blockBtn.dataset.id + "/", "PATCH", { is_active: false });
        window.location.reload();
      } catch (err) {
        showMsg(err.message, true);
      }
      return;
    }
    const unblockBtn = event.target.closest(".admin-unblock-user");
    if (unblockBtn) {
      try {
        await api(usersUrl + unblockBtn.dataset.id + "/", "PATCH", { is_active: true });
        window.location.reload();
      } catch (err) {
        showMsg(err.message, true);
      }
      return;
    }
    const deleteBtn = event.target.closest(".admin-delete-user");
    if (deleteBtn) {
      if (!window.confirm("Are you sure you want to delete " + deleteBtn.dataset.email + "?")) {
        return;
      }
      try {
        await api(usersUrl + deleteBtn.dataset.id + "/", "DELETE");
        window.location.reload();
      } catch (err) {
        showMsg(err.message, true);
      }
    }
  });

  form?.addEventListener("submit", async function (event) {
    event.preventDefault();
    formError.style.display = "none";
    const userId = document.getElementById("admin-user-id").value;
    const payload = {
      first_name: document.getElementById("admin-first-name").value,
      last_name: document.getElementById("admin-last-name").value,
      email: document.getElementById("admin-email").value,
      role: document.getElementById("admin-role").value,
    };
    const password = document.getElementById("admin-password").value;
    if (password) payload.password = password;

    try {
      if (userId) {
        await api(usersUrl + userId + "/", "PATCH", payload);
      } else {
        if (!password) {
          throw new Error("Password is required.");
        }
        await api(usersUrl, "POST", payload);
      }
      window.location.href = "?tab=users";
    } catch (err) {
      formError.textContent = err.message;
      formError.style.display = "block";
    }
  });
})();
