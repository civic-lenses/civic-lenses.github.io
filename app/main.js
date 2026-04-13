// AI-assisted (Claude Code, claude.ai) — https://claude.ai

import { connectGitHub, verifyToken } from "https://neevs.io/auth/lib.js";

let appData = null;
let selectedTopics = new Set(["healthcare", "education", "defense"]);
let activeTab = "scrutiny";
let currentUser = null;
let viewMode = "hybrid"; // "hybrid" = top 3 cards + table, "cards" = all cards, "table" = all table

const AUTH_KEY = "civic-lenses-auth";

const TOPIC_LABELS = {
  healthcare: "Healthcare",
  education: "Education",
  defense: "Defense",
  infrastructure: "Infrastructure",
  foreign_aid: "Foreign Aid",
  general_spending: "General Spending",
  government_efficiency: "Gov. Efficiency",
  research: "Research",
  finance: "Finance",
  agriculture: "Agriculture",
  energy: "Energy",
  doge_scrutiny: "DOGE Scrutiny",
};

function formatMoney(n) {
  if (n >= 1e9) return "$" + (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(0) + "K";
  return "$" + n.toFixed(0);
}

function scrutinyLevel(score) {
  if (score >= 0.7) return { cls: "scrutiny-high", label: "High scrutiny" };
  if (score >= 0.3) return { cls: "scrutiny-med", label: "Watch" };
  return { cls: "scrutiny-low", label: "Low" };
}

function flagClass(flag) {
  if (flag === "high_scrutiny" || flag === "doge_flag") return "flag-doge";
  if (flag === "high_value") return "flag-sole";
  if (flag === "vague_description") return "flag-vague";
  if (flag === "trending") return "flag-renewal";
  return "flag-doge";
}

function flagLabel(flag) {
  const labels = {
    high_scrutiny: "High scrutiny",
    doge_flag: "DOGE flagged",
    high_value: "High value",
    vague_description: "Vague description",
    trending: "Trending",
  };
  return labels[flag] || flag.replace(/_/g, " ");
}

function esc(str) {
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d)) return "";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function renderCard(contract, idx) {
  const s = scrutinyLevel(contract.scrutiny);
  const flagsHTML = (contract.flags || [])
    .map(f => {
      const tip = f === "doge_flag" ? ' data-tooltip="This contract was flagged and terminated by the Department of Government Efficiency (DOGE)."' : '';
      return `<span class="flag ${flagClass(f)}"${tip}>${flagLabel(f)}</span>`;
    })
    .join("");
  const dateStr = formatDate(contract.deleted_date);
  const cardId = `card-detail-${idx}`;

  const isRecommended = !!contract.final_score;
  // Sentence-case the description (avoid ALL CAPS shouting)
  const title = contract.description.length > 3 && contract.description === contract.description.toUpperCase()
    ? contract.description.charAt(0) + contract.description.slice(1).toLowerCase()
    : contract.description;
  // Shorten vendor name
  const shortVendor = (contract.vendor || "").replace(/,?\s*(LLC|INC|CORP|CO\.|CORPORATION|LTD|L\.?L\.?C\.?|INC\.)\.?$/i, "").trim();

  return `
    <div class="contract-card${isRecommended ? " card-recommended" : ""}">
      <div class="card-header">
        <span class="agency-tag">${contract.agency}</span>
        <span class="scrutiny-badge ${s.cls}" title="${isRecommended ? `Relevance: ${(contract.relevance * 100).toFixed(0)}% · Score: ${contract.final_score.toFixed(3)}` : s.label}">
          <span class="dot"></span>
          ${s.label}
        </span>
      </div>
      <div class="card-title">${esc(title)}</div>
      <div class="card-value-row">
        <span class="card-value">${formatMoney(contract.value)}</span>
        ${contract.savings > 0 ? `<span class="card-savings">${formatMoney(contract.savings)} cut</span>` : ""}
      </div>
      <div class="card-meta">
        <span class="meta-item">${esc(shortVendor)}</span>
        ${dateStr ? `<span class="meta-sep"></span><span class="meta-item">${dateStr}</span>` : ""}
        ${contract.state ? `<span class="meta-sep"></span><span class="meta-item meta-state">${contract.state}</span>` : ""}
      </div>
      ${flagsHTML ? `<div class="card-flags">${flagsHTML}</div>` : ""}
      ${contract.reason ? `<div class="card-reason">${contract.reason}</div>` : ""}
      <div class="card-actions">
        <button class="action-btn primary" onclick="document.getElementById('${cardId}').classList.toggle('open')">Details</button>
      </div>
      <div class="card-detail" id="${cardId}">
        <div class="card-detail-grid">
          <div class="detail-row"><span class="detail-label">Contract ID</span><span class="detail-value">${contract.contract_id}</span></div>
          <div class="detail-row"><span class="detail-label">Value</span><span class="detail-value">${formatMoney(contract.value)}</span></div>
          <div class="detail-row"><span class="detail-label">Savings</span><span class="detail-value">${formatMoney(contract.savings)}</span></div>
          <div class="detail-row"><span class="detail-label">Scrutiny</span><span class="detail-value">${(contract.scrutiny * 100).toFixed(0)}%</span></div>
          <div class="detail-row" data-tooltip="A score from 0-1 measuring how clear and specific the contract description is. Lower scores indicate vague descriptions."><span class="detail-label">Transparency</span><span class="detail-value">${(contract.transparency * 100).toFixed(0)}%</span></div>
          ${dateStr ? `<div class="detail-row"><span class="detail-label">Cut date</span><span class="detail-value">${dateStr}</span></div>` : ""}
        </div>
      </div>
    </div>`;
}

function truncate(str, len) {
  if (!str || str.length <= len) return str || "";
  return str.substring(0, len).trimEnd() + "\u2026";
}

let tableSortKey = null;
let tableSortAsc = false;
let searchQuery = "";
let showLimit = 20;

function sortContracts(contracts, key) {
  const sorted = [...contracts];
  const dir = tableSortAsc ? 1 : -1;
  sorted.sort((a, b) => {
    let va = a[key], vb = b[key];
    if (key === "deleted_date") { va = va || ""; vb = vb || ""; return va.localeCompare(vb) * dir; }
    if (key === "agency" || key === "state" || key === "description") { return (va || "").localeCompare(vb || "") * dir; }
    return ((va || 0) - (vb || 0)) * dir;
  });
  return sorted;
}

function renderTableRow(contract, idx) {
  const s = scrutinyLevel(contract.scrutiny);
  const rowId = `table-detail-${idx}`;
  const flagsHTML = (contract.flags || []).map(f => `<span class="flag ${flagClass(f)}">${flagLabel(f)}</span>`).join(" ");
  return `
    <tr class="compact-row" onclick="document.getElementById('${rowId}').classList.toggle('open')">
      <td class="col-rank">${idx + 1}</td>
      <td class="col-agency" title="${esc(contract.agency)}">${esc(truncate(contract.agency, 24))}</td>
      <td class="col-desc">${esc(truncate(contract.description, 60))}</td>
      <td class="col-value">${formatMoney(contract.value)}</td>
      <td class="col-state">${contract.state || "\u2014"}</td>
      <td class="col-scrutiny"><span class="dot ${s.cls}" title="${s.label} (${(contract.scrutiny * 100).toFixed(0)}%)"></span></td>
      <td class="col-date">${formatDate(contract.deleted_date) || "\u2014"}</td>
    </tr>
    <tr class="compact-detail-row" id="${rowId}">
      <td colspan="7">
        <div class="compact-detail-inner">
          <div class="detail-header">
            <span class="detail-title">${esc(contract.description)}</span>
            ${flagsHTML ? `<div class="detail-flags">${flagsHTML}</div>` : ""}
          </div>
          <div class="detail-grid-3col">
            <div class="detail-cell"><span class="detail-label">Contract ID</span><span class="detail-value">${contract.contract_id}</span></div>
            <div class="detail-cell"><span class="detail-label">Agency</span><span class="detail-value">${esc(contract.agency)}</span></div>
            <div class="detail-cell"><span class="detail-label">Vendor</span><span class="detail-value">${esc(contract.vendor)}</span></div>
            <div class="detail-cell"><span class="detail-label">Value</span><span class="detail-value">${formatMoney(contract.value)}</span></div>
            <div class="detail-cell"><span class="detail-label">Savings</span><span class="detail-value">${formatMoney(contract.savings)}</span></div>
            <div class="detail-cell"><span class="detail-label">Scrutiny</span><span class="detail-value">${(contract.scrutiny * 100).toFixed(0)}%</span></div>
            <div class="detail-cell"><span class="detail-label">Transparency</span><span class="detail-value">${(contract.transparency * 100).toFixed(0)}%</span></div>
            ${contract.state ? `<div class="detail-cell"><span class="detail-label">State</span><span class="detail-value">${contract.state}</span></div>` : ""}
            ${contract.deleted_date ? `<div class="detail-cell"><span class="detail-label">Cut Date</span><span class="detail-value">${formatDate(contract.deleted_date)}</span></div>` : ""}
          </div>
          ${contract.reason ? `<div class="detail-reason">${esc(contract.reason)}</div>` : ""}
        </div>
      </td>
    </tr>`;
}

const SORT_COLUMNS = [
  { key: null, label: "#", cls: "col-rank" },
  { key: "agency", label: "Agency", cls: "col-agency" },
  { key: "description", label: "Description", cls: "col-desc" },
  { key: "value", label: "Value", cls: "col-value" },
  { key: "state", label: "State", cls: "col-state" },
  { key: "scrutiny", label: "Risk", cls: "col-scrutiny" },
  { key: "deleted_date", label: "Date", cls: "col-date" },
];

function renderTable(contracts, startIdx) {
  if (contracts.length === 0) return "";
  const sorted = tableSortKey ? sortContracts(contracts, tableSortKey) : contracts;
  const arrow = tableSortAsc ? " \u25B2" : " \u25BC";
  return `
    <div class="compact-table-wrap">
      <table class="compact-table">
        <thead>
          <tr>
            ${SORT_COLUMNS.map(col => {
              const active = tableSortKey === col.key;
              const sortable = col.key ? " sortable" : "";
              return `<th class="${col.cls}${sortable}" data-sort="${col.key || ""}">${col.label}${active ? arrow : ""}</th>`;
            }).join("")}
          </tr>
        </thead>
        <tbody>
          ${sorted.map((c, i) => renderTableRow(c, startIdx + i)).join("")}
        </tbody>
      </table>
    </div>`;
}

function renderViewToggle() {
  const modes = [
    { key: "hybrid", label: "Hybrid" },
    { key: "cards", label: "Cards" },
    { key: "table", label: "Table" },
  ];
  return `
    <div class="view-toggle">
      ${modes.map(m => `<button class="view-toggle-btn${viewMode === m.key ? " active" : ""}" data-mode="${m.key}">${m.label}</button>`).join("")}
    </div>`;
}

function getFilteredContracts() {
  if (!appData) return [];

  // Primary: use model-ranked recommendations (TF-IDF + citizen impact)
  // These have relevance_score, final_score, flags, reason from the classical model
  let recommended = [];
  const seen = new Set();
  for (const topic of selectedTopics) {
    const recs = appData.recommendations[topic] || [];
    for (const r of recs) {
      if (!seen.has(r.contract_id)) {
        seen.add(r.contract_id);
        recommended.push(r);
      }
    }
  }

  // Secondary: fill remaining from the full contracts list (for browse/search)
  // These don't have model scores but allow the full dataset to be searchable
  const allContracts = appData.contracts || [];
  for (const c of allContracts) {
    if (selectedTopics.has(c.topic) && !seen.has(c.contract_id)) {
      seen.add(c.contract_id);
      recommended.push(c);
    }
  }

  return recommended;
}

