"use strict";

const PAGE = 120;
const $ = (id) => document.getElementById(id);
const state = {
  photos: [], next: 0, loading: false, viewing: -1, dayEls: new Map(),
  scope: { kind: null, month: null }, query: "", generation: 0, total: 0,
};

// ---------- server calls ----------

class Unauthorised extends Error {}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  if (response.status === 401) throw new Unauthorised();
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

// ---------- formatting ----------

const dayFormat = new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long" });
const yearDayFormat = new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

function bytes(n) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

function parseTime(text) {
  const date = text ? new Date(text) : null;
  return date && !Number.isNaN(date.getTime()) ? date : null;
}

function ago(text) {
  const date = parseTime(text);
  if (!date) return "never";
  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return timeFormat.format(date);
}

function dayKey(date) {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

const relativeDay = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const monthFormat = new Intl.DateTimeFormat(undefined, { month: "long" });
const monthYearFormat = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" });

function capitalise(text) {
  return text.charAt(0).toLocaleUpperCase() + text.slice(1);
}

// Today and yesterday come from Intl too, so they match the language of the other dates.
function dayLabel(date) {
  const today = new Date();
  const yesterday = new Date(today.getTime() - 86400000);
  if (dayKey(date) === dayKey(today)) return capitalise(relativeDay.format(0, "day"));
  if (dayKey(date) === dayKey(yesterday)) return capitalise(relativeDay.format(-1, "day"));
  return (date.getFullYear() === today.getFullYear() ? dayFormat : yearDayFormat).format(date);
}

function monthDate(month) {
  const [year, number] = month.split("-").map(Number);
  return new Date(year, number - 1, 1);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function toast(message) {
  const box = $("toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { box.hidden = true; }, 2200);
}

// ---------- tiles ----------

const PLAY = '<svg viewBox="0 0 10 12" aria-hidden="true"><path d="M0 0l10 6-10 6z"/></svg>';

function fallback(photo) {
  const box = el("div", "fallback");
  const ext = (photo.name.split(".").pop() || "file").toUpperCase();
  box.append(el("b", "", photo.video ? "VIDEO" : ext));
  box.append(el("span", "", photo.video ? "Tap to play" : "No preview"));
  return box;
}

function showImage(img, tile, sources, photo) {
  const source = sources.shift();
  if (!source) { img.remove(); tile.prepend(fallback(photo)); return; }
  img.onerror = () => showImage(img, tile, sources, photo);
  img.onload = () => img.classList.add("ready");
  img.src = source;
}

function tile(photo, index) {
  const button = el("button", "tile");
  button.type = "button";
  button.setAttribute("aria-label", `${photo.name}, ${timeFormat.format(parseTime(photo.time) || new Date())}`);
  button.addEventListener("click", () => openViewer(index));
  if (photo.video) {
    button.append(fallback(photo));
  } else {
    const img = el("img");
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";
    button.append(img);
    // A preview needs Pillow on the PC; Safari can also show HEIC originals itself.
    showImage(img, button, [photo.thumb, photo.media], photo);
  }
  if (photo.video) {
    const badge = el("span", "badge");
    badge.innerHTML = PLAY;
    button.append(badge);
  }
  return button;
}

function dayGroup(date) {
  const key = dayKey(date);
  if (state.dayEls.has(key)) return state.dayEls.get(key);
  const section = el("section", "day");
  const head = el("header", "day-head");
  const count = el("span");
  head.append(el("h2", "", dayLabel(date)), count);
  const grid = el("div", "grid");
  section.append(head, grid);
  $("days").append(section);
  const group = { grid, count, n: 0 };
  state.dayEls.set(key, group);
  return group;
}

function addPhotos(photos) {
  for (const photo of photos) {
    const index = state.photos.push(photo) - 1;
    const group = dayGroup(parseTime(photo.time) || new Date(0));
    group.grid.append(tile(photo, index));
    group.n += 1;
    group.count.textContent = String(group.n);
  }
}

function photosUrl() {
  const params = new URLSearchParams({ offset: String(state.next), limit: String(PAGE) });
  if (state.scope.kind) params.set("kind", state.scope.kind);
  if (state.scope.month) params.set("month", state.scope.month);
  if (state.query) params.set("q", state.query);
  return `/api/photos?${params}`;
}

async function loadMore() {
  if (state.loading || state.next === null) return;
  state.loading = true;
  const generation = state.generation;
  try {
    const page = await api(photosUrl());
    if (generation !== state.generation) return;
    addPhotos(page.photos);
    state.next = page.next;
    renderScope();
  } catch (error) {
    handle(error);
  } finally {
    state.loading = false;
    // A filter changed while this page was loading: load the first page of the new view.
    // On a tall screen one page may not reach the observer's margin, so keep going.
    const nearEnd = $("sentinel").getBoundingClientRect().top < window.innerHeight + 1200;
    if (generation !== state.generation || (nearEnd && state.next !== null && !$("view-photos").hidden)) loadMore();
  }
}

function resetPhotos() {
  state.generation += 1;
  state.photos = [];
  state.next = 0;
  state.dayEls.clear();
  $("days").replaceChildren();
  return loadMore();
}

// ---------- browsing: months, videos, search ----------

function scopeTitle() {
  if (state.scope.month) return capitalise(monthYearFormat.format(monthDate(state.scope.month)));
  return state.scope.kind === "video" ? "Videos" : "All photos";
}

function renderScope() {
  const narrowed = Boolean(state.scope.month || state.scope.kind || state.query);
  const shown = state.photos.length;
  $("scope-title").textContent = state.query ? `“${state.query}”` : scopeTitle();
  if (!narrowed) $("scope-count").textContent = state.total.toLocaleString();
  else $("scope-count").textContent = state.next === null ? shown.toLocaleString() : `${shown.toLocaleString()}+`;
  $("scope-clear").hidden = !narrowed;
  const empty = shown === 0 && state.next === null;
  $("empty").hidden = !empty;
  if (empty) {
    $("empty-title").textContent = narrowed ? "Nothing here" : "No photos yet";
    $("empty-text").textContent = narrowed
      ? "No photo matches. Try another month or search."
      : "Once the iPhone Shortcut runs on your home Wi-Fi, photos appear here, newest first. You can also drop files here or use Upload.";
    $("empty-action").hidden = narrowed;
  }
}

function markScope() {
  const active = state.scope.month || state.scope.kind || "all";
  for (const item of document.querySelectorAll(".rail-item")) {
    item.setAttribute("aria-pressed", String(item.dataset.scope === active));
  }
}

function setScope(kind, month) {
  state.scope = { kind, month };
  markScope();
  window.scrollTo({ top: 0 });
  resetPhotos();
}

function railButton(scope, label, count) {
  const button = el("button", "rail-item");
  button.type = "button";
  button.dataset.scope = scope;
  button.setAttribute("aria-pressed", "false");
  button.append(el("span", "", label), el("b", "", count.toLocaleString()));
  button.addEventListener("click", () => setScope(null, scope));
  return button;
}

async function loadOutline() {
  const outline = await api("/api/outline");
  const years = $("rail-years");
  years.replaceChildren();
  let year = null;
  for (const { month, count } of outline.months) {
    if (month.slice(0, 4) !== year) {
      year = month.slice(0, 4);
      years.append(el("h4", "rail-year", year));
    }
    years.append(railButton(month, capitalise(monthFormat.format(monthDate(month))), count));
  }
  $("rail-videos").textContent = outline.videos.toLocaleString();
  document.querySelector('[data-scope="video"]').hidden = outline.videos === 0;
  markScope();
}

function wireBrowser() {
  document.querySelector('[data-scope="all"]').addEventListener("click", () => setScope(null, null));
  document.querySelector('[data-scope="video"]').addEventListener("click", () => setScope("video", null));
  $("scope-clear").addEventListener("click", () => {
    $("search").value = "";
    state.query = "";
    setScope(null, null);
  });
  let timer = null;
  $("search").addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const query = $("search").value.trim();
      if (query === state.query) return;
      state.query = query;
      if (document.querySelector('[data-view="photos"]').getAttribute("aria-selected") !== "true") show("photos");
      // Search covers the whole library, not just the month in view.
      if (query) {
        state.scope = { kind: null, month: null };
        markScope();
      }
      resetPhotos();
    }, 250);
  });
}

