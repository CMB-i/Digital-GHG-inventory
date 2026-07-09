(function () {
  "use strict";

  const chartInstances = new Map();

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function spanClass(span) {
    if (span === "full") return "col-span-12";
    if (span === "half") return "col-span-12 md:col-span-6";
    return "col-span-12 md:col-span-6 xl:col-span-4";
  }

  function formatValue(value, unit) {
    if (value === null || value === undefined || value === "") return "—";
    const numeric = Number(value);
    const display = Number.isFinite(numeric)
      ? numeric.toLocaleString(undefined, { maximumFractionDigits: 3 })
      : String(value);
    return unit ? `${display} ${unit}` : display;
  }

  function statusBadge(status) {
    if (status === "calculated") {
      return '<span class="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-700">Calculated</span>';
    }
    if (status === "error") {
      return '<span class="rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-rose-700">Error</span>';
    }
    if (status === "not_configured") {
      return '<span class="rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-rose-700">Not configured</span>';
    }
    return '<span class="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-700">Needs input</span>';
  }

  function destroyCharts() {
    chartInstances.forEach((chart) => {
      try {
        chart.destroy();
      } catch (_err) {
        // ignore teardown errors
      }
    });
    chartInstances.clear();
  }

  function chartPalette() {
    return ["#1a3a6b", "#2563eb", "#0d9488", "#f59e0b", "#7c3aed", "#dc2626"];
  }

  function renderKpiCard(widget) {
    const showUnit = widget.show_unit !== false;
    const showStatus = widget.show_formula_status !== false;
    const unit = showUnit ? (widget.unit || "") : "";
    return `
      <div class="${spanClass(widget.span)}">
        <div class="h-full rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div class="flex items-start justify-between gap-2">
            <div class="text-xs font-bold uppercase tracking-wider text-slate-500">${escapeHtml(widget.label)}</div>
            ${showStatus ? statusBadge(widget.status) : ""}
          </div>
          <div class="mt-3 tabular-nums text-2xl font-bold text-[#1a3a6b]">${escapeHtml(formatValue(widget.value, unit))}</div>
          ${widget.message ? `<div class="mt-2 text-xs text-amber-700">${escapeHtml(widget.message)}</div>` : ""}
        </div>
      </div>
    `;
  }

  function chartCanvasId(widget) {
    return `wb-viz-chart-${String(widget.field_code || "widget").replace(/[^a-zA-Z0-9_-]/g, "_")}`;
  }

  function renderChartShell(widget, chartType) {
    return `
      <div class="${spanClass(widget.span)}">
        <div class="h-full rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div class="text-xs font-bold uppercase tracking-wider text-slate-500">${escapeHtml(widget.label)}</div>
          <div class="mt-3 h-56">
            <canvas id="${escapeHtml(chartCanvasId(widget))}" data-chart-type="${escapeHtml(chartType)}" aria-label="${escapeHtml(widget.label)} chart"></canvas>
          </div>
        </div>
      </div>
    `;
  }

  function mountCharts(widgets) {
    if (typeof Chart === "undefined") return;
    (widgets || []).forEach((widget) => {
      const widgetType = (widget.widget || "").toLowerCase();
      if (!["bar", "line", "donut"].includes(widgetType)) return;
      const canvas = document.getElementById(chartCanvasId(widget));
      if (!canvas) return;

      const colors = chartPalette();
      let config = null;
      if (widgetType === "donut") {
        const segments = widget.segments || [];
        config = {
          type: "doughnut",
          data: {
            labels: segments.map((segment) => segment.label),
            datasets: [{
              data: segments.map((segment) => Number(segment.value) || 0),
              backgroundColor: colors,
              borderWidth: 1,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
          },
        };
      } else {
        const series = widget.series || [];
        config = {
          type: widgetType === "bar" ? "bar" : "line",
          data: {
            labels: widget.month_labels || [],
            datasets: series.map((item, index) => ({
              label: item.label || item.field_code,
              data: (item.values || []).map((value) => (value === null || value === undefined ? null : Number(value))),
              borderColor: colors[index % colors.length],
              backgroundColor: widgetType === "bar" ? colors[index % colors.length] : "transparent",
              tension: 0.25,
              fill: false,
            })),
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: {
              y: { beginAtZero: true },
            },
          },
        };
      }

      const chart = new Chart(canvas, config);
      chartInstances.set(canvas.id, chart);
    });
  }

  function renderSummaryDashboard(visualization, containerEl) {
    if (!containerEl) return;
    destroyCharts();
    const panels = visualization && visualization.panels ? visualization.panels : [];
    if (!panels.length) {
      containerEl.innerHTML = `
        <div class="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
          No summary dashboard widgets configured for this sheet.
        </div>
      `;
      containerEl.classList.remove("hidden");
      return;
    }

    const html = `
      <div class="space-y-6">
        <div class="rounded-lg border border-indigo-100 bg-indigo-50/60 px-4 py-3 text-xs text-indigo-900">
          Read-only FY summary — values are computed from other sheets. Charts are not included in Excel export.
        </div>
        ${panels.map((panel) => `
          <section class="rounded-xl border border-slate-200 bg-slate-50/40 p-4">
            <h3 class="text-sm font-bold text-slate-900">${escapeHtml(panel.name || "Summary")}</h3>
            <div class="mt-4 grid grid-cols-12 gap-4">
              ${(panel.widgets || []).map((widget) => {
                const type = (widget.widget || "kpi").toLowerCase();
                if (type === "bar" || type === "line") return renderChartShell(widget, type);
                if (type === "donut") return renderChartShell(widget, "donut");
                return renderKpiCard(widget);
              }).join("")}
            </div>
          </section>
        `).join("")}
      </div>
    `;
    containerEl.innerHTML = html;
    containerEl.classList.remove("hidden");
    mountCharts(visualization.widgets || []);
  }

  window.WorkbookViz = {
    destroyCharts,
    renderSummaryDashboard,
  };
})();