function filterByTab(contracts) {
  if (activeTab === "scrutiny") {
    return contracts
      .filter(c => c.scrutiny >= 0.3)
      .sort((a, b) => {
        // Model-ranked items first (have final_score), then by scrutiny
        const aScore = a.final_score || 0;
        const bScore = b.final_score || 0;
        if (aScore && bScore) return bScore - aScore;
        if (aScore) return -1;
        if (bScore) return 1;
        return b.scrutiny - a.scrutiny;
      });
  }
  if (activeTab === "high-value") {
    return contracts
      .filter(c => c.value >= 1e6)
      .sort((a, b) => b.value - a.value);
  }
  if (activeTab === "just-cut") {
    return contracts
      .filter(c => c.savings > 0)
      .sort((a, b) => b.savings - a.savings);
  }
  return contracts;
}

// ── Charts ────────────────────────────────────────────────────

const CHART_COLORS = [
  '#00539B', '#E89923', '#2D6A4F', '#9B2226', '#5A67D8',
  '#0077B6', '#E76F51', '#386641', '#AE2012', '#7C3AED',
  '#023E8A', '#F4A261', '#52B788', '#CA6702', '#4361EE',
];

let charts = {};

let _resizeHandler = null;

function initCharts() {
  if (!appData) return;
  const stats = appData.stats;
  const isMobile = window.innerWidth < 768;

  // Dispose old instances
  Object.values(charts).forEach(c => { try { c.dispose(); } catch {} });

  const userState = resolveUserState();
  const tooltipBase = { confine: true, textStyle: { fontSize: 12 } };

  // -- States bar chart (show fewer on mobile) --
  const stateCount = isMobile ? 10 : 15;
  const stateEntries = Object.entries(stats.states)
    .sort((a, b) => b[1].value - a[1].value)
    .slice(0, stateCount);

  charts.states = echarts.init(document.getElementById("chart-states"));
  charts.states.setOption({
    tooltip: {
      ...tooltipBase, trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (p) => {
        const d = p[0]; const s = stats.states[d.name];
        return `<b>${d.name}</b><br/>Value: ${formatMoney(s.value)}<br/>Savings: ${formatMoney(s.savings)}<br/>Contracts: ${s.count.toLocaleString()}`;
      }
    },
    grid: { left: 36, right: 12, top: 8, bottom: 24, containLabel: false },
    xAxis: { type: "value", axisLabel: { formatter: v => formatMoney(v), fontSize: isMobile ? 9 : 10 }, splitLine: { lineStyle: { color: "#f0f0f0" } } },
    yAxis: { type: "category", data: stateEntries.map(e => e[0]).reverse(), axisLabel: { fontSize: isMobile ? 10 : 11 } },
    series: [{
      type: "bar", barWidth: isMobile ? 10 : 14,
      data: stateEntries.map(e => ({
        value: e[1].value,
        itemStyle: { color: e[0] === userState ? '#E89923' : '#00539B', borderRadius: [0, 3, 3, 0] }
      })).reverse(),
    }],
  });

  // -- Topic donut --
  const topicData = Object.entries(stats.topics)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v], i) => ({ name: TOPIC_LABELS[k] || k, value: v, itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] } }));

  charts.topics = echarts.init(document.getElementById("chart-topics"));
  charts.topics.setOption({
    tooltip: { ...tooltipBase, trigger: "item", formatter: "{b}: {c} ({d}%)" },
    series: [{
      type: "pie",
      radius: isMobile ? ["35%", "65%"] : ["42%", "72%"],
      center: ["50%", "52%"],
      label: {
        fontSize: isMobile ? 10 : 11,
        color: "#4a5568",
        overflow: "truncate",
        width: isMobile ? 60 : 80,
      },
      labelLayout: { hideOverlap: true },
      emphasis: { label: { fontWeight: "bold" } },
      data: topicData,
    }],
  });

  // -- Timeline --
  const timeEntries = Object.entries(stats.timeline).sort((a, b) => a[0].localeCompare(b[0]));
  charts.timeline = echarts.init(document.getElementById("chart-timeline"));
  charts.timeline.setOption({
    tooltip: {
      ...tooltipBase, trigger: "axis",
      formatter: (p) => {
        const d = p[0]; const t = stats.timeline[d.name];
        return `<b>${d.name}</b><br/>Savings: ${formatMoney(t.savings)}<br/>Contracts: ${t.count}`;
      }
    },
    grid: { left: isMobile ? 45 : 60, right: isMobile ? 10 : 40, top: 16, bottom: 28 },
    xAxis: { type: "category", data: timeEntries.map(e => e[0]), axisLabel: { fontSize: isMobile ? 9 : 10, rotate: isMobile ? 30 : 0 } },
    yAxis: [
      { type: "value", name: isMobile ? "" : "Savings", nameTextStyle: { fontSize: 10, color: "#999" }, axisLabel: { formatter: v => formatMoney(v), fontSize: isMobile ? 9 : 10 }, splitLine: { lineStyle: { color: "#f0f0f0" } } },
      isMobile
        ? { show: false }
        : { type: "value", name: "Contracts", nameTextStyle: { fontSize: 10, color: "#999" }, axisLabel: { formatter: v => v.toLocaleString(), fontSize: 10 }, splitLine: { show: false } },
    ],
    series: [
      {
        type: "bar", barMaxWidth: isMobile ? 14 : 20, name: "Savings",
        data: timeEntries.map(e => e[1].savings),
        itemStyle: { color: '#E89923', borderRadius: [3, 3, 0, 0] },
      },
      {
        type: "line", name: "Contracts", smooth: true,
        data: timeEntries.map(e => e[1].count),
        lineStyle: { color: '#00539B', width: 2 },
        showSymbol: false, areaStyle: { color: 'rgba(0,83,155,0.06)' },
        yAxisIndex: isMobile ? 0 : 1,
      },
    ],
  });

  // -- Agencies --
  const agencyCount = isMobile ? 7 : 10;
  const agencyEntries = Object.entries(stats.agencies)
    .sort((a, b) => b[1].value - a[1].value)
    .slice(0, agencyCount);
  const agencyLabels = agencyEntries.map(e => e[0].replace(/^Department of (the )?/i, "")).reverse();
  const agencyFull = agencyEntries.map(e => e[0]).reverse();
  charts.agencies = echarts.init(document.getElementById("chart-agencies"));
  charts.agencies.setOption({
    tooltip: {
      ...tooltipBase, trigger: "axis", axisPointer: { type: "shadow" },
      formatter: (p) => {
        const d = p[0]; const fullName = agencyFull[d.dataIndex];
        const a = stats.agencies[fullName];
        if (!a) return d.name;
        return `<b>${fullName}</b><br/>Value: ${formatMoney(a.value)}<br/>Savings: ${formatMoney(a.savings)}<br/>Contracts: ${a.count}`;
      }
    },
    grid: { left: isMobile ? 80 : 140, right: 12, top: 8, bottom: 24 },
    xAxis: { type: "value", axisLabel: { formatter: v => formatMoney(v), fontSize: isMobile ? 9 : 10 }, splitLine: { lineStyle: { color: "#f0f0f0" } } },
    yAxis: {
      type: "category", data: agencyLabels,
      axisLabel: { fontSize: isMobile ? 9 : 10, width: isMobile ? 70 : 125, overflow: "truncate", ellipsis: "..." }
    },
    series: [{
      type: "bar", barWidth: isMobile ? 10 : 12,
      data: agencyEntries.map((e, i) => ({
        value: e[1].value,
        itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length], borderRadius: [0, 3, 3, 0] }
      })).reverse(),
    }],
  });

  // Resize (cleanup previous handler)
  // Debounced resize: reflow charts + reinit if mobile state changed
  if (_resizeHandler) window.removeEventListener("resize", _resizeHandler);
  let _resizeTimer = null;
  let _wasMobile = isMobile;
  _resizeHandler = () => {
    Object.values(charts).forEach(c => c.resize());
    // Reinit charts if crossed the mobile breakpoint (options change)
    clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(() => {
      const nowMobile = window.innerWidth < 768;
      if (nowMobile !== _wasMobile) {
        _wasMobile = nowMobile;
        initCharts();
      }
    }, 300);
  };
  window.addEventListener("resize", _resizeHandler);
}