// ---------- uploads from the browser ----------

const uploads = { queue: [], running: false, done: 0, total: 0, stored: 0 };

function uploadOne(item) {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open("POST", "/api/upload");
    // Header values must be Latin-1, so the name travels percent-encoded.
    request.setRequestHeader("X-Name", encodeURIComponent(item.file.name));
    if (item.file.lastModified) request.setRequestHeader("X-Modified", new Date(item.file.lastModified).toISOString());
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) item.state.textContent = `${Math.round((event.loaded / event.total) * 100)}%`;
    };
    request.onload = () => {
      let reply = {};
      try { reply = JSON.parse(request.responseText); } catch (_) { /* not JSON */ }
      if (request.status === 200) {
        item.row.classList.add("done");
        item.state.textContent = reply.status === "duplicate" ? "Already here" : "Added";
        if (reply.status === "stored") uploads.stored += 1;
      } else {
        item.row.classList.add("failed");
        item.state.textContent = request.status === 401 ? "Signed out" : (reply.error || `Failed (${request.status})`);
      }
      resolve();
    };
    request.onerror = () => {
      item.row.classList.add("failed");
      item.state.textContent = "Connection lost";
      resolve();
    };
    request.send(item.file);
  });
}

function renderUploads() {
  $("uploads-title").textContent = uploads.running
    ? `Uploading ${Math.min(uploads.done + 1, uploads.total)} of ${uploads.total}`
    : `${uploads.stored} added · ${uploads.total - uploads.stored} skipped or failed`;
  $("uploads-progress").style.width = `${uploads.total ? (uploads.done / uploads.total) * 100 : 0}%`;
}

