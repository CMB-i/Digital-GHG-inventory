(function () {
  "use strict";

  // Elements
  const openDrawerBtn = document.getElementById("open_create_drawer_btn");
  const closeDrawerBtn = document.getElementById("close_create_drawer_btn");
  const closeDrawerSecBtn = document.getElementById("close_create_drawer_secondary");
  const drawer = document.getElementById("create_drawer");
  const backdrop = document.getElementById("drawer_backdrop");
  const scopeTypeSelect = document.getElementById("template_scope_type");
  const scopeSiteContainer = document.getElementById("scope_site_container");
  const createForm = document.getElementById("create_template_form");
  const feedbackContainer = document.getElementById("feedback_container");

  const previewTitle = document.getElementById("preview_title");
  const previewSubtitle = document.getElementById("preview_subtitle");
  const previewActions = document.getElementById("preview_actions");
  const previewSearch = document.getElementById("preview_search");
  const previewExportBtn = document.getElementById("preview_export_btn");
  const previewEmptyState = document.getElementById("preview_empty_state");
  const previewLoadingState = document.getElementById("preview_loading_state");
  const previewTableWrapper = document.getElementById("preview_table_wrapper");
  const previewTbody = document.getElementById("preview_tbody");

  let activePreviewData = [];

  // Feedback messaging helper
  function showFeedback(message, type = "success") {
    feedbackContainer.classList.remove("hidden", "border-emerald-200", "bg-emerald-50", "text-emerald-700", "border-red-200", "bg-red-50", "text-red-700");
    if (type === "success") {
      feedbackContainer.classList.add("border-emerald-200", "bg-emerald-50", "text-emerald-700");
    } else {
      feedbackContainer.classList.add("border-red-200", "bg-red-50", "text-red-700");
    }
    feedbackContainer.textContent = message;
    feedbackContainer.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Drawer Toggles
  function openDrawer() {
    backdrop.classList.remove("hidden");
    setTimeout(() => {
      backdrop.classList.remove("opacity-0");
      drawer.classList.remove("translate-x-full");
    }, 50);
  }

  function closeDrawer() {
    drawer.classList.add("translate-x-full");
    backdrop.classList.add("opacity-0");
    setTimeout(() => {
      backdrop.classList.add("hidden");
    }, 300);
    createForm.reset();
    scopeSiteContainer.classList.add("hidden");
  }

  if (openDrawerBtn) openDrawerBtn.addEventListener("click", openDrawer);
  if (closeDrawerBtn) closeDrawerBtn.addEventListener("click", closeDrawer);
  if (closeDrawerSecBtn) closeDrawerSecBtn.addEventListener("click", closeDrawer);
  if (backdrop) {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) closeDrawer();
    });
  }

  // Scope Type Visibility Toggle
  if (scopeTypeSelect) {
    scopeTypeSelect.addEventListener("change", function () {
      if (this.value === "site") {
        scopeSiteContainer.classList.remove("hidden");
        document.getElementById("template_scope_site_id").setAttribute("required", "required");
      } else {
        scopeSiteContainer.classList.add("hidden");
        document.getElementById("template_scope_site_id").removeAttribute("required");
      }
    });
  }

  // Handle Form Submit
  if (createForm) {
    createForm.addEventListener("submit", function (e) {
      e.preventDefault();

      // Gather multi-select checklist values
      const formIds = Array.from(createForm.querySelectorAll("input[name='form_ids']:checked")).map(el => parseInt(el.value, 10));
      const siteIds = Array.from(createForm.querySelectorAll("input[name='site_ids']:checked")).map(el => parseInt(el.value, 10));
      
      const startMonthVal = createForm.querySelector("select[name='start_month']").value;
      const startYearVal = createForm.querySelector("select[name='start_year']").value;
      const endMonthVal = createForm.querySelector("select[name='end_month']").value;
      const endYearVal = createForm.querySelector("select[name='end_year']").value;

      const payload = {
        name: document.getElementById("template_name").value,
        code: document.getElementById("template_code").value,
        description: document.getElementById("template_description").value,
        scope_type: scopeTypeSelect.value,
        scope_site_id: scopeTypeSelect.value === "site" ? parseInt(document.getElementById("template_scope_site_id").value, 10) : null,
        config_json: {
          form_ids: formIds,
          site_ids: siteIds,
          start_month: startMonthVal ? parseInt(startMonthVal, 10) : null,
          start_year: startYearVal ? parseInt(startYearVal, 10) : null,
          end_month: endMonthVal ? parseInt(endMonthVal, 10) : null,
          end_year: endYearVal ? parseInt(endYearVal, 10) : null
        }
      };

      fetch("/module/RPTBLD/api/templates", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === "success") {
          closeDrawer();
          showFeedback("Report template created successfully.", "success");
          setTimeout(() => {
            window.location.reload();
          }, 1000);
        } else {
          showFeedback(data.message || "Failed to create report template.", "error");
        }
      })
      .catch(err => {
        console.error(err);
        showFeedback("An unexpected network error occurred.", "error");
      });
    });
  }

  // Delete Template Action
  document.querySelectorAll(".delete-template-btn").forEach(btn => {
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      const templateId = this.dataset.templateId;
      if (!confirm("Are you sure you want to delete this report template?")) {
        return;
      }

      fetch(`/module/RPTBLD/api/templates/${templateId}`, {
        method: "DELETE"
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === "success") {
          showFeedback("Report template deleted.", "success");
          // Remove from list DOM
          const card = document.querySelector(`.template-card[data-template-id="${templateId}"]`);
          if (card) card.remove();
          // Reset preview panel if deleted template was active
          if (previewExportBtn.getAttribute("href") && previewExportBtn.getAttribute("href").includes(`/${templateId}/`)) {
            resetPreviewPane();
          }
        } else {
          showFeedback(data.message || "Failed to delete template.", "error");
        }
      })
      .catch(err => {
        console.error(err);
        showFeedback("Error deleting template.", "error");
      });
    });
  });

  function resetPreviewPane() {
    previewTitle.textContent = "Report Preview";
    previewSubtitle.textContent = "Select a report template to preview aggregated data.";
    previewActions.classList.add("hidden");
    previewEmptyState.classList.remove("hidden");
    previewLoadingState.classList.add("hidden");
    previewTableWrapper.classList.add("hidden");
    activePreviewData = [];
  }

  // Preview Action
  document.querySelectorAll(".preview-template-btn").forEach(btn => {
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      const templateId = this.dataset.templateId;
      const card = document.querySelector(`.template-card[data-template-id="${templateId}"]`);
      const templateName = card ? card.querySelector("h3").textContent : "Report";
      
      // Update preview state to loading
      previewEmptyState.classList.add("hidden");
      previewTableWrapper.classList.add("hidden");
      previewLoadingState.classList.remove("hidden");
      previewActions.classList.add("hidden");
      previewTitle.textContent = `Preview: ${templateName}`;
      previewSubtitle.textContent = "Fetching environmental data...";

      fetch(`/module/RPTBLD/api/templates/${templateId}/preview`)
      .then(res => res.json())
      .then(resData => {
        previewLoadingState.classList.add("hidden");
        if (resData.status === "success") {
          activePreviewData = resData.data;
          renderPreviewTable(activePreviewData);
          
          previewSubtitle.textContent = `Aggregated metrics from ${activePreviewData.length} records.`;
          previewActions.classList.remove("hidden");
          previewExportBtn.setAttribute("href", `/module/RPTBLD/api/templates/${templateId}/export`);
        } else {
          previewSubtitle.textContent = "Error loading report data.";
          previewEmptyState.classList.remove("hidden");
          alert(resData.message || "Failed to fetch preview data.");
        }
      })
      .catch(err => {
        console.error(err);
        previewLoadingState.classList.add("hidden");
        previewSubtitle.textContent = "Connection error.";
        previewEmptyState.classList.remove("hidden");
        alert("Failed to connect to server.");
      });
    });
  });

  // Render Table helper
  function renderPreviewTable(records) {
    previewTbody.innerHTML = "";
    if (records.length === 0) {
      previewTbody.innerHTML = `
        <tr>
          <td colspan="7" class="py-10 text-center text-slate-500 font-medium">
            No approved submission data matching template criteria was found.
          </td>
        </tr>
      `;
      previewTableWrapper.classList.remove("hidden");
      return;
    }

    records.forEach(r => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50 transition-colors border-b border-slate-100";
      
      let displayValue = r.value;
      let alignClass = "text-left";
      if (typeof displayValue === "number") {
        displayValue = displayValue.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 });
        alignClass = "text-right font-mono font-semibold text-slate-900";
      }

      tr.innerHTML = `
        <td class="py-3 pr-3 whitespace-nowrap font-medium text-slate-800">${r.period_label}</td>
        <td class="py-3 pr-3">${r.site_name}</td>
        <td class="py-3 pr-3">${r.form_name}</td>
        <td class="py-3 pr-3"><code class="text-xs bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded font-mono">${r.field_code}</code></td>
        <td class="py-3 pr-3 text-slate-700">${r.field_name}</td>
        <td class="py-3 pr-3 ${alignClass}">${displayValue === null ? "—" : displayValue}</td>
        <td class="py-3 pl-3 text-slate-500">${r.unit || "—"}</td>
      `;
      previewTbody.appendChild(tr);
    });

    previewTableWrapper.classList.remove("hidden");
  }

  // Live Table Search Filter
  if (previewSearch) {
    previewSearch.addEventListener("input", function () {
      const query = this.value.toLowerCase().trim();
      if (!query) {
        renderPreviewTable(activePreviewData);
        return;
      }

      const filtered = activePreviewData.filter(r => {
        return (
          r.period_label.toLowerCase().includes(query) ||
          r.site_name.toLowerCase().includes(query) ||
          r.form_name.toLowerCase().includes(query) ||
          r.field_code.toLowerCase().includes(query) ||
          r.field_name.toLowerCase().includes(query) ||
          (r.unit && r.unit.toLowerCase().includes(query)) ||
          (r.value !== null && String(r.value).toLowerCase().includes(query))
        );
      });
      renderPreviewTable(filtered);
    });
  }

})();