function render() {
  if (!appData) return;

  const all = getFilteredContracts();
  let filtered = filterByTab(all);

  // Apply search filter
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    filtered = filtered.filter(c =>
      (c.agency || "").toLowerCase().includes(q) ||
      (c.vendor || "").toLowerCase().includes(q) ||
      (c.description || "").toLowerCase().includes(q) ||
      (c.state || "").toLowerCase().includes(q) ||
      (c.topic || "").toLowerCase().includes(q) ||
      (c.contract_id || "").toLowerCase().includes(q)
    );
  }

  // KPIs
  document.getElementById("kpi-contracts").textContent = appData.stats.total_contracts.toLocaleString();
  document.getElementById("kpi-value").textContent = formatMoney(appData.stats.total_value);
  document.getElementById("kpi-savings").textContent = formatMoney(appData.stats.total_savings);
  document.getElementById("kpi-flagged").textContent = appData.stats.flagged.toLocaleString();

  // Date range context for contracts KPI
  const months = Object.keys(appData.stats.timeline || {}).sort();
  if (months.length >= 2) {
    const fmt = (m) => { const [y, mo] = m.split("-"); return new Date(y, mo - 1).toLocaleDateString("en-US", { month: "short", year: "numeric" }); };
    document.getElementById("kpi-contracts-ctx").textContent = `${fmt(months[0])} \u2013 ${fmt(months[months.length - 1])} \u00B7 ${all.length} in feed`;
  }

  // Tab counts
  document.getElementById("tab-scrutiny-count").textContent =
    all.filter(c => c.scrutiny >= 0.3).length;
  document.getElementById("tab-value-count").textContent =
    all.filter(c => c.value >= 1e6).length;
  document.getElementById("tab-cut-count").textContent =
    all.filter(c => c.savings > 0).length;

  // State impact banner
  const bannerEl = document.getElementById("state-banner");
  const userState = resolveUserState();
  if (userState && appData.stats.states[userState]) {
    const s = appData.stats.states[userState];
    bannerEl.innerHTML = `
      <div class="info-icon">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M9 1C6.2 1 4 3.2 4 6c0 4.5 5 10 5 10s5-5.5 5-10C14 3.2 11.8 1 9 1z" stroke="#fff" stroke-width="1.5" fill="none"/>
          <circle cx="9" cy="6" r="2" fill="#fff"/>
        </svg>
      </div>
      <div class="info-text">
        <strong>${userState}: ${s.count.toLocaleString()} contracts affected</strong>
        totaling ${formatMoney(s.value)} in value, ${formatMoney(s.savings)} in claimed savings.
      </div>`;
    bannerEl.dataset.tooltip = "Contract counts and values are based on Place of Performance data. Not all contracts have geographic data available.";
    bannerEl.style.display = "flex";
  } else {
    bannerEl.style.display = "none";
  }

  // Section label + view toggle
  const tabLabels = {
    scrutiny: "Under scrutiny",
    "high-value": "High value",
    "just-cut": "Recently cut",
  };
  const sectionLabel = document.getElementById("feed-section-label");
  // Preserve search input if it exists and is focused
  const existingSearch = document.getElementById("feed-search");
  const searchFocused = existingSearch && document.activeElement === existingSearch;

  sectionLabel.innerHTML = `
    <span>${tabLabels[activeTab]} \u00B7 ${filtered.length} contracts \u00B7 ranked by relevance to your topics</span>
    ${renderViewToggle()}`;

  // Search row (separate from section label)
  let searchRow = document.getElementById("feed-search-row");
  if (!searchRow) {
    searchRow = document.createElement("div");
    searchRow.id = "feed-search-row";
    searchRow.className = "feed-search-row";
    sectionLabel.parentNode.insertBefore(searchRow, sectionLabel.nextSibling);
  }
  searchRow.innerHTML = `<input class="feed-search" id="feed-search" type="text" placeholder="Search contracts by agency, vendor, description, state..." value="${esc(searchQuery)}">`;

  // Restore focus and cursor position
  if (searchFocused) {
    const newSearch = document.getElementById("feed-search");
    if (newSearch) {
      newSearch.focus();
      newSearch.setSelectionRange(searchQuery.length, searchQuery.length);
    }
  }

  // Bind view toggle buttons
  sectionLabel.querySelectorAll(".view-toggle-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      viewMode = btn.dataset.mode;
      render();
    });
  });

  // Bind search
  const searchInput = document.getElementById("feed-search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value;
      showLimit = 20; // Reset pagination on search
      render();
    });
  }

  // Cards + Table
  const grid = document.getElementById("cards-grid");
  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="info-banner">
        <div class="info-icon">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="9" r="7.5" stroke="#fff" stroke-width="1.5"/>
            <line x1="9" y1="5.5" x2="9" y2="9.5" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="9" cy="12.5" r="0.8" fill="#fff"/>
          </svg>
        </div>
        <div class="info-text"><strong>No contracts match this filter.</strong> Try selecting different topics or switching tabs.</div>
      </div>`;
    return;
  }

  const shown = filtered.slice(0, showLimit);
  let html = "";

  if (viewMode === "cards") {
    html = shown.map((c, i) => renderCard(c, i)).join("");
  } else if (viewMode === "table") {
    html = `<div style="grid-column:1/-1">${renderTable(shown, 0)}</div>`;
  } else {
    // hybrid: top 3 as cards, rest as table
    const top = shown.slice(0, 3);
    const rest = shown.slice(3);
    html = top.map((c, i) => renderCard(c, i)).join("");
    if (rest.length > 0) {
      html += `<div class="compact-table-divider" style="grid-column:1/-1"></div>`;
      html += `<div style="grid-column:1/-1">${renderTable(rest, 3)}</div>`;
    }
  }

  if (filtered.length > shown.length) {
    html += `<div class="show-more-wrap" style="grid-column:1/-1">` +
      `<span class="show-more-count">Showing ${shown.length} of ${filtered.length}</span>` +
      `<button class="show-more-btn" id="show-more-btn">Show more</button></div>`;
  }
  grid.innerHTML = html;

  // Bind "Show more" button
  const showMoreBtn = document.getElementById("show-more-btn");
  if (showMoreBtn) {
    showMoreBtn.addEventListener("click", () => {
      showLimit += 20;
      render();
    });
  }

  // Bind sort handlers on table headers
  grid.querySelectorAll("th.sortable").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (tableSortKey === key) {
        tableSortAsc = !tableSortAsc;
      } else {
        tableSortKey = key;
        tableSortAsc = key === "agency" || key === "state" || key === "description";
      }
      render();
    });
  });
}

function buildSidebar() {
  const container = document.getElementById("sidebar-categories");
  const topics = appData.topics
    .filter(t => (appData.stats.topics[t] || 0) > 0)
    .sort((a, b) => (appData.stats.topics[b] || 0) - (appData.stats.topics[a] || 0));
  container.innerHTML = topics
    .map(t => {
      const active = selectedTopics.has(t) ? " active" : "";
      const label = TOPIC_LABELS[t] || t;
      const count = appData.stats.topics[t] || 0;
      return `
        <li class="sidebar-nav-item${active}" data-topic="${t}">
          <span style="width:24px;text-align:right;font-size:12px;opacity:0.5;font-variant-numeric:tabular-nums">${count > 999 ? (count / 1000).toFixed(0) + "k" : count}</span>
          ${label}
        </li>`;
    })
    .join("");

  container.querySelectorAll(".sidebar-nav-item").forEach(item => {
    item.addEventListener("click", () => {
      const topic = item.dataset.topic;
      if (selectedTopics.has(topic)) {
        if (selectedTopics.size > 1) selectedTopics.delete(topic);
      } else {
        selectedTopics.add(topic);
      }
      item.classList.toggle("active", selectedTopics.has(topic));
      if (typeof trackInteraction === "function") trackInteraction("topics", topic);
      topicsAutoSelected = false;
      updateTopicExplainer();
      if (currentUser) saveTopics(currentUser.login);
      else localStorage.setItem("civic-topics-anon", JSON.stringify([...selectedTopics]));
      render();
    });
  });
}

function buildMobileTopics() {
  const container = document.getElementById("mobile-topics");
  const allTopics = appData.topics;
  container.innerHTML =
    `<span class="mobile-topic" data-topic="all">All</span>` +
    allTopics
      .map(t => {
        const active = selectedTopics.has(t) ? " active" : "";
        return `<span class="mobile-topic${active}" data-topic="${t}">${TOPIC_LABELS[t] || t}</span>`;
      })
      .join("");

  container.querySelectorAll(".mobile-topic").forEach(chip => {
    chip.addEventListener("click", () => {
      const topic = chip.dataset.topic;
      if (topic === "all") {
        selectedTopics = new Set(allTopics);
      } else {
        // Toggle
        if (selectedTopics.size === allTopics.length) {
          selectedTopics = new Set([topic]);
        } else if (selectedTopics.has(topic) && selectedTopics.size > 1) {
          selectedTopics.delete(topic);
        } else {
          selectedTopics.add(topic);
        }
      }
      // Update chip visuals
      container.querySelectorAll(".mobile-topic").forEach(c => {
        if (c.dataset.topic === "all") {
          c.classList.toggle("active", selectedTopics.size === allTopics.length);
        } else {
          c.classList.toggle("active", selectedTopics.has(c.dataset.topic));
        }
      });
      // Update sidebar too
      document.querySelectorAll("#sidebar-categories .sidebar-nav-item").forEach(item => {
        item.classList.toggle("active", selectedTopics.has(item.dataset.topic));
      });
      if (currentUser) saveTopics(currentUser.login);
      render();
    });
  });
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      activeTab = tab.dataset.tab;
      showLimit = 20;
      render();
    });
  });
}


// ── Auth ──────────────────────────────────────────────────────

function getStoredAuth() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY));
  } catch {
    return null;
  }
}

function saveStoredAuth(auth) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
}

function clearStoredAuth() {
  localStorage.removeItem(AUTH_KEY);
}

// ── Location ──────────────────────────────────────────────────

const LOCATION_KEY = "civic-lenses-location";

function getSavedLocation() {
  return localStorage.getItem(LOCATION_KEY);
}

function saveLocation(loc) {
  localStorage.setItem(LOCATION_KEY, loc);
  setLocationDisplay(loc);
  // Re-run auto-selection with new location
  if (appData && autoSelectTopicsFromState()) {
    buildSidebar();
    buildMobileTopics();
    render();
    initCharts();
  }
}

function setLocationDisplay(text) {
  const el = document.getElementById("location-text");
  const mel = document.getElementById("mobile-location-text");
  if (el) el.textContent = text;
  if (mel) mel.textContent = text;
}

async function reverseGeocode(lat, lon) {
  const resp = await fetch(
    `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&zoom=5`,
    { headers: { "Accept-Language": "en" } }
  );
  if (!resp.ok) return null;
  const data = await resp.json();
  return data.address?.state || data.address?.city || data.display_name?.split(",")[0] || null;
}

const STATE_LIST = [
  ["AL","Alabama"],["AK","Alaska"],["AZ","Arizona"],["AR","Arkansas"],
  ["CA","California"],["CO","Colorado"],["CT","Connecticut"],["DE","Delaware"],
  ["DC","District of Columbia"],["FL","Florida"],["GA","Georgia"],["HI","Hawaii"],
  ["ID","Idaho"],["IL","Illinois"],["IN","Indiana"],["IA","Iowa"],
  ["KS","Kansas"],["KY","Kentucky"],["LA","Louisiana"],["ME","Maine"],
  ["MD","Maryland"],["MA","Massachusetts"],["MI","Michigan"],["MN","Minnesota"],
  ["MS","Mississippi"],["MO","Missouri"],["MT","Montana"],["NE","Nebraska"],
  ["NV","Nevada"],["NH","New Hampshire"],["NJ","New Jersey"],["NM","New Mexico"],
  ["NY","New York"],["NC","North Carolina"],["ND","North Dakota"],["OH","Ohio"],
  ["OK","Oklahoma"],["OR","Oregon"],["PA","Pennsylvania"],["RI","Rhode Island"],
  ["SC","South Carolina"],["SD","South Dakota"],["TN","Tennessee"],["TX","Texas"],
  ["UT","Utah"],["VT","Vermont"],["VA","Virginia"],["WA","Washington"],
  ["WV","West Virginia"],["WI","Wisconsin"],["WY","Wyoming"],
];

function toggleLocationPicker() {
  const container = document.getElementById("location-picker-inline");
  if (container) {
    container.remove();
    return;
  }

  // On mobile, sidebar is hidden. Mount picker in the main dashboard instead.
  const card = document.querySelector(".sidebar-profile-card") || document.querySelector(".dashboard");

  const picker = document.createElement("div");
  picker.id = "location-picker-inline";
  picker.className = "location-picker-inline";
  picker.innerHTML = `
    <button class="loc-auto-btn" id="loc-auto-btn">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3">
        <circle cx="7" cy="7" r="5.5"/>
        <circle cx="7" cy="7" r="1.5" fill="currentColor"/>
        <line x1="7" y1="0" x2="7" y2="2.5"/>
        <line x1="7" y1="11.5" x2="7" y2="14"/>
        <line x1="0" y1="7" x2="2.5" y2="7"/>
        <line x1="11.5" y1="7" x2="14" y2="7"/>
      </svg>
      Auto-detect
    </button>
    <div class="loc-state-list" id="loc-state-list">
      ${STATE_LIST.map(([abbr, name]) => `<div class="loc-state-item" data-state="${name}" data-abbr="${abbr}">${abbr}<span>${name}</span></div>`).join("")}
    </div>`;
  card.appendChild(picker);

  // Auto-detect click
  document.getElementById("loc-auto-btn").onclick = async (e) => {
    e.stopPropagation();
    const btn = e.currentTarget;
    btn.textContent = "Locating...";
    if (navigator.geolocation) {
      try {
        const pos = await new Promise((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000 });
        });
        const name = await reverseGeocode(pos.coords.latitude, pos.coords.longitude);
        if (name) {
          saveLocation(name);
          picker.remove();
          return;
        }
      } catch {}
    }
    btn.textContent = "Could not detect. Pick below.";
  };

  // State item clicks
  picker.querySelectorAll(".loc-state-item").forEach(item => {
    item.addEventListener("click", (e) => {
      e.stopPropagation();
      saveLocation(item.dataset.state);
      picker.remove();
    });
  });
}

async function requestLocation() {
  toggleLocationPicker();
}

function initLocation() {
  const saved = getSavedLocation();
  if (currentUser?.location) {
    setLocationDisplay(currentUser.location);
  } else if (saved) {
    setLocationDisplay(saved);
  } else {
    setLocationDisplay("Set location");
  }

  // Make location clickable for unauthenticated or location-less users
  const sidebar = document.getElementById("sidebar-location");
  const mobile = document.getElementById("mobile-location");
  [sidebar, mobile].forEach(el => {
    if (!el) return;
    el.style.cursor = "pointer";
    el.addEventListener("click", () => {
      if (!currentUser?.location) requestLocation();
    });
  });
}

const STATE_NAMES_TO_ABBREV = {
  "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
  "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
  "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
  "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
  "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
  "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
  "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
  "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
  "new mexico": "NM", "new york": "NY", "north carolina": "NC",
  "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
  "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
  "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
  "vermont": "VT", "virginia": "VA", "washington": "WA",
  "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
  "district of columbia": "DC", "washington dc": "DC", "washington, dc": "DC",
};
const ALL_ABBREVS = new Set(Object.values(STATE_NAMES_TO_ABBREV));

function resolveUserState() {
  // Try GitHub profile location first
  const loc = currentUser?.location || getSavedLocation();
  if (!loc) return null;
  const lower = loc.toLowerCase().trim();
  // Direct abbreviation match (e.g., "NC")
  const upper = loc.toUpperCase().trim();
  if (upper.length === 2 && ALL_ABBREVS.has(upper)) return upper;
  // "City, ST" pattern
  const m = loc.match(/,\s*([A-Z]{2})\s*$/);
  if (m && ALL_ABBREVS.has(m[1])) return m[1];
  // Full state name
  if (STATE_NAMES_TO_ABBREV[lower]) return STATE_NAMES_TO_ABBREV[lower];
  // State name anywhere in string (e.g., "Durham, North Carolina")
  for (const [name, abbr] of Object.entries(STATE_NAMES_TO_ABBREV)) {
    if (lower.includes(name)) return abbr;
  }
  return null;
}

// ── Topics persistence & auto-selection ───────────────────────

let topicsAutoSelected = false;

function autoSelectTopicsFromState() {
  const userState = resolveUserState();
  if (!userState || !appData?.stats?.state_topics?.[userState]) return false;

  // Check if user already has saved preferences
  const login = currentUser?.login;
  if (login && localStorage.getItem(`civic-topics-${login}`)) return false;
  if (!login && localStorage.getItem("civic-topics-anon")) return false;

  const stateTopics = appData.stats.state_topics[userState];
  const top3 = Object.entries(stateTopics)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(e => e[0]);

  if (top3.length === 0) return false;

  selectedTopics = new Set(top3);
  topicsAutoSelected = true;

  // Show explainer
  const explainer = document.getElementById("topic-explainer");
  const text = document.getElementById("topic-explainer-text");
  const btn = document.getElementById("topic-explainer-btn");
  const labels = top3.map(t => TOPIC_LABELS[t] || t).join(", ");
  text.textContent = `Showing ${labels}. These topics have the most affected contracts in ${userState}. Tap a topic to change.`;
  explainer.style.display = "flex";

  btn.onclick = () => {
    explainer.style.display = "none";
    topicsAutoSelected = false;
    // Save as manual preference so auto-select doesn't trigger again
    if (login) saveTopics(login);
    else localStorage.setItem("civic-topics-anon", JSON.stringify([...selectedTopics]));
  };

  return true;
}

function updateTopicExplainer() {
  if (!topicsAutoSelected) {
    const el = document.getElementById("topic-explainer");
    if (el) el.style.display = "none";
  }
}

function loadSavedTopics(login) {
  try {
    const saved = localStorage.getItem(`civic-topics-${login}`);
    if (saved) {
      selectedTopics = new Set(JSON.parse(saved));
      topicsAutoSelected = false;
    }
  } catch {}
}

function saveTopics(login) {
  if (login) {
    localStorage.setItem(`civic-topics-${login}`, JSON.stringify([...selectedTopics]));
  }
}

function updateAuthUI() {
  const topBtn = document.getElementById("auth-btn-top");
  const topLabel = document.getElementById("auth-btn-label");
  const topAvatar = document.getElementById("auth-btn-avatar");
  const topIcon = topBtn.querySelector(".github-icon");
  const menu = document.getElementById("auth-menu");
  const menuUser = document.getElementById("auth-menu-user");
  const menuLogout = document.getElementById("auth-menu-logout");

  // Owl variants
  const owlBasic = document.querySelector(".owl-basic");
  const owlEnhanced = document.querySelector(".owl-enhanced");
  // Chat model badge
  const modelBadge = document.getElementById("chat-model-badge");

  if (currentUser) {
    topLabel.textContent = currentUser.login;
    topAvatar.src = currentUser.avatar_url;
    topAvatar.style.display = "block";
    topIcon.style.display = "none";
    topBtn.onclick = (e) => {
      e.stopPropagation();
      menu.classList.toggle("open");
      if (menu.classList.contains("open")) {
        const r = topBtn.getBoundingClientRect();
        menu.style.top = (r.bottom + 6) + "px";
        menu.style.right = (window.innerWidth - r.right) + "px";
      }
    };
    menuUser.textContent = currentUser.name || currentUser.login;
    menuLogout.onclick = () => {
      menu.classList.remove("open");
      handleLogout();
    };
    if (currentUser.location) {
      setLocationDisplay(currentUser.location);
    }
    // Swap to enhanced owl
    if (owlBasic) owlBasic.style.display = "none";
    if (owlEnhanced) owlEnhanced.style.display = "block";
    if (modelBadge) { modelBadge.textContent = "GPT-4o"; modelBadge.style.display = ""; modelBadge.className = "chat-model-badge badge-gpt"; }
  } else {
    topLabel.textContent = "Sign in with GitHub";
    topAvatar.style.display = "none";
    topIcon.style.display = "block";
    menu.classList.remove("open");
    topBtn.onclick = handleLogin;
    // Swap to basic owl
    if (owlBasic) owlBasic.style.display = "block";
    if (owlEnhanced) owlEnhanced.style.display = "none";
    if (modelBadge) { modelBadge.textContent = "LFM2.5-350M"; modelBadge.style.display = ""; modelBadge.className = "chat-model-badge badge-lfm"; }
  }
}

// Close menu when clicking outside
document.addEventListener("click", () => {
  document.getElementById("auth-menu")?.classList.remove("open");
});

async function fetchGitHubUser(token) {
  const resp = await fetch("https://api.github.com/user", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) return null;
  return resp.json();
}

async function handleLogin() {
  try {
    const { token, username, avatarUrl } = await connectGitHub("read:user", "civic-lenses");
    const user = await fetchGitHubUser(token);
    currentUser = user || { login: username, avatar_url: avatarUrl };
    saveStoredAuth({ token, user: currentUser });
    loadSavedTopics(currentUser.login);
    updateAuthUI();
    render();
  } catch (err) {
    if (err.message === "OAuth flow cancelled") return;
    console.warn("[auth] Login failed:", err.message);
  }
}

function handleLogout() {
  if (currentUser) saveTopics(currentUser.login);
  currentUser = null;
  clearStoredAuth();
  updateAuthUI();
}

async function restoreAuth() {
  const stored = getStoredAuth();
  if (!stored || !stored.token) return;
  try {
    await verifyToken(stored.token);
    currentUser = stored.user;
    loadSavedTopics(currentUser.login);
    updateAuthUI();
  } catch {
    clearStoredAuth();
  }
}

// ── Chat: Two-tier AI inference pipeline ─────────────────────

// -- Tier 2: Dashboard tools --

const DASHBOARD_TOOLS = {
  filter_topics: (topics) => {
    selectedTopics = new Set(topics);
    // Update sidebar visuals
    document.querySelectorAll("#sidebar-categories .sidebar-nav-item").forEach(item => {
      item.classList.toggle("active", selectedTopics.has(item.dataset.topic));
    });
    document.querySelectorAll("#mobile-topics .mobile-topic").forEach(chip => {
      if (chip.dataset.topic === "all") {
        chip.classList.toggle("active", selectedTopics.size === appData.topics.length);
      } else {
        chip.classList.toggle("active", selectedTopics.has(chip.dataset.topic));
      }
    });
  },
  set_location: (state) => {
    saveLocation(state);
  },
  highlight_chart: (chartId, ...dataNames) => {
    const chart = charts[chartId];
    if (!chart) return;
    const option = chart.getOption();
    const HIGHLIGHT_COLORS = ["#E89923", "#c53030", "#5a67d8", "#2D6A4F"];
    const userState = resolveUserState();

    // Get the axis data array
    let axisData = null;
    if (option.yAxis?.[0]?.data) axisData = option.yAxis[0].data;
    else if (option.xAxis?.[0]?.data) axisData = option.xAxis[0].data;

    if (axisData && option.series?.[0]?.data) {
      // Bar chart: color specific bars, dim others
      const names = dataNames.flat().filter(Boolean);
      const newData = option.series[0].data.map((item, i) => {
        const name = axisData[i];
        const val = typeof item === "object" ? item.value : item;
        const nameIdx = names.indexOf(name);
        let color;
        if (nameIdx >= 0) {
          color = HIGHLIGHT_COLORS[nameIdx % HIGHLIGHT_COLORS.length];
        } else if (name === userState) {
          color = "rgba(232, 153, 35, 0.35)"; // user state stays faint gold
        } else {
          color = "rgba(0, 83, 155, 0.2)"; // dimmed
        }
        return { value: val, itemStyle: { color, borderRadius: [0, 3, 3, 0] } };
      });
      chart.setOption({ series: [{ data: newData }] });
      // Show tooltip on first highlighted item
      const firstIdx = names.length > 0 ? axisData.indexOf(names[0]) : -1;
      if (firstIdx >= 0) {
        chart.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: firstIdx });
      }
    } else if (option.series?.[0]?.data) {
      // Pie chart: use select
      const names = dataNames.flat().filter(Boolean);
      chart.dispatchAction({ type: "downplay", seriesIndex: 0 });
      names.forEach(name => {
        const idx = option.series[0].data.findIndex(d => d.name === name);
        if (idx >= 0) {
          chart.dispatchAction({ type: "highlight", seriesIndex: 0, dataIndex: idx });
          chart.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: idx });
        }
      });
    }
    // Auto-reset after 8 seconds
    setTimeout(() => initCharts(), 8000);
  },
  switch_tab: (tab) => {
    activeTab = tab;
    document.querySelectorAll(".tab").forEach(t => {
      t.classList.toggle("active", t.dataset.tab === tab);
    });
  },
  scroll_to: (sectionId) => {
    const el = document.getElementById(sectionId);
    if (!el) return;
    // Scroll with offset for sticky topbar
    const topbar = document.querySelector(".topbar");
    const offset = topbar ? topbar.offsetHeight + 16 : 80;
    const y = el.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({ top: y, behavior: "smooth" });
    // Add a brief highlight pulse to the target
    el.closest(".chart-panel, .kpi-card, .compact-table-wrap, .contract-card")
      ?.classList.add("pulse-highlight");
    setTimeout(() => {
      el.closest(".chart-panel, .kpi-card, .compact-table-wrap, .contract-card")
        ?.classList.remove("pulse-highlight");
    }, 2000);
  },
  highlight_text: (selector, text) => {
    const el = document.querySelector(selector);
    if (!el) return;
    // Wrap matching text in a highlight span
    const regex = new RegExp(`(${text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, "gi");
    const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walk.nextNode()) nodes.push(walk.currentNode);
    nodes.forEach(node => {
      if (regex.test(node.textContent)) {
        const span = document.createElement("span");
        span.innerHTML = node.textContent.replace(regex, `<mark class="text-highlight">$1</mark>`);
        node.parentNode.replaceChild(span, node);
        // Auto-remove highlight after 3s
        setTimeout(() => {
          span.querySelectorAll(".text-highlight").forEach(m => {
            m.classList.add("fade-out");
            setTimeout(() => { m.outerHTML = m.textContent; }, 500);
          });
        }, 3000);
      }
    });
  },
};