async function runUploads() {
  if (uploads.running) return;
  uploads.running = true;
  while (uploads.queue.length) {
    renderUploads();
    await uploadOne(uploads.queue.shift());
    uploads.done += 1;
  }
  uploads.running = false;
  renderUploads();
  if (uploads.stored) {
    toast(`${uploads.stored} added to Harbor`);
    refreshStatus().catch(handle);
    loadOutline().catch(handle);
    resetPhotos();
  }
}

function isMedia(file) {
  return /^(image|video)\//.test(file.type) || /\.(heic|heif|dng|mov)$/i.test(file.name);
}

function enqueue(files) {
  const media = [...files].filter(isMedia);
  if (media.length === 0) { toast("Only photos and videos can be added"); return; }
  const list = $("uploads-list");
  if (!uploads.running) {
    Object.assign(uploads, { done: 0, total: 0, stored: 0 });
    list.replaceChildren();
  }
  for (const file of media) {
    const row = el("li");
    const label = el("span", "state", "Waiting");
    row.append(el("span", "", file.name), label);
    list.append(row);
    uploads.queue.push({ file, row, state: label });
  }
  uploads.total += media.length;
  $("uploads").hidden = false;
  runUploads();
}

function wireUploads() {
  $("upload-button").addEventListener("click", () => $("upload-input").click());
  $("upload-input").addEventListener("change", (event) => {
    enqueue(event.target.files);
    event.target.value = "";
  });
  $("uploads-close").addEventListener("click", () => { $("uploads").hidden = true; });
  let depth = 0;
  const hasFiles = (event) => [...(event.dataTransfer?.types || [])].includes("Files");
  document.addEventListener("dragenter", (event) => {
    if (!hasFiles(event) || $("shell").hidden) return;
    depth += 1;
    $("drop").hidden = false;
  });
  document.addEventListener("dragleave", () => {
    depth = Math.max(depth - 1, 0);
    if (depth === 0) $("drop").hidden = true;
  });
  document.addEventListener("dragover", (event) => { if (hasFiles(event)) event.preventDefault(); });
  document.addEventListener("drop", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    depth = 0;
    $("drop").hidden = true;
    if (!$("shell").hidden) enqueue(event.dataTransfer.files);
  });
}

// ---------- viewer ----------

function openViewer(index) {
  const photo = state.photos[index];
  if (!photo) return;
  state.viewing = index;
  const stage = $("viewer-stage");
  stage.replaceChildren();
  if (photo.video) {
    const video = el("video");
    video.controls = true;
    video.playsInline = true;
    video.preload = "metadata";
    video.src = photo.media;
    stage.append(video);
  } else {
    const img = el("img");
    img.alt = photo.name;
    img.onerror = () => {
      img.onerror = null;
      img.src = photo.thumb;
      img.addEventListener("error", () => stage.replaceChildren(el("p", "fallback",
        "This browser cannot show this format. Download the original to open it.")), { once: true });
    };
    img.src = photo.media;
    stage.append(img);
  }
  $("viewer-title").textContent = photo.name;
  const taken = parseTime(photo.time);
  $("viewer-detail").textContent = `${taken ? timeFormat.format(taken) : ""} · ${bytes(photo.size)}`;
  $("viewer-download").href = photo.media;
  $("viewer-download").setAttribute("download", photo.name);
  $("viewer-prev").disabled = index === 0;
  $("viewer-next").disabled = index === state.photos.length - 1;
  $("viewer").hidden = false;
  document.body.style.overflow = "hidden";
}

function closeViewer() {
  $("viewer").hidden = true;
  $("viewer-stage").replaceChildren();
  document.body.style.overflow = "";
  state.viewing = -1;
}

