const bar = document.getElementById("bar");
const articlesEl = document.getElementById("articles");
const listTitle = document.getElementById("listTitle");
const dateSelect = document.getElementById("dateSelect");
const themeBtn = document.getElementById("themeBtn");

let ALL = [];
let mapObj = null;

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
  const items = countryCode ? ALL.filter((a) => a.country_code === countryCode) : ALL;
  listTitle.textContent = countryCode ? `Country: ${countryCode}` : "All Countries";
  articlesEl.innerHTML = items
    .map(
      (a) => `
    <div class="article">
      <a href="${a.url}" target="_blank" rel="noopener noreferrer">${a.title}</a>
      <div class="meta">${a.outlet} | ${a.country} | ${fmtDate(a.date)} | ${a.source}</div>
    </div>
  `
    )
    .join("") || "<div>No articles found.</div>";
}

function countryCounts() {
  const counts = {};
  for (const article of ALL) {
    counts[article.country_code] = (counts[article.country_code] || 0) + 1;
  }
  return counts;
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
    onRegionClick: (_, code) => renderList(code),
  });
}

async function loadDate(dateValue) {
  setProgress(20);
  const res = await fetch(`data/${dateValue}.json`);
  const json = await res.json();
  setProgress(70);
  ALL = json.articles || [];
  renderMap();
  renderList();
  setProgress(100);
  setTimeout(() => setProgress(0), 500);
}

async function init() {
  setProgress(10);
  const idx = await fetch("data/index.json").then((r) => r.json());
  const dates = idx.dates || [];
  dateSelect.innerHTML = dates.map((d) => `<option value="${d}">${d}</option>`).join("");
  if (!dates.length) {
    articlesEl.innerHTML = "<div>No data yet. Run the workflow once.</div>";
    return;
  }
  await loadDate(dates[0]);
  dateSelect.onchange = () => loadDate(dateSelect.value);
}

themeBtn.onclick = () => document.body.classList.toggle("light");
init();