// -- Regex-based intent extraction (Tier 1 fallback) --

function extractIntentLocal(question) {
  if (!appData) return { entities: [], topic: null, dimension: null, operation: null };

  const lower = question.toLowerCase().trim();
  const intent = { entities: [], topic: null, dimension: null, operation: null };

  // Greetings and short messages: don't parse as data queries
  if (/^(hi|hey|hello|yo|sup|thanks|thank you|ok|okay|bye|good|huh|uh|what|hm+)\b/i.test(lower) && lower.length < 20) {
    intent.operation = "help";
    return intent;
  }

  // Extract state entities (full names only, not abbreviations alone)
  for (const [name, abbr] of Object.entries(STATE_NAMES_TO_ABBREV)) {
    if (name.length > 3 && lower.includes(name)) {
      intent.entities.push({ type: "state", value: abbr, name });
    }
  }
  // Extract topic FIRST (takes priority over abbreviation matching)
  for (const [key, label] of Object.entries(TOPIC_LABELS)) {
    if (lower.includes(key.replace(/_/g, " ")) || lower.includes(label.toLowerCase())) {
      intent.topic = key;
      break;
    }
  }

  // Extract operation
  const operationPatterns = [
    { pattern: /\bcompar|\bvs\.?\b|\bversus\b|\bdiffer/i, op: "compare" },
    { pattern: /\btrend\b|over time|\btimeline\b|\bmonth\b/i, op: "trend" },
    { pattern: /\btop\b|\bmost\b|\bhighest\b|\blargest\b|\bbiggest\b|\brank/i, op: "rank" },
    { pattern: /\bshow\b|\bfilter\b|\bonly\b/i, op: "filter" },
    { pattern: /\bwhat is\b|\bwhat are\b|\bdefine\b|\bexplain\b|\btell me about\b|\bwhat'?s\b/i, op: "define" },
    { pattern: /\bhow (many|much)\b/i, op: "count" },
    { pattern: /\bhelp\b|\bwhat can\b/i, op: "help" },
  ];
  for (const { pattern, op } of operationPatterns) {
    if (pattern.test(lower)) {
      intent.operation = op;
      break;
    }
  }

  // Bare state abbreviations: only match if the word is standalone
  // and not a common English word (me, or, in, oh, hi, ok, etc.)
  const AMBIGUOUS_ABBREVS = new Set(["ME", "OR", "IN", "OH", "HI", "OK", "MA", "PA", "DE", "LA"]);
  const words = question.split(/\s+/);
  for (const w of words) {
    const clean = w.replace(/[^A-Za-z]/g, "");
    const up = clean.toUpperCase();
    if (up.length !== 2 || !ALL_ABBREVS.has(up)) continue;
    if (intent.entities.some(e => e.value === up)) continue;
    // Skip ambiguous abbreviations unless they look intentional
    // (all caps in original, or preceded by "in"/"from"/"vs")
    if (AMBIGUOUS_ABBREVS.has(up)) {
      if (clean !== up) continue; // not all-caps, skip
      const wIdx = words.indexOf(w);
      const prev = wIdx > 0 ? words[wIdx - 1].toLowerCase() : "";
      if (!["in", "from", "vs", "vs.", "and", "to", "&"].includes(prev)) continue;
    }
    intent.entities.push({ type: "state", value: up, name: up });
  }

  // Extract dimension (use word boundaries to avoid substring matches)
  const dimensionPatterns = [
    { pattern: /\bscrutin|\brisk\b|\bdoge\b/i, dim: "scrutiny" },
    { pattern: /\btransparen|\bvague\b|\bopaque\b/i, dim: "transparency" },
    { pattern: /\bsaving|\bcuts?\b|\breduc/i, dim: "savings" },
    { pattern: /\bvalue\b|\bworth\b|\bcost\b|\bamount\b|\bspending\b/i, dim: "value" },
    { pattern: /\bimpact\b|\bcitizen\b/i, dim: "impact" },
  ];
  for (const { pattern, dim } of dimensionPatterns) {
    if (pattern.test(lower)) {
      intent.dimension = dim;
      break;
    }
  }

  return intent;
}

// -- LFM2.5 loader (lazy, non-blocking) --

let lfm2Pipeline = null;
let lfm2Loading = false;

let lfm2LoadPromise = null;

let lfm2Progress = 0; // 0 to 1

async function loadLFM2(onProgress) {
  if (lfm2Pipeline) return lfm2Pipeline;
  if (lfm2LoadPromise) return lfm2LoadPromise;

  lfm2Loading = true;
  lfm2LoadPromise = (async () => {
    try {
      lfm2Progress = 0.05;
      if (onProgress) onProgress(lfm2Progress);

      const { initRuntime, LFM2ForCausalLM } = await import("./lfm2.js");
      lfm2Progress = 0.1;
      if (onProgress) onProgress(lfm2Progress);

      const { device } = await initRuntime("webgpu");
      lfm2Progress = 0.15;
      if (onProgress) onProgress(lfm2Progress);

      lfm2Pipeline = await LFM2ForCausalLM.fromHub("LiquidAI/LFM2.5-350M-ONNX", {
        device,
        precision: "q4",
      });

      lfm2Progress = 1;
      if (onProgress) onProgress(1);
      return lfm2Pipeline;
    } catch (e) {
      console.warn("LFM2.5 failed to load:", e);
      lfm2Progress = 1;
      if (onProgress) onProgress(1);
      return null;
    } finally {
      lfm2Loading = false;
    }
  })();
  return lfm2LoadPromise;
}

async function extractIntentLFM2(question) {
  if (!lfm2Pipeline) return extractIntentLocal(question);

  const topicKeys = Object.keys(TOPIC_LABELS).join(", ");
  const systemPrompt = `You parse user questions about US federal spending data into structured JSON.
Topics: ${topicKeys}
Dimensions: scrutiny, transparency, savings, value, impact
Operations: compare, trend, rank, filter, define, count, help
Output ONLY valid JSON: {"entities":[],"topic":null,"dimension":null,"operation":null}`;

  try {
    const messages = [
      { role: "system", content: systemPrompt },
      { role: "user", content: question },
    ];
    const text = await lfm2Pipeline.chat(messages, { maxNewTokens: 100 });
    console.log("[owl] LFM2.5 raw output:", text);

    // Try to extract JSON, be forgiving about malformed output
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      // Attempt to fix common LLM JSON issues: trailing commas, truncation
      let jsonStr = jsonMatch[0]
        .replace(/,\s*([}\]])/g, "$1")   // remove trailing commas
        .replace(/'/g, '"');              // single quotes to double
      // If truncated (missing closing), try to close it
      const opens = (jsonStr.match(/\[/g) || []).length;
      const closes = (jsonStr.match(/\]/g) || []).length;
      for (let i = 0; i < opens - closes; i++) jsonStr += "]";
      if (!jsonStr.endsWith("}")) jsonStr += "}";

      try {
        const parsed = JSON.parse(jsonStr);
        if (parsed && typeof parsed === "object") {
          return {
            entities: Array.isArray(parsed.entities) ? parsed.entities : [],
            topic: parsed.topic || null,
            dimension: parsed.dimension || null,
            operation: parsed.operation || null,
          };
        }
      } catch (parseErr) {
        console.warn("[owl] JSON parse failed after cleanup:", jsonStr, parseErr);
      }
    }
  } catch (e) {
    console.warn("[owl] LFM2.5 inference failed, falling back to regex:", e);
  }
  return extractIntentLocal(question);
}

