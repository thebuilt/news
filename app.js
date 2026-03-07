const bar = document.getElementById("bar");
const articlesEl = document.getElementById("articles");
const listTitle = document.getElementById("listTitle");
const dateSelect = document.getElementById("dateSelect");
const countrySelect = document.getElementById("countrySelect");
const themeBtn = document.getElementById("themeBtn");
const clearFilterBtn = document.getElementById("clearFilterBtn");

let ALL = [];
let FILTERED = [];
let mapObj = null;
let currentCountryCode = null;
let pageSize = 120;
let page = 1;

const setProgress = (v) => {
  bar.style.width = `${v}%`;
};

function fmtDate(s) {
  try {
    return new Date(s).toLocaleString();
  } catch {
    return s;
  }
}

function renderList(countryCode = null) {
  currentCountryCode = countryCode;
  FILTERED = countryCode ? ALL.filter((a) => a.country_code === countryCode) : ALL;
  page = 1;
  syncCountrySelect();
  drawPage();
}

function drawPage() {
  const items = FILTERED.slice(0, pageSize * page);
  listTitle.textContent = currentCountryCode ? `Country: ${currentCountryCode}` : "All Countries";
  if (clearFilterBtn) {
    clearFilterBtn.disabled = !currentCountryCode;
  }
  const hasMore = FILTERED.length > items.length;
  const content =
    items
      .map(
      (a) => `
    <div class="article">
      <a href="${a.url}" target="_blank" rel="noopener noreferrer">${a.title}</a>
      <div class="meta">${a.outlet} | ${a.country} | ${fmtDate(a.date)} | ${a.source}</div>
    </div>
  `
      )
      .join("") || "<div>No articles found.</div>";
  const moreBtn = hasMore
    ? `<button id="loadMoreBtn" class="more-btn">Load more (${FILTERED.length - items.length} remaining)</button>`
    : "";
  articlesEl.innerHTML = `${content}${moreBtn}`;
  const loadMoreBtn = document.getElementById("loadMoreBtn");
  if (loadMoreBtn) {
    loadMoreBtn.onclick = () => {
      page += 1;
      drawPage();
    };
  }
}

function countryCounts() {
  const counts = {};
  for (const article of ALL) {
    counts[article.country_code] = (counts[article.country_code] || 0) + 1;
  }
  return counts;
}

function countryLabelMap() {
  const map = {};
  for (const article of ALL) {
    if (!map[article.country_code]) {
      map[article.country_code] = article.country || article.country_code || "Unknown";
    }
  }
  return map;
}

function syncCountrySelect() {
  if (!countrySelect) return;
  countrySelect.value = currentCountryCode || "ALL";
}

function renderCountrySelect() {
  if (!countrySelect) return;
  const labels = countryLabelMap();
  const counts = countryCounts();
  const options = Object.keys(labels)
    .sort((a, b) => (labels[a] || "").localeCompare(labels[b] || ""))
    .map((code) => {
      const label = labels[code] || code;
      const count = counts[code] || 0;
      return `<option value="${code}">${label} (${count})</option>`;
    })
    .join("");
  countrySelect.innerHTML = `<option value="ALL">All Countries (${ALL.length})</option>${options}`;
  syncCountrySelect();
}

function renderMap() {
  if (mapObj) {
    mapObj.destroy();
  }
  mapObj = new jsVectorMap({
    selector: "#worldMap",
    map: "world",
    regionStyle: {
      initial: { fill: "#3b4d73" },
    },
    series: {
      regions: [
        {
          values: countryCounts(),
          scale: ["#334155", "#38bdf8"],
          normalizeFunction: "polynomial",
        },
      ],
    },
    onRegionClick: (_, code) => {
      if (currentCountryCode === code) {
        renderList(null);
        return;
      }
      renderList(code);
    },
    onRegionTooltipShow: (event, tooltip, code) => {
      const counts = countryCounts();
      const count = counts[code] || 0;
      tooltip.text(`${tooltip.text()} (${count})`);
    },
  });
}

async function loadDate(dateValue) {
  setProgress(20);
  const res = await fetch(`data/${dateValue}.json`);
  const json = await res.json();
  setProgress(70);
  ALL = json.articles || [];
  renderCountrySelect();
  setTimeout(() => renderMap(), 0);
  renderList();
  setProgress(100);
  setTimeout(() => setProgress(0), 500);
}

async function init() {
  setProgress(10);
  let latestDate = "";
  try {
    const latest = await fetch("data/latest.json").then((r) => r.json());
    ALL = latest.articles || [];
    latestDate = latest.date || "";
    renderCountrySelect();
    renderList();
    setTimeout(() => renderMap(), 0);
    setProgress(60);
  } catch {
    articlesEl.innerHTML = "<div>No data yet. Run the workflow once.</div>";
    setProgress(0);
    return;
  }

  try {
    const idx = await fetch("data/index.json").then((r) => r.json());
    const dates = idx.dates || [];
    dateSelect.innerHTML = dates.map((d) => `<option value="${d}">${d}</option>`).join("");
    if (latestDate && dates.includes(latestDate)) {
      dateSelect.value = latestDate;
    }
    if (dates.length) {
      dateSelect.onchange = () => loadDate(dateSelect.value);
    }
  } catch {
    dateSelect.innerHTML = "";
  }
  setProgress(100);
  setTimeout(() => setProgress(0), 500);
}

themeBtn.onclick = () => document.body.classList.toggle("light");
if (clearFilterBtn) {
  clearFilterBtn.onclick = () => renderList(null);
}
if (countrySelect) {
  countrySelect.onchange = () => {
    if (countrySelect.value === "ALL") {
      renderList(null);
      return;
    }
    renderList(countrySelect.value);
  };
}
init();
