import { memoryCapture } from './memory-capture.js';
import { storyPlayer } from './story-player.js';
export function startLinterna({ media } = {}) {
const $ = (sel) => document.querySelector(sel);

const lantern = $("#lantern");
const lanternLabel = $("#lantern-label");
const draft = $("#draft");
const transcriptEl = $("#transcript");
const playback = $("#playback");
const playbackTitle = $("#playback-title");
const playbackText = $("#playback-text");
const memoryTree = $("#memory-tree");
const searchResults = $("#search-results");
const emptyHint = $("#empty-hint");
const statusEl = $("#status");
const setupDialog = $("#setup-dialog");
const setupForm = $("#setup-form");
const searchForm = $("#search-form");
const searchQ = $("#search-q");
const browseLabel = $("#browse-label");
const btnClearFilters = $("#btn-clear-filters");

let timeline = [];
let selectedId = null;
let filters = { year: null, month: null, day: null };
let searchMode = false;

function setStatus(msg) {
  statusEl.textContent = msg || "";
}

function showDraft() {
  playback.classList.add("hidden");
  draft.classList.remove("hidden");
}

let selectedMemory = null;
function showPlayback(memory) {
  player.stop(false);
  selectedMemory = memory;
  const original = $("#original-audio");
  original.pause(); original.removeAttribute("src");
  original.classList.toggle("hidden", !memory.has_audio);
  if (memory.has_audio) original.src = `/api/memories/${memory.id}/audio`;
  original.load();
  $("#btn-play").textContent = memory.has_audio ? "Play recording" : "Read transcript";
  $("#btn-read").classList.toggle("hidden", !memory.has_audio || !memory.transcript);
  draft.classList.add("hidden");
  playback.classList.remove("hidden");
  playbackTitle.textContent = memory.title;
  playbackText.textContent = memory.transcript;
  selectedId = memory.id;
  if (searchMode) renderSearchResults(window.__lastSearch || []);
  else renderTimeline();
}

function queryParams(extra = {}) {
  const params = new URLSearchParams();
  const merged = { ...filters, ...extra };
  if (merged.year) params.set("year", String(merged.year));
  if (merged.month) params.set("month", String(merged.month));
  if (merged.day) params.set("day", String(merged.day));
  return params;
}

function updateBrowseChrome() {
  const parts = [];
  if (filters.year) parts.push(String(filters.year));
  if (filters.month) {
    const label = new Date(2000, filters.month - 1, 1).toLocaleString(undefined, {
      month: "long",
    });
    parts.push(label);
  }
  if (filters.day) parts.push(`day ${filters.day}`);

  browseLabel.textContent = parts.length ? parts.join(" · ") : "All years";
  btnClearFilters.classList.toggle(
    "hidden",
    !filters.year && !filters.month && !filters.day && !searchMode,
  );
}

async function loadTimeline() {
  searchMode = false;
  searchResults.classList.add("hidden");
  memoryTree.classList.remove("hidden");

  const params = queryParams();
  const res = await fetch(`/api/memories/timeline?${params}`);
  const data = await res.json();
  timeline = data.years || [];
  updateBrowseChrome();
  renderTimeline();
}

function countMemories(years) {
  let n = 0;
  for (const year of years) {
    for (const month of year.months || []) {
      for (const day of month.days || []) {
        n += (day.memories || []).length;
      }
    }
  }
  return n;
}

function memoryButton(memory) {
  const btn = document.createElement("button");
  btn.type = "button";
  if (memory.id === selectedId) btn.classList.add("active");
  btn.innerHTML =
    `<img class="memory-thumb" src="/static/assets/lanterns/hero.png" alt="" />` +
    `<span class="memory-copy"><span class="title"></span><span class="meta"></span></span>`;
  btn.querySelector(".title").textContent = memory.title;
  const when = new Date(memory.created_at).toLocaleString();
  const score =
    typeof memory.score === "number" ? ` · match ${memory.score.toFixed(2)}` : "";
  btn.querySelector(".meta").textContent = `${when}${score}`;
  btn.addEventListener("click", () => {
    if (capture.busy()) { setStatus("Finish recording before opening another memory."); return; }
    capture.cancelTranscription(); showPlayback(memory);
  });
  return btn;
}

function renderTimeline() {
  memoryTree.innerHTML = "";
  const total = countMemories(timeline);
  emptyHint.classList.toggle("hidden", total > 0 || searchMode);
  if (!total) {
    emptyHint.textContent = filters.year
      ? "Nothing in this slice. Clear filters or light a new memory."
      : "No memories yet. Press the linterna to speak one.";
    return;
  }

  for (const year of timeline) {
    const yearDetails = document.createElement("details");
    yearDetails.className = "year-group";
    yearDetails.open = Boolean(filters.year) || timeline.length <= 2;
    yearDetails.innerHTML = `<summary></summary><div class="month-stack"></div>`;
    yearDetails.querySelector("summary").textContent = String(year.year);

    const monthStack = yearDetails.querySelector(".month-stack");
    for (const month of year.months || []) {
      const monthDetails = document.createElement("details");
      monthDetails.className = "month-group";
      monthDetails.open = Boolean(filters.month) || (year.months || []).length <= 3;
      monthDetails.innerHTML = `<summary></summary><div class="day-stack"></div>`;
      monthDetails.querySelector("summary").textContent = month.label;

      const dayStack = monthDetails.querySelector(".day-stack");
      for (const day of month.days || []) {
        const dayBlock = document.createElement("div");
        dayBlock.className = "day-group";

        const dayBtn = document.createElement("button");
        dayBtn.type = "button";
        dayBtn.className = "day-chip";
        dayBtn.textContent = day.label;
        dayBtn.addEventListener("click", () => {
          filters = { year: year.year, month: month.month, day: day.day };
          void loadTimeline();
        });
        dayBlock.appendChild(dayBtn);

        const list = document.createElement("ul");
        list.className = "memory-list";
        for (const memory of day.memories || []) {
          const li = document.createElement("li");
          li.appendChild(memoryButton(memory));
          list.appendChild(li);
        }
        dayBlock.appendChild(list);
        dayStack.appendChild(dayBlock);
      }

      monthDetails.querySelector("summary").addEventListener("click", (event) => {
        if (event.metaKey || event.ctrlKey) {
          event.preventDefault();
          filters = { year: year.year, month: month.month, day: null };
          void loadTimeline();
        }
      });

      monthStack.appendChild(monthDetails);
    }

    yearDetails.querySelector("summary").addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey) {
        event.preventDefault();
        filters = { year: year.year, month: null, day: null };
        void loadTimeline();
      }
    });

    memoryTree.appendChild(yearDetails);
  }
}