// -- Intent-to-action mapper (Tier 2) --

function processIntent(intent, question) {
  const lower = (question || "").toLowerCase();
  if (!appData) return { actions: [], responseText: "Still loading data. Try again in a moment." };

  const actions = [];
  const stats = appData.stats;

  // Help / greetings
  if (intent.operation === "help") {
    const greetings = [
      "Hey there! I'm here to help you explore the data.",
      "Hello! Ask me about states, topics, or terms.",
      "Hi! I can look things up and control the dashboard for you.",
    ];
    return {
      actions: [],
      responseText: greetings[Math.floor(Math.random() * greetings.length)] + " Try:\n\n"
        + "\u2022 \"Show me healthcare contracts\"\n"
        + "\u2022 \"Which state has the most cuts?\"\n"
        + "\u2022 \"Compare Texas and California\"\n"
        + "\u2022 \"What is scrutiny score?\"\n"
        + "\u2022 \"Show me the timeline\"",
    };
  }

  // State entities present
  if (intent.entities.length > 0) {
    const stateEntities = intent.entities.filter(e => e.type === "state");

    if (intent.operation === "compare" && stateEntities.length >= 2) {
      const rows = stateEntities.map(e => {
        const sd = stats.states[e.value];
        if (!sd) return `<b>${e.value}</b>: No data available.`;
        return `<b>${e.value}</b>: ${sd.count} contracts, ${formatMoney(sd.value)} value, ${formatMoney(sd.savings)} savings`;
      });
      actions.push({ tool: "highlight_chart", args: ["states", ...stateEntities.map(e => e.value)] });
      actions.push({ tool: "scroll_to", args: ["chart-states"] });
      return { actions, responseText: rows.join("\n") };
    }

    if (stateEntities.length === 1) {
      const abbr = stateEntities[0].value;
      const sd = stats.states[abbr];
      if (sd) {
        const st = stats.state_topics?.[abbr] || {};
        const topTopics = Object.entries(st).sort((a, b) => b[1] - a[1]).slice(0, 3);
        actions.push({ tool: "highlight_chart", args: ["states", abbr] });
        actions.push({ tool: "scroll_to", args: ["chart-states"] });
        let text = `<b>${abbr}</b>: ${sd.count} contracts, ${formatMoney(sd.value)} total value, ${formatMoney(sd.savings)} claimed savings.`;
        if (topTopics.length) {
          text += "\n\nTop topics: " + topTopics.map(([t, c]) => `${TOPIC_LABELS[t] || t} (${c})`).join(", ");
        }
        return { actions, responseText: text };
      }
      return { actions: [], responseText: `No data found for ${abbr}.` };
    }
  }

  // Topic filter
  if (intent.topic) {
    const key = intent.topic;
    const label = TOPIC_LABELS[key] || key;
    const count = stats.topics[key] || 0;
    const recs = appData.recommendations[key] || [];

    if (intent.operation === "filter") {
      actions.push({ tool: "filter_topics", args: [[key]] });
      actions.push({ tool: "scroll_to", args: ["cards-grid"] });
      // Compute top agencies within this topic from the contracts data
      const topicContracts = (appData.contracts || []).filter(c => c.topic === key);
      const agencyCounts = {};
      topicContracts.forEach(c => {
        if (!agencyCounts[c.agency]) agencyCounts[c.agency] = { count: 0, value: 0 };
        agencyCounts[c.agency].count++;
        agencyCounts[c.agency].value += c.value;
      });
      const topAgencies = Object.entries(agencyCounts)
        .sort((a, b) => b[1].value - a[1].value)
        .slice(0, 3)
        .map(([a, d]) => `${a} (${formatMoney(d.value)}, ${d.count})`);

      return {
        actions,
        responseText: `Filtered to <b>${label}</b> (${count.toLocaleString()} contracts).${topAgencies.length ? "\n\nTop agencies: " + topAgencies.join(", ") : ""}`,
      };
    }

    let text = `<b>${label}</b>: ${count.toLocaleString()} contracts in the dataset.`;
    if (recs[0]) {
      text += `\n\nTop contract: "${esc(recs[0].description.substring(0, 80))}..." (${formatMoney(recs[0].value)}, ${recs[0].agency})`;
    }
    actions.push({ tool: "highlight_chart", args: ["topics", label] });
    return { actions, responseText: text };
  }

  // Trend operation
  if (intent.operation === "trend") {
    actions.push({ tool: "scroll_to", args: ["chart-timeline"] });
    const timeEntries = Object.entries(stats.timeline).sort((a, b) => a[0].localeCompare(b[0]));
    const latest = timeEntries[timeEntries.length - 1];
    const peak = timeEntries.reduce((max, e) => e[1].savings > max[1].savings ? e : max, timeEntries[0]);
    return {
      actions,
      responseText: `Scrolled to the timeline. Peak savings month: <b>${peak[0]}</b> with ${formatMoney(peak[1].savings)} across ${peak[1].count} contracts.`
        + (latest ? `\nMost recent: <b>${latest[0]}</b> with ${formatMoney(latest[1].savings)} in savings.` : ""),
    };
  }

  // Rank operation (top states)
  if (intent.operation === "rank" && (!intent.dimension || intent.dimension === "savings" || intent.dimension === "value")) {
    const dim = intent.dimension === "value" ? "value" : "savings";
    const isAgency = /\bagenc/i.test(lower);

    if (isAgency && stats.agencies) {
      // Rank agencies
      const top5 = Object.entries(stats.agencies)
        .sort((a, b) => b[1][dim] - a[1][dim])
        .slice(0, 5);
      actions.push({ tool: "scroll_to", args: ["chart-agencies"] });
      return {
        actions,
        responseText: `Top 5 agencies by ${dim}:\n` + top5.map(([a, d], i) =>
          `${i + 1}. <b>${a}</b>: ${formatMoney(d[dim])} (${d.count} contracts)`
        ).join("\n"),
      };
    }

    // Rank states (default)
    const top5 = Object.entries(stats.states)
      .sort((a, b) => b[1][dim] - a[1][dim])
      .slice(0, 5);
    actions.push({ tool: "scroll_to", args: ["chart-states"] });
    actions.push({ tool: "highlight_chart", args: ["states", top5[0][0]] });
    return {
      actions,
      responseText: `Top 5 states by ${dim}:\n` + top5.map(([s, d], i) =>
        `${i + 1}. <b>${s}</b>: ${formatMoney(d[dim])} (${d.count} contracts)`
      ).join("\n"),
    };
  }

  // Dimension-specific definitions
  if (intent.operation === "define" || intent.dimension) {
    if (intent.dimension === "scrutiny") {
      return { actions: [], responseText: "<b>DOGE Scrutiny Score</b> measures what fraction of a contract's value was terminated by the Department of Government Efficiency (DOGE). A score of 1.0 means the entire contract was cut. Contracts with scrutiny >= 0.7 are flagged as 'High scrutiny'." };
    }
    if (intent.dimension === "transparency") {
      return { actions: [], responseText: "<b>Transparency Score</b> (0-1) estimates how clear a contract description is. It combines description length, jargon penalty, and specificity bonus (numbers/dates). Lower scores indicate vague descriptions with no measurable deliverables." };
    }
    if (intent.dimension === "impact") {
      return { actions: [], responseText: "<b>Citizen Impact Score</b> is a composite of: 30% news popularity (GDELT), 30% DOGE scrutiny, 20% inverse transparency (opaque = higher impact), and 20% log-normalized contract value." };
    }
  }

  // Count operation
  if (intent.operation === "count") {
    if (intent.dimension === "savings") {
      return { actions: [], responseText: `Total claimed savings across all ${stats.total_contracts.toLocaleString()} tracked contracts: <b>${formatMoney(stats.total_savings)}</b>.\n\nNote: these are DOGE's claimed figures. Actual savings may differ.` };
    }
    return { actions: [], responseText: `We're tracking <b>${stats.total_contracts.toLocaleString()}</b> contracts, grants, and leases worth ${formatMoney(stats.total_value)} in total value.` };
  }

  // Define operation on a non-dimension term (e.g., "what is usaspending")
  if (intent.operation === "define" && !intent.dimension && !intent.topic && intent.entities.length === 0) {
    // Check for known terms
    const termDefs = {
      usaspending: "<b>USAspending.gov</b> is the official federal spending database maintained by the U.S. Treasury. Civic Lenses pulls agency budget data (obligated and outlay amounts) and contract award records from its API.",
      gdelt: "<b>GDELT</b> (Global Database of Events, Language, and Tone) indexes news articles worldwide. We use it to measure how much media coverage each spending topic receives, creating a recency-weighted popularity score.",
      "sam.gov": "<b>SAM.gov</b> is the federal procurement portal where agencies post contract opportunities. We pull active opportunities and entity registrations via its API.",
      "doge.gov": "<b>DOGE.gov</b> publishes contracts, grants, and leases that the Department of Government Efficiency has terminated or flagged, including the original value and claimed savings.",
      "civic lenses": "<b>Civic Lenses</b> unifies data from DOGE.gov, USAspending, GDELT, and SAM.gov into a personalized dashboard. It recommends contracts worth your attention based on your topic preferences and location.",
    };
    for (const [term, def] of Object.entries(termDefs)) {
      if (lower.includes(term)) return { actions: [], responseText: def };
    }
  }

  // Dimension definition without explicit "define" operation
  if (intent.dimension && !intent.operation) {
    if (intent.dimension === "scrutiny") {
      return { actions: [], responseText: "<b>DOGE Scrutiny Score</b> measures what fraction of a contract's value was terminated by DOGE. A score of 1.0 means the entire contract was cut. Contracts >= 0.7 are 'High scrutiny'." };
    }
    if (intent.dimension === "transparency") {
      return { actions: [], responseText: "<b>Transparency Score</b> (0-1) estimates description clarity. Combines length, jargon penalty, and specificity bonus. Lower = vaguer." };
    }
    if (intent.dimension === "savings") {
      return { actions: [], responseText: `Total claimed savings: <b>${formatMoney(stats.total_savings)}</b> across ${stats.total_contracts.toLocaleString()} items. Note: these are DOGE's claimed figures.` };
    }
    if (intent.dimension === "value") {
      return { actions: [], responseText: `Total contract value tracked: <b>${formatMoney(stats.total_value)}</b> across ${stats.total_contracts.toLocaleString()} contracts, grants, and leases.` };
    }
  }

  // Single state abbreviation with no operation (e.g., just "TX")
  if (intent.entities.length === 1 && !intent.operation && !intent.topic) {
    const abbr = intent.entities[0].value;
    const sd = stats.states[abbr];
    if (sd) {
      actions.push({ tool: "highlight_chart", args: ["states", abbr] });
      const st = stats.state_topics?.[abbr] || {};
      const topTopics = Object.entries(st).sort((a, b) => b[1] - a[1]).slice(0, 3);
      let text = `<b>${abbr}</b>: ${sd.count} contracts, ${formatMoney(sd.value)} value, ${formatMoney(sd.savings)} savings.`;
      if (topTopics.length) text += "\n\nTop topics: " + topTopics.map(([t, c]) => `${TOPIC_LABELS[t] || t} (${c})`).join(", ");
      return { actions, responseText: text };
    }
  }

  // No structured match: generic helpful response
  return {
    actions: [],
    responseText: "I'm not sure about that. Try asking about a <b>state</b> (e.g., \"Texas\"), a <b>topic</b> (e.g., \"healthcare\"), or a <b>term</b> (e.g., \"what is scrutiny\"). Type <b>help</b> for more ideas.",
  };
}

