(function () {
  "use strict";

  const euro = new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" });
  const charts = new Map();

  function renderCharts(root) {
    if (typeof Chart === "undefined") return;
    root.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
      const source = document.getElementById(canvas.dataset.chart);
      if (!source) return;
      const config = JSON.parse(source.textContent);
      if (charts.has(canvas.id)) charts.get(canvas.id).destroy();
      charts.set(
        canvas.id,
        new Chart(canvas, {
          type: config.type,
          data: {
            labels: config.labels,
            datasets: [{ label: config.label, data: config.values, tension: 0.25 }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (ctx) => euro.format(ctx.parsed.y) } },
            },
            scales: { y: { beginAtZero: true, ticks: { callback: (v) => euro.format(v) } } },
          },
        })
      );
    });
  }

  // Voorkomt dubbel versturen van formulieren met data-once.
  document.addEventListener("submit", function (event) {
    const form = event.target;
    if (!form.hasAttribute("data-once")) return;
    if (form.dataset.submitted) {
      event.preventDefault();
      return;
    }
    form.dataset.submitted = "true";
    const button = form.querySelector("button[type=submit]");
    if (button) button.setAttribute("aria-busy", "true");
  });

  document.addEventListener("DOMContentLoaded", function () {
    renderCharts(document);
  });
  document.addEventListener("htmx:afterSettle", function (event) {
    renderCharts(event.target);
  });
})();