function renderSearchResults(results) {
  searchResults.innerHTML = "";
  emptyHint.classList.toggle("hidden", results.length > 0);
  if (!results.length) {
    emptyHint.textContent = "No stories matched that topic.";
    return;
  }
  for (const memory of results) {
    const li = document.createElement("li");
    li.appendChild(memoryButton(memory));
    searchResults.appendChild(li);
  }
}

async function runSearch(event) {
  event.preventDefault();
  const q = searchQ.value.trim();
  if (!q) {
    await loadTimeline();
    return;
  }

  setStatus("Searching…");
  const params = queryParams();
  params.set("q", q);
  const res = await fetch(`/api/memories/search?${params}`);
  const data = await res.json();
  window.__lastSearch = data.results || [];

  searchMode = true;
  memoryTree.classList.add("hidden");
  searchResults.classList.remove("hidden");
  updateBrowseChrome();
  browseLabel.textContent = `Topic: ${q}`;
  renderSearchResults(window.__lastSearch);
  setStatus(
    window.__lastSearch.length
      ? `Found ${window.__lastSearch.length} stor${window.__lastSearch.length === 1 ? "y" : "ies"}.`
      : "No matches.",
  );
}

async function clearFilters() {
  filters = { year: null, month: null, day: null };
  searchQ.value = "";
  searchMode = false;
  await loadTimeline();
  setStatus("");
}

const player = storyPlayer(setStatus);
function stopStory(announce = true) { player.stop(announce); $("#original-audio").pause(); }
const capture = memoryCapture({ media, status: setStatus, showDraft, stopPlayback: stopStory,
  saved: async memory => { await loadTimeline(); showPlayback(memory); },
});

async function deleteSelected() {
  if (!selectedId) return;
  if (!window.confirm("Delete this memory?")) return;
  stopStory();
  const res = await fetch(`/api/memories/${selectedId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    setStatus("Delete failed.");
    return;
  }
  selectedId = null;
  playback.classList.add("hidden");
  if (searchMode && searchQ.value.trim()) {
    await runSearch(new Event("submit"));
  } else {
    await loadTimeline();
  }
  setStatus("Memory cleared.");
}

async function openSetup() {
  const res = await fetch("/api/config");
  const cfg = await res.json();
  for (const key of [
    "chat_base_url",
    "chat_model",
    "tts_base_url",
    "tts_model",
    "tts_voice",
    "asr_base_url",
    "asr_model",
  ]) {
    setupForm.elements[key].value = cfg[key] || "";
  }
  setupDialog.showModal();
}

async function saveSetup(event) {
  event.preventDefault();
  const submitter = event.submitter;
  if (submitter && submitter.value === "cancel") {
    setupDialog.close();
    return;
  }

  const body = {
    chat_base_url: setupForm.elements.chat_base_url.value.trim(),
    chat_model: setupForm.elements.chat_model.value.trim(),
    tts_base_url: setupForm.elements.tts_base_url.value.trim(),
    tts_model: setupForm.elements.tts_model.value.trim() || "magpie-tts",
    tts_voice: setupForm.elements.tts_voice.value.trim() || "Sofia",
    asr_base_url: setupForm.elements.asr_base_url.value.trim(),
    asr_model: setupForm.elements.asr_model.value.trim() || "whisper-1",
  };

  const response = await fetch("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error("Config could not be saved.");
  setupDialog.close();
  setStatus("Config saved.");
}

function run(action) { void Promise.resolve().then(action).catch(error => setStatus(error.message || 'Something went wrong. Please try again.')); }
$("#btn-save").addEventListener("click", () => run(capture.save));
$("#btn-discard").addEventListener("click", capture.discard);
$("#btn-play").addEventListener("click", () => { $("#original-audio").pause(); if (selectedMemory) run(() => player.play(selectedMemory)); });
$("#btn-read").addEventListener("click", () => { $("#original-audio").pause(); if (selectedMemory) run(() => player.play(selectedMemory, true)); });
$("#original-audio").addEventListener("play", () => player.stop(false));
$("#btn-stop").addEventListener("click", () => stopStory());
$("#btn-delete").addEventListener("click", () => run(deleteSelected));
$("#btn-setup").addEventListener("click", () => run(openSetup));
btnClearFilters.addEventListener("click", () => run(clearFilters));
setupForm.addEventListener("submit", event => { event.preventDefault(); run(() => saveSetup(event)); });
searchForm.addEventListener("submit", event => { event.preventDefault(); run(() => runSearch(event)); });
window.addEventListener('pagehide', () => stopStory(false));
run(loadTimeline);
document.addEventListener('visibilitychange', () => {
  document.documentElement.toggleAttribute('data-paused', document.hidden);
  if (document.hidden) stopStory(false);
});

}