// -- Markdown rendering --

function renderMarkdown(text) {
  if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
    marked.use({ gfm: true, breaks: true });
    return DOMPurify.sanitize(marked.parse(text));
  }
  return esc(text);
}

// -- Floating particle effects --

function spawnParticles(type, count = 3) {
  // Find the VISIBLE owl scene (basic or enhanced)
  const scene = document.querySelector(".owl-scene:not([style*='display: none'])") ||
                document.querySelector(".owl-scene");
  if (!scene) return;
  const rect = scene.getBoundingClientRect();
  // Skip if element is hidden (rect is 0,0)
  if (rect.width === 0 && rect.height === 0) return;
  const symbols = { think: "?", money: "$", spark: "\u2728", dream: "\u00B7", wake: "\u2606" };
  const char = symbols[type] || "?";
  for (let i = 0; i < count; i++) {
    const p = document.createElement("span");
    p.className = "owl-particle";
    p.textContent = char;
    p.style.left = (rect.left + 20 + Math.random() * 40) + "px";
    p.style.top = (rect.top + 10 + Math.random() * 20) + "px";
    p.style.animationDelay = (i * 0.3) + "s";
    document.body.appendChild(p);
    setTimeout(() => p.remove(), 2000);
  }
}

// -- Data context builder (compact summary for LFM2) --

function buildDataContext() {
  if (!appData) return "";
  const stats = appData.stats;

  const topStates = Object.entries(stats.states)
    .sort((a, b) => b[1].value - a[1].value)
    .slice(0, 10)
    .map(([s, d]) => `${s}: ${d.count} contracts, ${formatMoney(d.value)} value, ${formatMoney(d.savings)} savings`)
    .join(". ");

  const topAgencies = Object.entries(stats.agencies)
    .sort((a, b) => b[1].value - a[1].value)
    .slice(0, 8)
    .map(([a, d]) => `${a.replace(/^Department of (the )?/i, "")}: ${formatMoney(d.value)}, ${d.count} contracts`)
    .join(". ");

  const topics = Object.entries(stats.topics)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([t, c]) => `${TOPIC_LABELS[t] || t}: ${c.toLocaleString()}`)
    .join(", ");

  const timeline = Object.entries(stats.timeline || {})
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([m, d]) => `${m}: ${formatMoney(d.savings)}`)
    .join(", ");

  const userState = resolveUserState();
  let userContext = "";
  if (userState && stats.states[userState]) {
    const sd = stats.states[userState];
    const st = stats.state_topics?.[userState] || {};
    const topT = Object.entries(st).sort((a, b) => b[1] - a[1]).slice(0, 3);
    userContext = `User's state: ${userState} (${sd.count} contracts, ${formatMoney(sd.value)} value, ${formatMoney(sd.savings)} savings. Top topics: ${topT.map(([t, c]) => `${TOPIC_LABELS[t] || t} (${c})`).join(", ")}).`;
  }

  return [
    `Dashboard: ${stats.total_contracts.toLocaleString()} contracts, ${formatMoney(stats.total_value)} total value, ${formatMoney(stats.total_savings)} claimed savings, ${stats.flagged} high scrutiny.`,
    `Top states: ${topStates}.`,
    `Top agencies: ${topAgencies}.`,
    `Topics: ${topics}.`,
    `Monthly savings: ${timeline}.`,
    userContext,
    `Terms: scrutiny = fraction of contract value DOGE cut. transparency = description clarity (0-1). citizen impact = composite of news + scrutiny + transparency + value.`,
    `Sources: DOGE.gov (cuts), USAspending.gov (awards), GDELT (news), SAM.gov (opportunities).`,
  ].filter(Boolean).join("\n");
}

let cachedDataContext = "";

// -- Conversation history (for multi-turn) --
let chatHistory = [];

// -- Unified chat handler --

async function handleChat(question) {
  try {
    // 1. Regex for tool calls only (dashboard actions)
    const intent = extractIntentLocal(question);
    const { actions } = processIntent(intent, question);

    // 2. Execute tools
    let toolNote = null;
    // Store on module for sendMessage to read
    handleChat._lastToolNote = null;
    if (actions.length > 0) {
      const actionNarrations = {
        filter_topics: (args) => `filtered to ${(args[0] || []).map(t => TOPIC_LABELS[t] || t).join(", ")}`,
        set_location: (args) => `set location to ${args[0]}`,
        highlight_chart: (args) => `highlighted ${args[1] || args[0]} on the chart`,
        switch_tab: (args) => `switched to ${args[0]} view`,
        scroll_to: () => `scrolled the dashboard`,
      };

      const narrations = [];
      for (let i = 0; i < actions.length; i++) {
        const action = actions[i];
        const toolFn = DASHBOARD_TOOLS[action.tool];
        if (toolFn) {
          if (i > 0) await new Promise(r => setTimeout(r, 200));
          toolFn(...action.args);
          spawnParticles("spark", 3);
          const narrate = actionNarrations[action.tool];
          if (narrate) narrations.push(narrate(action.args));
        }
      }
      render();
      if (narrations.length > 0) {
        const scrollAction = actions.find(a => a.tool === "scroll_to");
        const highlightAction = actions.find(a => a.tool === "highlight_chart");
        const scrollTarget = scrollAction ? scrollAction.args[0] : (highlightAction ? `chart-${highlightAction.args[0]}` : "");
        const argsDetail = actions.map(a => `${a.tool}(${JSON.stringify(a.args)})`).join("\n");
        const replayActions = actions.map(a => ({ ...a }));
        toolNote = { html: `<span class="action-icon">\u2728</span> ${narrations.join(" and ")}`, scrollTarget, argsDetail, replayActions };
        handleChat._lastToolNote = toolNote;
      }
    }

    // 3. Build messages for model response
    if (!cachedDataContext) cachedDataContext = buildDataContext();

    // Build dynamic context: what the dashboard is showing NOW after tool execution
    const { responseText } = processIntent(intent, question);
    const groundedFacts = responseText ? responseText.replace(/<[^>]+>/g, "").trim() : "";

    // Current feed state
    const currentContracts = getFilteredContracts();
    const currentTopics = [...selectedTopics].map(t => TOPIC_LABELS[t] || t).join(", ");
    const currentState = `Currently showing: ${currentTopics} (${currentContracts.length} contracts).`;

    chatHistory.push({ role: "user", content: question });
    if (chatHistory.length > 12) chatHistory = chatHistory.slice(-12);

    const systemPrompt = `You are a friendly owl assistant on Civic Lenses, a federal spending dashboard. Answer using ONLY the data provided. 1-3 sentences.\n\n${cachedDataContext}\n\n${currentState}${groundedFacts ? `\n\nRetrieved facts for this question:\n${groundedFacts}` : ""}`;
    const messages = [
      { role: "system", content: systemPrompt },
      ...chatHistory,
    ];

    // 3a. GPT-4o via GitHub Models (authenticated, streaming)
    const storedAuth = getStoredAuth();
    if (currentUser && storedAuth?.token) {
      try {
        const resp = await fetch("https://models.inference.ai.azure.com/chat/completions", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${storedAuth.token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model: "gpt-4o",
            messages,
            max_tokens: 200,
            stream: true,
          }),
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        // Parse SSE stream
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let full = "";
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6).trim();
            if (data === "[DONE]") break;
            try {
              const chunk = JSON.parse(data);
              const delta = chunk.choices?.[0]?.delta?.content;
              if (delta) {
                full += delta;
                if (handleChat._onToken) handleChat._onToken(full);
              }
            } catch {}
          }
        }

        if (full.length > 2) {
          chatHistory.push({ role: "assistant", content: full });
          return null; // already streamed
        }
      } catch (e) {
        console.warn("[owl] GPT-4o stream error, falling back:", e);
      }
    }

    // 3b. LFM2 local model (streaming via onChunk)
    if (lfm2Pipeline) {
      let full = "";
      const response = await lfm2Pipeline.chat(messages, {
        maxNewTokens: 100,
        onChunk: (delta) => {
          full += delta;
          if (handleChat._onToken) handleChat._onToken(full);
        },
      });
      const finalText = full || response;
      console.log("[owl] LFM2:", finalText);

      if (finalText && finalText.length > 5 && finalText.length < 500) {
        chatHistory.push({ role: "assistant", content: finalText });
        if (full) return null; // already streamed
        return esc(finalText);
      }
    }

    // Model not loaded
    const excuses = [
      "* yawn * Still waking up... give me a moment.",
      "Hold on, brewing my coffee...",
      "* stretches wings * Almost ready...",
      "Am I hallucinating or is my brain not loaded yet?",
    ];
    return excuses[Math.floor(Math.random() * excuses.length)];
  } catch (e) {
    console.error("[owl] error:", e);
    return "* rubs eyes * Something went wrong. Try again?";
  }
}

