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

  // Datumvelden: tekst in dd-mm-jjjj [uu:mm]; de kalenderknop gebruikt een verborgen
  // <input type="date|datetime-local"> en zet de keuze terug in Nederlandse notatie.
  const pad = (n) => String(n).padStart(2, "0");

  function nlToIso(text, withTime) {
    const m = text.trim().match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?:\s+(\d{1,2})[:.](\d{2}))?$/);
    if (!m) return "";
    const day = `${m[3]}-${pad(m[2])}-${pad(m[1])}`;
    return withTime ? `${day}T${pad(m[4] || "12")}:${m[5] || "00"}` : day;
  }

  function isoToNl(iso, withTime) {
    const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
    if (!m) return "";
    const day = `${m[3]}-${m[2]}-${m[1]}`;
    return withTime ? `${day} ${m[4] || "00"}:${m[5] || "00"}` : day;
  }

  function dateParts(element) {
    const field = element.closest(".date-field");
    const proxy = field.querySelector(".date-proxy");
    return { text: field.querySelector("[data-date-text]"), proxy, withTime: proxy.type === "datetime-local" };
  }

  document.addEventListener("click", function (event) {
    const button = event.target.closest("[data-date-picker]");
    if (!button) return;
    const { text, proxy, withTime } = dateParts(button);
    proxy.value = nlToIso(text.value, withTime);
    try {
      proxy.showPicker();
    } catch (error) {
      proxy.focus();
      proxy.click();
    }
  });

  // Capture-fase: het hulpveld zelf mag geen change-event naar het formulier sturen
  // (het rapportfilter vernieuwt bij change); dat doet alleen het zichtbare tekstveld.
  document.addEventListener(
    "change",
    function (event) {
      if (!event.target.matches(".date-proxy")) return;
      event.stopPropagation();
      const { text, proxy, withTime } = dateParts(event.target);
      if (!proxy.value) return;
      text.value = isoToNl(proxy.value, withTime);
      text.dispatchEvent(new Event("change", { bubbles: true }));
      text.focus();
    },
    true
  );

  document.addEventListener("DOMContentLoaded", function () {
    renderCharts(document);
  });
  document.addEventListener("htmx:afterSettle", function (event) {
    renderCharts(event.target);
  });
})();
