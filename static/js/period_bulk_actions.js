document.addEventListener("DOMContentLoaded", function () {
  var checkboxes = Array.prototype.slice.call(document.querySelectorAll(".period-select-checkbox"));
  if (!checkboxes.length) return;

  var monthSelectAlls = Array.prototype.slice.call(document.querySelectorAll(".month-select-all"));
  var pageSelectAll = document.querySelector(".page-select-all");
  var bar = document.getElementById("bulk_action_bar");
  var countEl = document.getElementById("bulk_selected_count");
  var buttonsEl = document.getElementById("bulk_action_buttons");
  var clearBtn = document.getElementById("bulk_clear_selection");

  var transitionForm = document.getElementById("bulk_transition_form");
  var transitionTargetInput = document.getElementById("bulk_transition_target_status");

  var reopenModal = document.getElementById("bulk_reopen_modal");
  var reopenForm = document.getElementById("bulk_reopen_form");
  var reopenCountEl = document.getElementById("bulk_reopen_modal_count");
  var reopenReasonInput = document.getElementById("bulk_reopen_reason_input");

  var validTransitions = window.PERIOD_VALID_TRANSITIONS || {};
  var transitionLabels = window.PERIOD_TRANSITION_LABELS || {};

  // TRANSITION_LABELS is keyed by current status ("the action taken FROM this
  // status"); bulk buttons are keyed by target status instead, since that's
  // what a mixed selection actually groups by. VALID_TRANSITIONS is a 1:1
  // cycle, so inverting it here is safe -- every target has exactly one
  // current-status source.
  var targetLabels = {};
  Object.keys(validTransitions).forEach(function (currentStatus) {
    var target = validTransitions[currentStatus];
    targetLabels[target] = transitionLabels[currentStatus] || target;
  });

  function checkboxesInMonth(monthKey) {
    return checkboxes.filter(function (cb) { return cb.dataset.monthKey === monthKey; });
  }

  function syncMonthSelectAll(monthKey) {
    var selectAll = monthSelectAlls.filter(function (el) { return el.dataset.monthKey === monthKey; })[0];
    if (!selectAll) return;
    var inGroup = checkboxesInMonth(monthKey);
    var checkedCount = inGroup.filter(function (cb) { return cb.checked; }).length;
    selectAll.checked = inGroup.length > 0 && checkedCount === inGroup.length;
    selectAll.indeterminate = checkedCount > 0 && checkedCount < inGroup.length;
  }

  function syncPageSelectAll() {
    if (!pageSelectAll) return;
    var checkedCount = checkboxes.filter(function (cb) { return cb.checked; }).length;
    pageSelectAll.checked = checkedCount === checkboxes.length;
    pageSelectAll.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
  }

  function syncAllSelectAlls() {
    monthSelectAlls.forEach(function (el) { syncMonthSelectAll(el.dataset.monthKey); });
    syncPageSelectAll();
  }

  function setHiddenPeriodIds(form, ids) {
    Array.prototype.slice.call(form.querySelectorAll('input[name="period_ids"]')).forEach(function (el) {
      el.parentNode.removeChild(el);
    });
    ids.forEach(function (id) {
      var input = document.createElement("input");
      input.type = "hidden";
      input.name = "period_ids";
      input.value = id;
      form.appendChild(input);
    });
  }

  function updateBar() {
    var selected = checkboxes.filter(function (cb) { return cb.checked; });

    if (!selected.length) {
      bar.classList.add("hidden");
      buttonsEl.innerHTML = "";
      return;
    }

    bar.classList.remove("hidden");
    countEl.textContent = String(selected.length);

    var idsByTarget = {};
    selected.forEach(function (cb) {
      var target = validTransitions[cb.dataset.currentStatus];
      if (!target) return;
      if (!idsByTarget[target]) idsByTarget[target] = [];
      idsByTarget[target].push(cb.dataset.periodId);
    });

    buttonsEl.innerHTML = "";
    Object.keys(idsByTarget).forEach(function (target) {
      var ids = idsByTarget[target];
      var label = targetLabels[target] || target;
      var button = document.createElement("button");
      button.type = "button";
      button.className = "action-button " + (target === "REOPENED" ? "btn-outline" : "btn-neutral");
      button.textContent = label + " selected (" + ids.length + ")";
      button.addEventListener("click", function () {
        submitBulkTransition(target, label, ids);
      });
      buttonsEl.appendChild(button);
    });
  }

  function submitBulkTransition(target, label, ids) {
    if (target === "REOPENED") {
      setHiddenPeriodIds(reopenForm, ids);
      if (reopenCountEl) {
        reopenCountEl.textContent = ids.length + " reporting period(s) will be reopened.";
      }
      if (reopenModal) {
        reopenModal.classList.remove("hidden");
        reopenModal.classList.add("flex");
      }
      if (reopenReasonInput) { reopenReasonInput.focus(); }
      return;
    }

    var confirmMessage = "Move " + ids.length + " selected reporting period(s) to '" + label + "'?";
    if (!window.confirm(confirmMessage)) return;

    transitionTargetInput.value = target;
    setHiddenPeriodIds(transitionForm, ids);
    transitionForm.submit();
  }

  checkboxes.forEach(function (cb) {
    cb.addEventListener("change", function () {
      syncMonthSelectAll(cb.dataset.monthKey);
      syncPageSelectAll();
      updateBar();
    });
  });

  monthSelectAlls.forEach(function (selectAll) {
    selectAll.addEventListener("change", function () {
      var checked = selectAll.checked;
      checkboxesInMonth(selectAll.dataset.monthKey).forEach(function (cb) {
        cb.checked = checked;
      });
      selectAll.indeterminate = false;
      syncPageSelectAll();
      updateBar();
    });
  });

  if (pageSelectAll) {
    pageSelectAll.addEventListener("change", function () {
      var checked = pageSelectAll.checked;
      checkboxes.forEach(function (cb) { cb.checked = checked; });
      pageSelectAll.indeterminate = false;
      syncAllSelectAlls();
      updateBar();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      checkboxes.forEach(function (cb) { cb.checked = false; });
      monthSelectAlls.forEach(function (el) {
        el.checked = false;
        el.indeterminate = false;
      });
      if (pageSelectAll) {
        pageSelectAll.checked = false;
        pageSelectAll.indeterminate = false;
      }
      updateBar();
    });
  }

  function closeReopenModal() {
    if (!reopenModal) return;
    reopenModal.classList.add("hidden");
    reopenModal.classList.remove("flex");
    if (reopenForm) { reopenForm.reset(); }
  }

  document.querySelectorAll(".bulk-reopen-cancel").forEach(function (button) {
    button.addEventListener("click", closeReopenModal);
  });

  if (reopenModal) {
    reopenModal.addEventListener("click", function (event) {
      if (event.target === reopenModal) { closeReopenModal(); }
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { closeReopenModal(); }
  });
});