// -- Original keyword-based answerer (fallback) --

function answerQuestion(q) {
  if (!appData) return "Still loading data. Try again in a moment.";
  const lower = q.toLowerCase();
  const stats = appData.stats;

  // State queries
  if (lower.includes("which state") || lower.includes("most cuts") || lower.includes("top state") || lower.includes("most affected state")) {
    const top5 = Object.entries(stats.states)
      .sort((a, b) => b[1].savings - a[1].savings)
      .slice(0, 5);
    return `Top 5 states by claimed savings:\n${top5.map(([s, d], i) => `${i+1}. <b>${s}</b>: ${formatMoney(d.savings)} savings (${d.count} contracts)`).join("\n")}`;
  }

  // Topic queries
  for (const [key, label] of Object.entries(TOPIC_LABELS)) {
    if (lower.includes(key) || lower.includes(label.toLowerCase())) {
      const count = stats.topics[key] || 0;
      const recs = appData.recommendations[key] || [];
      const topContract = recs[0];
      let answer = `<b>${label}</b>: ${count.toLocaleString()} contracts in the dataset.`;
      if (topContract) {
        answer += `\n\nTop recommendation: "${esc(topContract.description.substring(0, 80))}..." (${formatMoney(topContract.value)}, ${topContract.agency})`;
      }
      return answer;
    }
  }

  // Specific state
  for (const [name, abbr] of Object.entries(STATE_NAMES_TO_ABBREV)) {
    if (lower.includes(name) || lower === abbr.toLowerCase()) {
      const sd = stats.states[abbr.toUpperCase()];
      if (sd) {
        const st = stats.state_topics?.[abbr.toUpperCase()] || {};
        const topTopics = Object.entries(st).sort((a, b) => b[1] - a[1]).slice(0, 3);
        return `<b>${abbr.toUpperCase()}</b>: ${sd.count} contracts, ${formatMoney(sd.value)} total value, ${formatMoney(sd.savings)} claimed savings.${topTopics.length ? "\n\nTop topics: " + topTopics.map(([t,c]) => `${TOPIC_LABELS[t] || t} (${c})`).join(", ") : ""}`;
      }
      return `No data found for ${abbr.toUpperCase()}.`;
    }
  }

  // Definitions
  if (lower.includes("scrutiny") || lower.includes("doge")) {
    return "<b>DOGE Scrutiny Score</b> measures what fraction of a contract's value was terminated by the Department of Government Efficiency (DOGE). A score of 1.0 means the entire contract was cut. Contracts with scrutiny >= 0.7 are flagged as 'High scrutiny'.";
  }
  if (lower.includes("transparency")) {
    return "<b>Transparency Score</b> (0-1) estimates how clear a contract description is. It combines description length, jargon penalty, and specificity bonus (numbers/dates). Lower scores indicate vague descriptions with no measurable deliverables.";
  }
  if (lower.includes("citizen impact") || lower.includes("impact score")) {
    return "<b>Citizen Impact Score</b> is a composite of: 30% news popularity (GDELT), 30% DOGE scrutiny, 20% inverse transparency (opaque = higher impact), and 20% log-normalized contract value.";
  }
  if (lower.includes("savings") || lower.includes("how much")) {
    return `Total claimed savings across all ${stats.total_contracts.toLocaleString()} tracked contracts: <b>${formatMoney(stats.total_savings)}</b>.\n\nNote: these are DOGE's claimed figures. Actual savings may differ.`;
  }
  if (lower.includes("how many") || lower.includes("total contracts")) {
    return `We're tracking <b>${stats.total_contracts.toLocaleString()}</b> contracts, grants, and leases worth ${formatMoney(stats.total_value)} in total value.`;
  }
  if (lower.includes("help") || lower.includes("what can")) {
    return "I can answer questions about the federal spending data. Try:\n\n• \"Which state has the most cuts?\"\n• \"Tell me about healthcare\"\n• \"What is DOGE scrutiny?\"\n• \"How much has been saved?\"\n• \"Tell me about North Carolina\"\n• \"What is transparency score?\"";
  }

  return "I'm not sure about that. Try asking about a specific state, topic, or term like 'scrutiny', 'transparency', or 'savings'. Type <b>help</b> for a list of things I can answer.";
}

function initOwlEyes() {
  document.addEventListener("mousemove", (e) => {
    const widget = document.getElementById("owl-widget");
    if (!widget || !widget.classList.contains("owl-awake")) return;
    // Find the currently visible owl scene
    const owl = currentUser
      ? document.getElementById("owl-trigger-enhanced")
      : document.getElementById("owl-trigger");
    if (!owl) return;
    const pupils = owl.querySelectorAll(".owl-pupil");
    if (!pupils.length) return;
    const rect = owl.getBoundingClientRect();
    const eyeX = rect.left + rect.width * 0.47;
    const eyeY = rect.top + rect.height * 0.36;
    const dx = e.clientX - eyeX;
    const dy = e.clientY - eyeY;
    const angle = Math.atan2(dy, dx);
    const dist = Math.min(Math.hypot(dx, dy) / 200, 1);
    const maxShift = 1.5;
    const offsetX = Math.cos(angle) * maxShift * dist;
    const offsetY = Math.sin(angle) * maxShift * dist;
    pupils.forEach(p => {
      p.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
    });
  });
}

