(function () {
  const rows = Array.from(document.querySelectorAll(".user-row"));
  const search = document.getElementById("user_search");
  const filterButtons = Array.from(document.querySelectorAll("[data-user-filter]"));
  const emptyRow = document.getElementById("filtered_empty_row");
  const clearFilters = document.getElementById("clear_user_filters");
  let activeFilter = "all";

  function applyFilters() {
    const query = (search ? search.value : "").trim().toLowerCase();
    let visibleCount = 0;

    rows.forEach(function (row) {
      const matchesSearch = !query || row.dataset.search.includes(query);
      const matchesFilter =
        activeFilter === "all" ||
        row.dataset.status === activeFilter ||
        (activeFilter === "global" && row.dataset.global === "true") ||
        (activeFilter === "no_access" && row.dataset.noAccess === "true");
      const isVisible = matchesSearch && matchesFilter;
      row.classList.toggle("hidden", !isVisible);
      visibleCount += isVisible ? 1 : 0;
    });

    if (emptyRow) {
      emptyRow.classList.toggle("hidden", visibleCount !== 0 || rows.length === 0);
    }
  }

  filterButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      activeFilter = button.dataset.userFilter;
      filterButtons.forEach(function (candidate) {
        const isActive = candidate === button;
        candidate.classList.toggle("border-slate-900", isActive);
        candidate.classList.toggle("bg-slate-900", isActive);
        candidate.classList.toggle("text-white", isActive);
        candidate.classList.toggle("border-slate-300", !isActive);
        candidate.classList.toggle("bg-white", !isActive);
        candidate.classList.toggle("text-slate-600", !isActive);
      });
      applyFilters();
    });
  });

  if (filterButtons.length) {
    filterButtons[0].click();
  }
  if (search) {
    search.addEventListener("input", applyFilters);
  }
  if (clearFilters) {
    clearFilters.addEventListener("click", function () {
      if (search) {
        search.value = "";
      }
      if (filterButtons.length) {
        filterButtons[0].click();
      } else {
        applyFilters();
      }
    });
  }

  const actionMenuToggles = Array.from(document.querySelectorAll(".action-menu-toggle"));

  function closeActionMenus(exceptToggle) {
    actionMenuToggles.forEach(function (toggle) {
      if (toggle === exceptToggle) {
        return;
      }
      toggle.setAttribute("aria-expanded", "false");
      const menu = toggle.parentElement.querySelector(".action-menu");
      if (menu) {
        menu.classList.add("hidden");
      }
    });
  }

  actionMenuToggles.forEach(function (toggle) {
    toggle.addEventListener("click", function (event) {
      event.stopPropagation();
      const menu = toggle.parentElement.querySelector(".action-menu");
      const willOpen = menu.classList.contains("hidden");
      closeActionMenus(toggle);
      menu.classList.toggle("hidden", !willOpen);
      toggle.setAttribute("aria-expanded", String(willOpen));
    });
  });

  document.addEventListener("click", function (event) {
    if (!event.target.closest(".action-menu")) {
      closeActionMenus();
    }
  });

  const modal = document.getElementById("password_modal");
  const resetForm = document.getElementById("password_reset_form");
  const resetInput = document.getElementById("reset_temporary_password");
  const modalUser = document.getElementById("password_modal_user");

  function closePasswordModal() {
    if (!modal) {
      return;
    }
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    if (resetForm) {
      resetForm.reset();
    }
  }

  document.querySelectorAll(".reset-password-button").forEach(function (button) {
    button.addEventListener("click", function () {
      closeActionMenus();
      resetForm.action = button.dataset.passwordUrl;
      modalUser.textContent = button.dataset.userName;
      modal.classList.remove("hidden");
      modal.classList.add("flex");
      resetInput.focus();
    });
  });

  document.querySelectorAll(".password-modal-cancel").forEach(function (button) {
    button.addEventListener("click", closePasswordModal);
  });
  if (modal) {
    modal.addEventListener("click", function (event) {
      if (event.target === modal) {
        closePasswordModal();
      }
    });
  }
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeActionMenus();
      closePasswordModal();
    }
  });

  document.querySelectorAll(".user-status-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.dataset.confirm)) {
        event.preventDefault();
      }
    });
  });
})();