function step(delta) {
  if (state.viewing < 0) return;
  const target = state.viewing + delta;
  if (target >= state.photos.length - 6) loadMore();
  if (target >= 0 && target < state.photos.length) openViewer(target);
}

function wireViewer() {
  $("viewer-close").addEventListener("click", closeViewer);
  $("viewer-prev").addEventListener("click", () => step(-1));
  $("viewer-next").addEventListener("click", () => step(1));
  document.addEventListener("keydown", (event) => {
    if (state.viewing < 0) return;
    if (event.key === "Escape") closeViewer();
    if (event.key === "ArrowLeft") step(-1);
    if (event.key === "ArrowRight") step(1);
  });
  let startX = null;
  const stage = $("viewer-stage");
  stage.addEventListener("touchstart", (event) => { startX = event.touches[0].clientX; }, { passive: true });
  stage.addEventListener("touchend", (event) => {
    if (startX === null) return;
    const dx = event.changedTouches[0].clientX - startX;
    startX = null;
    if (Math.abs(dx) > 50) step(dx < 0 ? 1 : -1);
  });
}

// ---------- sync and setup views ----------

async function refreshStatus() {
  const s = await api("/api/status");
  state.total = s.count;
  $("rail-all").textContent = s.count.toLocaleString();
  $("s-count").textContent = s.count.toLocaleString();
  $("s-bytes").textContent = bytes(s.bytes);
  $("s-sync").textContent = ago(s.last_sync);
  const d = s.last_day;
  $("s-day").textContent = `${d.stored} new · ${d.duplicate} already here · ${d.rejected} failed`;
  const list = $("missing");
  list.replaceChildren();
  if (s.missing.length === 0) {
    list.append(el("li", "none", "Nothing missing. Every photo checked so far is on the PC."));
  }
  for (const item of s.missing) {
    const row = el("li");
    row.append(el("span", "", item.name || `${item.sha256.slice(0, 12)}…`), el("span", "hint", ago(item.reported_at)));
    list.append(row);
  }
  $("previews-note").textContent = s.previews ? "" :
    "Previews are off: install Pillow and pillow-heif on the PC for HEIC thumbnails in every browser.";
}

async function loadSetup() {
  const setup = await api("/api/setup");
  $("setup-server").textContent = setup.server;
  $("setup-key").textContent = setup.key;
}

function show(view) {
  for (const tab of document.querySelectorAll("[role=tab]")) {
    tab.setAttribute("aria-selected", String(tab.dataset.view === view));
  }
  for (const name of ["photos", "sync", "setup"]) $(`view-${name}`).hidden = name !== view;
  if (view === "sync") refreshStatus().catch(handle);
  if (view === "setup") loadSetup().catch(handle);
  try { localStorage.setItem("harbor-view", view); } catch (_) { /* private mode */ }
}

function wireShell() {
  for (const tab of document.querySelectorAll("[role=tab]")) {
    tab.addEventListener("click", () => show(tab.dataset.view));
  }
  for (const link of document.querySelectorAll("[data-goto]")) {
    link.addEventListener("click", () => show(link.dataset.goto));
  }
  for (const button of document.querySelectorAll("[data-copy]")) {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText($(button.dataset.copy).textContent);
        toast("Copied");
      } catch (_) {
        toast("Select the text and copy it by hand");
      }
    });
  }
  new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) loadMore();
  }, { rootMargin: "1200px" }).observe($("sentinel"));
  const bar = document.querySelector(".topbar");
  new ResizeObserver(() => {
    document.documentElement.style.setProperty("--topbar-h", `${bar.offsetHeight}px`);
  }).observe(bar);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && !$("shell").hidden) refreshStatus().catch(handle);
  });
}

// ---------- sign-in ----------

function handle(error) {
  if (error instanceof Unauthorised) {
    $("shell").hidden = true;
    $("login").hidden = false;
    $("login-key").focus();
    return;
  }
  toast(error.message || "Something went wrong");
}

async function start() {
  try {
    await refreshStatus();
  } catch (error) {
    handle(error);
    return;
  }
  $("login").hidden = true;
  $("shell").hidden = false;
  let view = "photos";
  try { view = localStorage.getItem("harbor-view") || "photos"; } catch (_) { /* private mode */ }
  show(view);
  loadOutline().catch(handle);
  resetPhotos();
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("login-error").textContent = "";
  try {
    await api("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: $("login-key").value.trim() }),
    });
    start();
  } catch (error) {
    $("login-error").textContent = error instanceof Unauthorised ? "That key is not right." : error.message;
  }
});

wireShell();
wireBrowser();
wireUploads();
wireViewer();
start();
