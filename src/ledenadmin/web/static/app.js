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

  // PDF-export: de browser drukt het rapport af via de printstijlen ("Opslaan als PDF").
  document.addEventListener("click", function (event) {
    const link = event.target.closest("[data-print-report]");
    if (!link) return;
    event.preventDefault();
    const article = link.closest("article");
    const form = document.getElementById("report-filter");
    const filters = [];
    if (form) {
      form.querySelectorAll("select").forEach(function (select) {
        if (!select.value) return;
        const label = form.querySelector(`label[for="${select.id}"]`);
        const name = label ? label.childNodes[0].textContent.trim() : select.name;
        filters.push(`${name}: ${select.options[select.selectedIndex].text}`);
      });
    }
    const period = article.querySelector(".page-head span").textContent.trim();
    const target = article.querySelector("[data-print-filters]");
    if (target) target.textContent = [period, ...filters].join(" · ");
    const closed = Array.from(article.querySelectorAll("details:not([open])"));
    closed.forEach((d) => (d.open = true));
    const title = document.title;
    const today = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    document.title = `Rapportage ${pad(today.getDate())}-${pad(today.getMonth() + 1)}-${today.getFullYear()}`;
    window.addEventListener(
      "afterprint",
      function () {
        document.title = title;
        closed.forEach((d) => (d.open = false));
      },
      { once: true }
    );
    window.print();
  });

  // Grafieken opnieuw tekenen op papierformaat, en daarna weer op schermformaat.
  window.addEventListener("beforeprint", () => charts.forEach((chart) => chart.resize()));
  window.addEventListener("afterprint", () => charts.forEach((chart) => chart.resize()));

  // Selectie in tabellen (zoals Gmail): rij-vinkjes, "alles"-vinkje en een actiebalk.
  function updateBulk(form) {
    const rows = Array.from(form.querySelectorAll("tr:not([hidden]) [data-select-row]"));
    const checked = Array.from(form.querySelectorAll("[data-select-row]:checked"));
    const all = form.querySelector("[data-select-all]");
    if (all) {
      all.checked = checked.length > 0 && checked.length === rows.length;
      all.indeterminate = checked.length > 0 && checked.length < rows.length;
    }
    rows.forEach((box) => box.closest("tr").classList.toggle("is-selected", box.checked));
    const bar = form.querySelector(".bulk-bar");
    bar.hidden = checked.length === 0;
    form.querySelector("[data-bulk-count]").textContent =
      `${checked.length} ${checked.length === 1 ? form.dataset.one : form.dataset.many} geselecteerd`;
    return checked.length;
  }

  document.addEventListener("change", function (event) {
    const form = event.target.closest("form[data-bulk-select]");
    if (!form) return;
    if (event.target.matches("[data-select-all]")) {
      form
        .querySelectorAll("tr:not([hidden]) [data-select-row]")
        .forEach((box) => (box.checked = event.target.checked));
    }
    updateBulk(form);
  });

  document.addEventListener(
    "submit",
    function (event) {
      const form = event.target;
      if (!form.matches("form[data-bulk-select]")) return;
      const count = updateBulk(form);
      const what = count === 1 ? form.dataset.this : `deze ${count} ${form.dataset.many}`;
      const extra = form.dataset.confirmExtra ? `\n\n${form.dataset.confirmExtra}` : "";
      if (!count || !window.confirm(`Weet je zeker dat je ${what} definitief wilt verwijderen?${extra}`)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    },
    true
  );

  // Terug-knop (bfcache): vinkjes kunnen bewaard zijn, dus de balk opnieuw bijwerken.
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("form[data-bulk-select]").forEach(updateBulk);
  });

  // Logboek: klikken op links, knoppen en vinkjes vastleggen (de server bepaalt de gebruiker).
  function csrfToken() {
    try {
      return JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRF-Token"] || "";
    } catch (e) {
      return "";
    }
  }

  document.addEventListener(
    "click",
    function (event) {
      const el = event.target.closest("a, button, summary, [role=button], input[type=checkbox]");
      if (!el || !navigator.sendBeacon) return;
      const label = (
        el.getAttribute("aria-label") ||
        el.textContent ||
        el.value ||
        el.name ||
        ""
      )
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 150);
      const data = new FormData();
      data.append("csrf_token", csrfToken());
      data.append("element", el.tagName.toLowerCase() + (el.id ? `#${el.id}` : ""));
      data.append("label", label);
      if (el.getAttribute("href")) data.append("href", el.getAttribute("href"));
      data.append("pagina", location.pathname + location.search);
      navigator.sendBeacon((document.body.dataset.org || "") + "/logboek/klik", new URLSearchParams(data));
    },
    true
  );

  // JavaScript-fouten naar het logboek (maximaal 5 per pagina), voor onderzoek achteraf.
  let reportedErrors = 0;
  const reportError = (message, source) => {
    const org = document.body.dataset.org;
    if (!org || reportedErrors >= 5) return;
    reportedErrors += 1;
    const data = new URLSearchParams();
    data.append("csrf_token", csrfToken());
    data.append("melding", String(message || "").slice(0, 500));
    data.append("bron", String(source || "").slice(0, 300));
    data.append("pagina", location.pathname + location.search);
    navigator.sendBeacon(org + "/logboek/fout", data);
  };
  window.addEventListener("error", (e) =>
    reportError(e.message, `${e.filename || ""}:${e.lineno || ""}:${e.colno || ""}`)
  );
  window.addEventListener("unhandledrejection", (e) =>
    reportError(e.reason && (e.reason.stack || e.reason.message || e.reason), "promise")
  );

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

  // Ledenkeuzelijst: het zoekveld filtert de <option>s (ook op e-mail via data-zoek),
  // ongevoelig voor hoofdletters en accenten ("ayse" vindt "Ayşe"). Opties worden echt
  // verwijderd en teruggezet, omdat verborgen opties niet in elke browser verdwijnen.
  const memberOptions = new WeakMap();
  const autoSelectTimers = new WeakMap();

  function normalize(text) {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/ı/g, "i").toLowerCase();
  }

  function memberParts(search) {
    const picker = search.closest(".member-picker");
    const select = picker.querySelector("select");
    if (!memberOptions.has(select)) {
      memberOptions.set(
        select,
        [...select.options].map((option) => ({
          option,
          text: normalize(`${option.text} ${option.dataset.zoek || ""}`),
        }))
      );
    }
    const count = picker.querySelector(".member-count");
    return { select, count, all: memberOptions.get(select) };
  }

  function chooseMember(select, option) {
    if (select.value === option.value) return;
    select.value = option.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function filterMembers(search) {
    const { select, count, all } = memberParts(search);
    const terms = normalize(search.value).split(/\s+/).filter(Boolean);
    const members = all.filter((entry) => entry.option.value);
    const matches = members.filter((entry) => terms.every((term) => entry.text.includes(term)));
    const matched = new Set(matches);
    // De lege keuze ("Alle leden") en het huidige lid blijven altijd in de lijst staan.
    // Werk met de waarde i.p.v. option.selected: losgekoppelde opties houden die vlag soms vast.
    const current = select.value;
    const keep = all.filter((entry) => !entry.option.value || entry.option.value === current || matched.has(entry));
    select.replaceChildren(...keep.map((entry) => entry.option));
    select.value = current;

    clearTimeout(autoSelectTimers.get(search));
    if (!terms.length) {
      count.textContent = "";
      // Zoekveld leeggemaakt: terug naar de eerste keuze ("Alle leden" / "Kies een lid…").
      chooseMember(select, select.options[0]);
    } else if (!matches.length) {
      count.textContent = "Geen leden gevonden";
    } else if (matches.length === 1) {
      count.textContent = "1 lid gevonden en gekozen";
      // Even wachten: bij doortypen niet voor elke letter een nieuw rapport opvragen.
      autoSelectTimers.set(search, setTimeout(() => chooseMember(select, matches[0].option), 400));
    } else {
      count.textContent = `${matches.length} van ${members.length} leden – kies in de lijst of druk op Enter voor de eerste`;
    }
    return matches;
  }

  document.addEventListener("input", function (event) {
    if (event.target.matches("[data-member-search]")) filterMembers(event.target);
  });

  document.addEventListener("keydown", function (event) {
    const search = event.target;
    if (!search.matches || !search.matches("[data-member-search]")) return;
    if (event.key === "Enter") {
      event.preventDefault(); // niet het hele formulier versturen
      const matches = filterMembers(search);
      if (matches.length) chooseMember(memberParts(search).select, matches[0].option);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      memberParts(search).select.focus();
    }
  });

  // Het zoekveld heeft geen name; zijn change-event mag het rapportfilter niet vernieuwen.
  document.addEventListener(
    "change",
    function (event) {
      if (event.target.matches("[data-member-search]")) event.stopPropagation();
    },
    true
  );

  // Voor de terugknop bewaart HTMX de pagina-HTML: tijdelijk alle leden terugzetten en
  // na de momentopname het filter van de gebruiker herstellen.
  document.addEventListener("htmx:beforeHistorySave", function () {
    document.querySelectorAll("[data-member-search]").forEach(function (search) {
      if (!memberOptions.has(search.closest(".member-picker").querySelector("select"))) return;
      const { select, count, all } = memberParts(search);
      const current = select.value;
      const text = search.value;
      const message = count.textContent;
      select.replaceChildren(...all.map((entry) => entry.option));
      select.value = current;
      count.textContent = "";
      setTimeout(function () {
        // Bij de terugknop is de pagina intussen vervangen; dan niets herstellen.
        if (!text || !search.isConnected) return;
        search.value = text;
        filterMembers(search);
        count.textContent = message;
      });
    });
  });

  // Na terug/vooruit: zet de filtervelden gelijk aan de URL. De HTMX-momentopname bevat
  // de velden zoals ze waren op het moment van weggaan, niet per se die van deze URL.
  document.addEventListener("htmx:historyRestore", function () {
    const params = new URLSearchParams(location.search);
    if (!params.size) return;
    document.querySelectorAll("form[hx-push-url]").forEach(function (form) {
      for (const field of form.elements) {
        if (field.name && params.has(field.name)) field.value = params.get(field.name);
      }
    });
  });

  // Bevestiging voor gewone formulieren met data-confirm.
  document.addEventListener("submit", function (event) {
    const message = event.target.dataset && event.target.dataset.confirm;
    if (message && !window.confirm(message)) event.preventDefault();
  });

  // Lange tabellen: toon 50 rijen en voeg er steeds 50 toe bij scrollen of "Meer weergeven".
  const PAGE_SIZE = 50;
  const pagerObserver =
    "IntersectionObserver" in window
      ? new IntersectionObserver((entries) => {
          entries.forEach((entry) => entry.isIntersecting && entry.target.click());
        })
      : null;

  function showMore(tbody, button) {
    const hidden = tbody.querySelectorAll("tr[hidden]");
    Array.from(hidden)
      .slice(0, PAGE_SIZE)
      .forEach((row) => (row.hidden = false));
    const rest = hidden.length - Math.min(PAGE_SIZE, hidden.length);
    const total = tbody.rows.length;
    const form = tbody.closest("form[data-bulk-select]");
    if (form) updateBulk(form);
    button.textContent = `Meer weergeven (${total - rest} van ${total})`;
    if (rest === 0) {
      if (pagerObserver) pagerObserver.unobserve(button);
      button.remove();
    }
  }

  function initPaging(root) {
    root.querySelectorAll("tbody[data-paginate]:not([data-paged])").forEach((tbody) => {
      tbody.dataset.paged = "1";
      if (tbody.rows.length <= PAGE_SIZE) return;
      Array.from(tbody.rows)
        .slice(PAGE_SIZE)
        .forEach((row) => (row.hidden = true));
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary outline show-more";
      button.addEventListener("click", () => showMore(tbody, button));
      tbody.closest("table").after(button);
      button.textContent = `Meer weergeven (${PAGE_SIZE} van ${tbody.rows.length})`;
      if (pagerObserver) pagerObserver.observe(button);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-member-search]").forEach((search) => (search.hidden = false));
    renderCharts(document);
    initPaging(document);
  });
  document.addEventListener("htmx:afterSettle", function (event) {
    renderCharts(event.target);
    initPaging(document);
    document.querySelectorAll("form[data-bulk-select]").forEach(updateBulk);
  });
})();
