// AI-assisted (Claude Code, claude.ai) — https://claude.ai

import { connectGitHub, verifyToken } from "https://neevs.io/auth/lib.js";

let appData = null;
let selectedTopics = new Set(["healthcare", "education", "defense"]);
let activeTab = "scrutiny";
let currentUser = null;

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
  technology: "Technology",
  energy: "Energy",
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

function renderCard(contract) {
  const s = scrutinyLevel(contract.scrutiny);
  const flagsHTML = (contract.flags || [])
    .map(f => `<span class="flag ${flagClass(f)}">${flagLabel(f)}</span>`)
    .join("");

  return `
    <div class="contract-card">
      <div class="card-header">
        <span class="agency-tag">${contract.agency}</span>
        <span class="scrutiny-badge ${s.cls}">
          <span class="dot"></span>
          ${s.label}
        </span>
      </div>
      <div class="card-title">${contract.description}</div>
      <div class="card-meta">
        <span class="meta-item meta-amount">${formatMoney(contract.value)}</span>
        <span class="meta-sep"></span>
        <span class="meta-item">${contract.vendor}</span>
        <span class="meta-sep"></span>
        <span class="meta-item">${TOPIC_LABELS[contract.topic] || contract.topic}</span>
      </div>
      ${flagsHTML ? `<div class="card-flags">${flagsHTML}</div>` : ""}
      ${contract.reason ? `<div class="card-reason">${contract.reason}</div>` : ""}
      <div class="card-actions">
        <button class="action-btn primary" onclick="alert('Contract: ${contract.contract_id}\\nValue: ${formatMoney(contract.value)}\\nSavings: ${formatMoney(contract.savings)}\\nScrutiny: ${(contract.scrutiny * 100).toFixed(0)}%')">Details</button>
      </div>
    </div>`;
}

function getFilteredContracts() {
  if (!appData) return [];
  let contracts = [];
  for (const topic of selectedTopics) {
    const recs = appData.recommendations[topic] || [];
    contracts.push(...recs);
  }
  // Deduplicate by contract_id
  const seen = new Set();
  contracts = contracts.filter(c => {
    if (seen.has(c.contract_id)) return false;
    seen.add(c.contract_id);
    return true;
  });
  return contracts;
}

function filterByTab(contracts) {
  if (activeTab === "scrutiny") {
    return contracts
      .filter(c => c.scrutiny >= 0.3)
      .sort((a, b) => b.scrutiny - a.scrutiny);
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

function render() {
  if (!appData) return;

  const all = getFilteredContracts();
  const filtered = filterByTab(all);

  // Stats
  const totalValue = all.reduce((s, c) => s + c.value, 0);
  const flaggedCount = all.filter(c => c.scrutiny >= 0.7).length;
  document.getElementById("stat-value").textContent = formatMoney(totalValue);
  document.getElementById("stat-flagged").textContent = flaggedCount;
  document.getElementById("feed-badge").textContent = all.length;

  // Tab counts
  document.getElementById("tab-scrutiny-count").textContent =
    all.filter(c => c.scrutiny >= 0.3).length;
  document.getElementById("tab-value-count").textContent =
    all.filter(c => c.value >= 1e6).length;
  document.getElementById("tab-cut-count").textContent =
    all.filter(c => c.savings > 0).length;

  // Section label
  const tabLabels = {
    scrutiny: "Under scrutiny",
    "high-value": "High value",
    "just-cut": "Recently cut",
  };
  document.getElementById("feed-section-label").textContent =
    `${tabLabels[activeTab]} \u00B7 ${filtered.length} contracts`;

  // Cards
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
  grid.innerHTML = filtered.slice(0, 20).map(renderCard).join("");

  // Sidebar selected topics
  document.getElementById("sidebar-selected-topics").innerHTML =
    [...selectedTopics]
      .map(t => `<span class="sidebar-topic">${TOPIC_LABELS[t] || t}</span>`)
      .join("");
}

function buildSidebar() {
  const container = document.getElementById("sidebar-categories");
  const topics = appData.topics;
  container.innerHTML = topics
    .map(t => {
      const active = selectedTopics.has(t) ? " active" : "";
      const label = TOPIC_LABELS[t] || t;
      const count = appData.stats.topics[t] || 0;
      return `
        <li class="sidebar-nav-item${active}" data-topic="${t}">
          <span style="width:20px;text-align:center;font-size:13px;opacity:0.7">${count > 999 ? (count / 1000).toFixed(0) + "k" : count}</span>
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
      if (currentUser) saveTopics(currentUser.login);
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
      render();
    });
  });
}

// Mobile bottom nav
document.querySelectorAll(".nav-item").forEach(item => {
  item.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(i => i.classList.remove("active"));
    item.classList.add("active");
  });
});

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

async function requestLocation() {
  // Try browser geolocation first
  if (navigator.geolocation) {
    setLocationDisplay("Locating...");
    try {
      const pos = await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000 });
      });
      const name = await reverseGeocode(pos.coords.latitude, pos.coords.longitude);
      if (name) {
        saveLocation(name);
        return;
      }
    } catch {}
  }
  // Fallback: ask the user
  const input = prompt("Enter your state or city:");
  if (input && input.trim()) {
    saveLocation(input.trim());
  } else {
    setLocationDisplay("Set location");
  }
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

// ── Topics persistence ────────────────────────────────────────

function loadSavedTopics(login) {
  try {
    const saved = localStorage.getItem(`civic-topics-${login}`);
    if (saved) selectedTopics = new Set(JSON.parse(saved));
  } catch {}
}

function saveTopics(login) {
  if (login) {
    localStorage.setItem(`civic-topics-${login}`, JSON.stringify([...selectedTopics]));
  }
}

function updateAuthUI() {
  const authBtn = document.getElementById("auth-btn");
  const locationText = document.getElementById("location-text");
  const mobileLocationText = document.getElementById("mobile-location-text");
  const profileUser = document.getElementById("profile-user");
  const profileAvatar = document.getElementById("profile-avatar");
  const profileName = document.getElementById("profile-name");

  if (currentUser) {
    profileUser.style.display = "flex";
    profileAvatar.src = currentUser.avatar_url;
    profileName.textContent = currentUser.name || currentUser.login;
    authBtn.textContent = "Sign out";
    authBtn.onclick = handleLogout;
    if (currentUser.location) {
      setLocationDisplay(currentUser.location);
    }
  } else {
    profileUser.style.display = "none";
    authBtn.textContent = "Sign in";
    authBtn.onclick = handleLogin;
    // Location display handled by initLocation
  }
}

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

// ── Init ──────────────────────────────────────────────────────

restoreAuth();

fetch("data.json")
  .then(r => r.json())
  .then(data => {
    appData = data;
    buildSidebar();
    buildMobileTopics();
    setupTabs();
    render();
    updateAuthUI();
    initLocation();
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