function initChat() {
  const owlBasic = document.getElementById("owl-trigger");
  const owlEnhanced = document.getElementById("owl-trigger-enhanced");
  const input = document.getElementById("chat-input");
  const send = document.getElementById("chat-send");
  const messages = document.getElementById("chat-messages");
  const widget = document.getElementById("owl-widget");

  // Rotating idle thoughts (data-driven, shown while sleeping/idle)
  function getIdleThoughts() {
    if (!appData) return ["Click me to explore federal spending."];
    const stats = appData.stats;
    const topState = Object.entries(stats.states).sort((a, b) => b[1].value - a[1].value)[0];
    const topAgency = Object.entries(stats.agencies).sort((a, b) => b[1].value - a[1].value)[0];
    const userState = resolveUserState();
    const userStatData = userState ? stats.states[userState] : null;
    const isSignedIn = !!currentUser;
    const hasLocation = !!userState;
    const selectedCount = selectedTopics.size;

    const thoughts = [
      `${stats.total_contracts.toLocaleString()} contracts tracked. Click me to explore.`,
      `${formatMoney(stats.total_savings)} in claimed savings. Where did it go?`,
      topState ? `${topState[0]} leads with ${formatMoney(topState[1].value)} in contracts.` : null,
      topAgency ? `${topAgency[0].replace(/^Department of /, "")}: ${formatMoney(topAgency[1].value)} in spending.` : null,

      // Location-aware
      !hasLocation ? `Set your location. I'll show what affects your state.` : null,
      !hasLocation ? `${Object.keys(stats.states).length} states in the data. Where's yours?` : null,
      userStatData ? `${userState}: ${userStatData.count} contracts, ${formatMoney(userStatData.savings)} in cuts.` : null,
      userStatData ? `Watching ${userState} for you. Ask me what's changed.` : null,

      // Auth-aware
      !isSignedIn ? `Sign in to wake up my smarter side.` : null,
      isSignedIn ? `Welcome back, ${currentUser.login}. What should we look into?` : null,

      // Topic-aware
      selectedCount === 1 ? `Focused on ${TOPIC_LABELS[[...selectedTopics][0]] || [...selectedTopics][0]}. Try adding more topics.` : null,
      selectedCount >= 3 ? `Tracking ${selectedCount} topics. Ask me to compare them.` : null,

      // Engagement
      `Try asking me: "Compare NC and VA"`,
      `Try: "What's the savings trend?"`,
      `The owl sees all. Click to ask me anything.`,
    ];

    return thoughts.filter(Boolean);
  }

  let idleInterval = null;

  function stopIdleThoughts() {
    if (idleInterval) { clearInterval(idleInterval); idleInterval = null; }
  }

  function startIdleThoughts() {
    const idle = document.getElementById("owl-balloon-idle");
    if (!idle) return;
    const widget = document.getElementById("owl-widget");

    let thoughts = getIdleThoughts();
    let idx = Math.floor(Math.random() * thoughts.length);
    idle.textContent = thoughts[idx] || "";

    stopIdleThoughts();
    idleInterval = setInterval(() => {
      // Don't update during waking (dreams handle that)
      if (widget && (widget.classList.contains("owl-waking") || widget.classList.contains("owl-sleeping"))) return;
      thoughts = getIdleThoughts();
      idx = (idx + 1) % thoughts.length;
      idle.style.opacity = 0;
      setTimeout(() => {
        idle.textContent = thoughts[idx];
        idle.style.opacity = 1;
      }, 350);
    }, 9000);
  }

  // ── Interaction tracker (session-only, for contextual prompts) ──
  const interactionLog = { topics: {}, states: {}, charts: {}, tabs: {} };

  function trackInteraction(type, value) {
    if (!interactionLog[type]) interactionLog[type] = {};
    interactionLog[type][value] = (interactionLog[type][value] || 0) + 1;
  }

  function getContextualPrompts() {
    const prompts = [];
    const stats = appData?.stats;
    if (!stats) return ["Which state has the most cuts?", "What is DOGE scrutiny?", "Show me healthcare"];

    // Based on most-interacted topics
    const topTopics = Object.entries(interactionLog.topics).sort((a, b) => b[1] - a[1]);
    if (topTopics.length > 0) {
      const t = topTopics[0][0];
      prompts.push(`Tell me more about ${TOPIC_LABELS[t] || t}`);
    }

    // Based on user's state
    const userState = resolveUserState();
    if (userState && stats.states[userState]) {
      prompts.push(`What's happening in ${userState}?`);
    }

    // Based on which charts they hovered
    if (interactionLog.charts["states"]) prompts.push("Which state has the most cuts?");
    if (interactionLog.charts["agencies"]) prompts.push("Top agencies by spending");
    if (interactionLog.charts["timeline"]) prompts.push("What's the savings trend?");

    // Based on active tab
    if (activeTab === "high-value") prompts.push("Show me the biggest contracts");
    if (activeTab === "just-cut") prompts.push("What was cut most recently?");

    // Fill remaining with defaults
    const defaults = [
      "Compare NC and VA",
      "Show me defense contracts",
      "What is DOGE scrutiny?",
      "Which state has the most cuts?",
      "What's trending?",
    ];
    for (const d of defaults) {
      if (prompts.length >= 4) break;
      if (!prompts.includes(d)) prompts.push(d);
    }

    return prompts.slice(0, 4);
  }

  function renderPromptChips(container) {
    const prompts = getContextualPrompts();
    const chipsHTML = prompts.map(p =>
      `<button class="prompt-chip" data-prompt="${esc(p)}">${esc(p)}</button>`
    ).join("");
    container.innerHTML += `<div class="prompt-chips">${chipsHTML}</div>`;

    container.querySelectorAll(".prompt-chip").forEach(chip => {
      chip.addEventListener("click", (e) => {
        e.stopPropagation();
        input.value = chip.dataset.prompt;
        sendMessage();
      });
    });
  }

  // Track chart hovers
  setTimeout(() => {
    ["states", "topics", "timeline", "agencies"].forEach(id => {
      const el = document.getElementById(`chart-${id}`);
      if (el) el.addEventListener("mouseenter", () => trackInteraction("charts", id));
    });
  }, 2000);

  function getDreams() {
    if (!appData) return ["Dreaming of contracts..."];
    const stats = appData.stats;
    const topState = Object.entries(stats.states).sort((a, b) => b[1].savings - a[1].savings)[0];
    const topAgency = Object.entries(stats.agencies).sort((a, b) => b[1].value - a[1].value)[0];
    const dreams = [
      "zzZ... dreaming of spreadsheets...",
      `*mumbles* ...${formatMoney(stats.total_savings)} in savings...`,
      topState ? `...${topState[0]}... so many contracts there...` : null,
      "...who approved this $12.5B contract...",
      topAgency ? `...${topAgency[0].replace(/^Department of /, "")}... what are they spending on...` : null,
      `...${stats.total_contracts.toLocaleString()} contracts... can't count them all...`,
      "...transparency score... too low... must investigate...",
      "*snore* ...DOGE... scissors... cutting everything...",
      "...why is this description so vague...",
      "* yawn * ...waking up...",
      "Adjusting lenses...",
      "I see the data now...",
    ];
    return dreams.filter(Boolean);
  }

  function setEyelids(progress) {
    // Map 0-1 progress to eyelid height: 12 (closed) to 0 (open)
    const height = Math.max(0, 12 * (1 - progress));
    document.querySelectorAll(".owl-lid").forEach(lid => {
      lid.setAttribute("height", height.toFixed(1));
    });
  }

  function getDreamForProgress(progress) {
    if (progress < 0.12) return "zzZ... dreaming of spreadsheets...";
    if (progress < 0.24) return "*mumbles* ...so many contracts...";
    if (progress < 0.36) return "...$100 trillion in savings... wait, am I hallucinating?";
    if (progress < 0.48) return "*snore* ...DOGE... scissors... cutting...";
    if (progress < 0.58) return "...mmm... need coffee to stop hallucinating...";
    if (progress < 0.68) return "...* sip *... neurons connecting...";
    if (progress < 0.78) return "...loading 350 million parameters...";
    if (progress < 0.88) return "...almost there... grounding to real data...";
    if (progress < 0.95) return "...eyes... focusing on facts only...";
    return "* blink blink * ...I see data! Real data.";
  }

  async function wakeOwl() {
    widget.classList.remove("owl-sleeping");
    widget.classList.add("owl-waking");

    const idle = document.getElementById("owl-balloon-idle");
    let lastDream = "";

    const useGPT4o = !!(currentUser && getStoredAuth()?.token);

    // Eyelids track loading progress
    setEyelids(0);
    idle.style.opacity = 1;

    if (useGPT4o) {
      // Authenticated: skip LFM2, fast wake with GPT-4o
      idle.textContent = "Adjusting lenses...";
      setEyelids(0.5);
      await new Promise(r => setTimeout(r, 600));
      idle.style.opacity = 0;
      await new Promise(r => setTimeout(r, 200));
      idle.textContent = "* blink * GPT-4o ready!";
      setEyelids(1);
      spawnParticles("wake", 5);
      idle.style.opacity = 1;
    } else {
      // Unauthenticated: load LFM2 with dream sequence
      const allDreams = [
        "zzZ... dreaming of spreadsheets...",
        "*mumbles* ...so many contracts...",
        "...$100 trillion in savings... am I hallucinating?",
        "*snore* ...DOGE... scissors... cutting...",
        "...need coffee to stop hallucinating...",
        "...* sip *... neurons connecting...",
        "...loading 350 million parameters...",
        "...grounding to real data...",
        "...who approved this contract...",
        "...transparency score... too low...",
        "...mmm... the data is calling...",
        "...just five more minutes...",
      ];
      // Shuffle so each wake shows different dreams
      const dreams = allDreams.sort(() => Math.random() - 0.5);
      // Always end with a waking-up dream
      dreams.push("...eyes... focusing on facts only...");

      const dots = document.querySelectorAll("#thought-dots .thought-dot");
      let dreamIdx = 0;

      async function showDream(text) {
        // Fade out bubble
        idle.style.opacity = 0;

        // Animate dots bottom to top
        dots.forEach(d => { d.style.opacity = 0; d.style.transform = "scale(0)"; });
        for (let i = dots.length - 1; i >= 0; i--) {
          await new Promise(r => setTimeout(r, 180));
          dots[i].style.transition = "opacity 0.2s, transform 0.2s";
          dots[i].style.opacity = 1;
          dots[i].style.transform = "scale(1)";
        }

        // Show bubble with new text
        await new Promise(r => setTimeout(r, 200));
        idle.textContent = text;
        idle.style.opacity = 1;
        spawnParticles("dream", 2);

        // Open eyelids gradually
        setEyelids(Math.min((dreamIdx + 1) / dreams.length, 0.9));
      }

      // Show first dream
      idle.textContent = dreams[0];
      idle.style.opacity = 1;
      setEyelids(0);

      // Cycle dreams on a timer
      const dreamInterval = setInterval(() => {
        dreamIdx = Math.min(dreamIdx + 1, dreams.length - 1);
        showDream(dreams[dreamIdx]);
      }, 3500);

      // Load model in parallel
      const modelPromise = loadLFM2();
      const minWake = new Promise(r => setTimeout(r, 4000));
      await Promise.all([minWake, modelPromise]);

      clearInterval(dreamInterval);
      setEyelids(1);

      idle.style.opacity = 0;
      await new Promise(r => setTimeout(r, 250));
      idle.textContent = lfm2Pipeline ? "* blink * Ready to talk!" : "* stretches * I'm awake!";
      spawnParticles("wake", 5);
      idle.style.opacity = 1;
    }

    widget.classList.remove("owl-waking");
    widget.classList.add("owl-awake");

    // Brief pause, then open chat
    await new Promise(r => setTimeout(r, 800));

    const authHint = currentUser
      ? ""
      : `<br><br><a class="chat-link" id="chat-signin">Sign in with GitHub</a> to upgrade my brain (GPT-4o).`;

    messages.innerHTML = `<div class="chat-msg chat-bot">I can help you explore federal spending data. Ask me anything, or try one of these:</div>`;
    renderPromptChips(messages);


    widget.classList.add("chat-open");
    input.focus();

    // Now that the owl is awake, start context-aware idle thoughts
    startIdleThoughts();
  }

  // Toggle chat balloon on owl click (bind both variants)
  function handleOwlClick(e) {
    e.stopPropagation();

    // Sleeping: trigger wake sequence
    if (widget.classList.contains("owl-sleeping")) {
      wakeOwl();
      return;
    }

    // Waking: ignore clicks during animation
    if (widget.classList.contains("owl-waking")) return;

    // Awake: toggle chat as before
    widget.classList.toggle("chat-open");
    if (widget.classList.contains("chat-open")) input.focus();
  }
  owlBasic.addEventListener("click", handleOwlClick);
  owlEnhanced.addEventListener("click", handleOwlClick);

  // Close when clicking outside
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".owl-widget")) {
      widget.classList.remove("chat-open");
    }
  });

  async function sendMessage() {
    const q = input.value.trim();
    if (!q) return;

    const userMsg = document.createElement("div");
    userMsg.className = "chat-msg chat-user";
    userMsg.textContent = q;
    messages.appendChild(userMsg);
    input.value = "";

    // Create bot message that will be updated during streaming
    const botMsg = document.createElement("div");
    botMsg.className = "chat-msg chat-bot";
    botMsg.innerHTML = `<span class="chat-spinner"><span></span><span></span><span></span></span>`;
    messages.appendChild(botMsg);
    messages.scrollTop = messages.scrollHeight;
    spawnParticles("think", 4);

    // Set up streaming callback
    let streaming = false;
    handleChat._onToken = (text) => {
      streaming = true;
      botMsg.innerHTML = renderMarkdown(text);
      messages.scrollTop = messages.scrollHeight;
    };

    let answer;
    try {
      answer = await handleChat(q);
    } catch (e) {
      console.error("[owl] handleChat error:", e);
      answer = "Something went wrong. Try a different question.";
    }

    handleChat._onToken = null;

    // If not streamed (excuses, errors), set the content now
    if (answer !== null) {
      botMsg.innerHTML = renderMarkdown(answer);
    }

    // Append action note if tools were executed
    const tn = handleChat._lastToolNote;
    if (tn) {
      const noteEl = document.createElement("div");
      noteEl.className = "owl-action-note";
      noteEl.innerHTML = tn.html;
      if (tn.argsDetail) {
        noteEl.title = tn.argsDetail;
      }
      noteEl.style.cursor = "pointer";
      noteEl.addEventListener("click", () => {
        // Replay all tool calls
        if (tn.replayActions) {
          tn.replayActions.forEach(action => {
            const toolFn = DASHBOARD_TOOLS[action.tool];
            if (toolFn) {
              toolFn(...action.args);
              spawnParticles("spark", 2);
            }
          });
          render();
        }
      });
      botMsg.appendChild(noteEl);
      handleChat._lastToolNote = null;
    }
    messages.scrollTop = messages.scrollHeight;
  }

  send.addEventListener("click", (e) => { e.stopPropagation(); sendMessage(); });
  input.addEventListener("click", (e) => e.stopPropagation());
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });

  // Start rotating data-driven thoughts after 3s
  // Idle thoughts only start after owl is awake (not while sleeping)
  // startIdleThoughts() is called after wakeOwl completes
}

// ── Init ──────────────────────────────────────────────────────

restoreAuth();

fetch("data.json")
  .then(r => r.json())
  .then(data => {
    appData = data;
    // Load saved anonymous topics if no user
    if (!currentUser) {
      try {
        const saved = localStorage.getItem("civic-topics-anon");
        if (saved) selectedTopics = new Set(JSON.parse(saved));
      } catch {}
    }
    autoSelectTopicsFromState();
    buildSidebar();
    buildMobileTopics();
    setupTabs();
    render();
    initCharts();
    updateAuthUI();
    initLocation();
    initChat();
    initOwlEyes();
  })
  .catch(err => {
    document.getElementById("cards-grid").innerHTML =
      `<div class="info-banner">
        <div class="info-icon">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="9" r="7.5" stroke="#fff" stroke-width="1.5"/>
            <line x1="9" y1="5.5" x2="9" y2="9.5" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="9" cy="12.5" r="0.8" fill="#fff"/>
          </svg>
        </div>
        <div class="info-text"><strong>Could not load contract data.</strong> ${err.message}</div>
      </div>`;
  });
