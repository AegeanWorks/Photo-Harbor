"use strict";

const PAGE = 120;
const BATCH = 500;
const TILE_MIN = 150;
const DAY_HEADER = 42;
const DAY_GAP = 18;
const $ = (id) => document.getElementById(id);
const state = {
  photos: [], next: 0, loading: false, viewing: -1, dayEls: new Map(), dayList: [],
  dayWindowFrame: null,
  scope: { kind: null, month: null, favorite: false, album: null, tag: null, place: null,
    camera: null, lens: null, start: null, end: null, day: null, archived: false,
    order: "newest" },
  query: "",
  months: [],
  generation: 0, total: 0, visible: 0, archived: 0, profile: null, people: [], me: null,
  owner: false, favorites: 0, albums: [], tags: [], selecting: false, selected: new Set(),
  viewerReturnFocus: null, compareReturnFocus: null, similarTimer: null,
};

function personName(id) {
  const person = state.people.find((p) => p.id === id);
  return person ? person.name : id;
}

function initials(name) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toLocaleUpperCase()).join("");
}

function post(path, body) {
  return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

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

function items(n) {
  return `${n.toLocaleString()} item${n === 1 ? "" : "s"}`;
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
const dateOnlyFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });

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
  button.dataset.index = String(index);
  button.dataset.sha = photo.sha256;
  if (state.selected.has(photo.sha256)) button.classList.add("selected");
  button.setAttribute("aria-label", `${photo.name}${photo.favorite ? ", favorite" : ""}, ${timeFormat.format(parseTime(photo.time) || new Date())}`);
  button.addEventListener("click", () => {
    if (state.selecting) toggleSelected(photo.sha256);
    else openViewer(index);
  });
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
  if (photo.favorite) button.append(favoriteMark());
  return button;
}

function favoriteMark() {
  const heart = el("span", "heart", "♥");
  heart.title = "Favorite";
  return heart;
}

function dayGroup(date) {
  const key = dayKey(date);
  if (state.dayEls.has(key)) return state.dayEls.get(key);
  const group = { key, photos: [], n: 0, section: null, grid: null, count: null,
    top: 0, height: 0, rendered: false };
  state.dayEls.set(key, group);
  state.dayList.push(group);
  return group;
}

function gridMetrics() {
  const days = $("days");
  const width = Math.max(days.clientWidth || days.getBoundingClientRect().width, 1);
  const gap = parseFloat(getComputedStyle(document.documentElement)
    .getPropertyValue("--gap")) || 4;
  const columns = window.innerWidth <= 380 ? 3
    : Math.max(1, Math.floor((width + gap) / (TILE_MIN + gap)));
  return { gap, columns, tile: Math.max(1, (width - gap * (columns - 1)) / columns) };
}

function layoutDays() {
  const metrics = gridMetrics();
  let top = 0;
  for (const group of state.dayList) {
    const rows = Math.max(1, Math.ceil(group.photos.length / metrics.columns));
    const gridHeight = group.photos.length
      ? rows * metrics.tile + (rows - 1) * metrics.gap : 0;
    group.top = top;
    group.height = DAY_HEADER + gridHeight + DAY_GAP;
    top += group.height;
    if (group.section) {
      group.section.style.top = `${group.top}px`;
      group.section.style.height = `${group.height}px`;
      group.grid.style.height = `${gridHeight}px`;
      group.grid.style.gridTemplateRows = `repeat(${rows}, ${metrics.tile}px)`;
    }
  }
  const days = $("days");
  days.style.position = "relative";
  days.style.height = `${top}px`;
}

function createDaySection(group) {
  const section = el("section", "day virtual-day");
  section.dataset.day = group.key;
  section.style.top = `${group.top}px`;
  section.style.height = `${group.height}px`;
  const head = el("header", "day-head");
  const count = el("span");
  const first = group.photos[0]?.photo;
  head.append(el("h2", "", dayLabel(parseTime(first?.time) || new Date(0))), count);
  const grid = el("div", "grid");
  section.append(head, grid);
  $("days").append(section);
  group.section = section;
  group.grid = grid;
  group.count = count;
}

function renderDay(group) {
  if (!group.section) createDaySection(group);
  group.count.textContent = String(group.photos.length);
  group.grid.replaceChildren(...group.photos.map((item) => tile(item.photo, item.index)));
  const metrics = gridMetrics();
  const rows = Math.max(1, Math.ceil(group.photos.length / metrics.columns));
  group.grid.style.height = group.photos.length
    ? `${rows * metrics.tile + (rows - 1) * metrics.gap}px` : "0px";
  group.grid.style.gridTemplateRows = `repeat(${rows}, ${metrics.tile}px)`;
  group.rendered = true;
}

function unrenderDay(group) {
  if (group.section) group.section.remove();
  group.section = null;
  group.grid = null;
  group.count = null;
  group.rendered = false;
}

function renderWindow() {
  if (state.dayList.length === 0) {
    $("days").style.height = "0px";
    return;
  }
  const days = $("days");
  const origin = days.getBoundingClientRect().top + window.scrollY;
  const top = window.scrollY - 1000;
  const bottom = window.scrollY + window.innerHeight + 1200;
  for (const group of state.dayList) {
    const sectionTop = origin + group.top;
    const sectionBottom = sectionTop + group.height;
    const visible = sectionBottom >= top && sectionTop <= bottom;
    if (visible && !group.rendered) renderDay(group);
    else if (!visible && group.rendered) unrenderDay(group);
  }
}

function scheduleWindow() {
  if (state.dayWindowFrame !== null) return;
  // A timer, not requestAnimationFrame: the window must also update in a background
  // tab where Chromium pauses animation frames.
  state.dayWindowFrame = setTimeout(() => {
    state.dayWindowFrame = null;
    renderWindow();
  }, 16);
}

function addPhotos(photos) {
  const touched = new Set();
  for (const photo of photos) {
    const index = state.photos.push(photo) - 1;
    const group = dayGroup(parseTime(photo.time) || new Date(0));
    group.photos.push({ photo, index });
    group.n += 1;
    touched.add(group);
  }
  for (const group of touched) {
    if (group.count) group.count.textContent = String(group.photos.length);
    if (group.rendered) renderDay(group);
  }
  layoutDays();
  renderWindow();
}

function filterParams() {
  const params = new URLSearchParams();
  if (state.scope.kind) params.set("kind", state.scope.kind);
  if (state.scope.month) params.set("month", state.scope.month);
  if (state.scope.favorite) params.set("favorite", "1");
  if (state.scope.archived) params.set("archived", "1");
  if (state.scope.album) params.set("album", String(state.scope.album));
  if (state.scope.tag) params.set("tag", String(state.scope.tag));
  if (state.scope.place) params.set("place", state.scope.place);
  if (state.scope.camera) params.set("camera", state.scope.camera);
  if (state.scope.lens) params.set("lens", state.scope.lens);
  if (state.scope.start) params.set("from", state.scope.start);
  if (state.scope.end) params.set("to", state.scope.end);
  if (state.scope.day) params.set("day", state.scope.day);
  if (state.scope.order) params.set("order", state.scope.order);
  if (state.query) params.set("q", state.query);
  if (state.profile) params.set("profile", state.profile);
  return params;
}

function photosUrl() {
  const params = filterParams();
  params.set("offset", String(state.next));
  params.set("limit", String(PAGE));
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
  if (state.selected.size || document.querySelector(".tile.selected")) clearSelected();
  state.generation += 1;
  state.photos = [];
  state.next = 0;
  state.dayEls.clear();
  state.dayList = [];
  if (state.dayWindowFrame !== null) {
    clearTimeout(state.dayWindowFrame);
    state.dayWindowFrame = null;
  }
  $("days").replaceChildren();
  $("days").style.height = "0px";
  return loadMore();
}

// ---------- browsing: months, videos, search ----------

function currentAlbum() {
  return state.albums.find((album) => album.id === state.scope.album) || null;
}

function currentTag() {
  return state.tags.find((tag) => tag.id === state.scope.tag) || null;
}

function placeLabel(key) {
  const [lat, lon] = String(key).split(",").map(Number);
  const north = lat >= 0 ? "N" : "S";
  const east = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(1)}° ${north}, ${Math.abs(lon).toFixed(1)}° ${east}`;
}

function dateTitle() {
  const start = state.scope.start
    ? dateOnlyFormat.format(new Date(`${state.scope.start}T00:00:00`)) : null;
  const end = state.scope.end
    ? dateOnlyFormat.format(new Date(`${state.scope.end}T00:00:00`)) : null;
  if (start && end) return `${start} – ${end}`;
  if (start) return `From ${start}`;
  if (end) return `Until ${end}`;
  return "";
}

function scopeTitle() {
  const album = currentAlbum();
  let base = "All photos";
  if (album) base = album.name;
  else if (state.scope.tag) base = currentTag()?.name || "Tag";
  else if (state.scope.place) base = `Near ${placeLabel(state.scope.place)}`;
  else if (state.scope.camera) base = `Shot with ${state.scope.camera}`;
  else if (state.scope.lens) base = `Lens ${state.scope.lens}`;
  else if (state.scope.archived) base = "Archive";
  else if (state.scope.favorite) base = "Favorites";
  else if (state.scope.day) base = "On this day";
  else if (state.scope.month) base = capitalise(monthYearFormat.format(monthDate(state.scope.month)));
  else if (state.scope.kind === "video") base = "Videos";
  const dates = dateTitle();
  return dates ? `${base} · ${dates}` : base;
}

function renderScope() {
  const extra = Boolean(state.scope.month || state.scope.kind || state.scope.start
    || state.scope.end || state.scope.day || state.scope.place || state.scope.camera
    || state.scope.lens || state.query);
  const narrowed = Boolean(extra || state.scope.favorite || state.scope.album
    || state.scope.tag || state.scope.archived);
  const shown = state.photos.length;
  const title = state.query ? `${scopeTitle()} · “${state.query}”` : scopeTitle();
  $("scope-title").textContent = state.profile ? `${personName(state.profile)} · ${title}` : title;
  if (extra) $("scope-count").textContent = state.next === null ? shown.toLocaleString() : `${shown.toLocaleString()}+`;
  else if (state.scope.album) $("scope-count").textContent = (currentAlbum()?.count ?? shown).toLocaleString();
  else if (state.scope.tag) $("scope-count").textContent = (currentTag()?.count ?? shown).toLocaleString();
  else if (state.scope.archived) $("scope-count").textContent = state.archived.toLocaleString();
  else if (state.scope.favorite) $("scope-count").textContent = state.favorites.toLocaleString();
  else if (!narrowed && !state.profile) $("scope-count").textContent = state.visible.toLocaleString();
  else if (!narrowed) $("scope-count").textContent = state.visible.toLocaleString();
  else $("scope-count").textContent = state.next === null ? shown.toLocaleString() : `${shown.toLocaleString()}+`;
  $("scope-clear").hidden = !narrowed;
  $("sort-order").value = state.scope.order || "newest";
  $("album-rename").hidden = !currentAlbum();
  $("album-delete").hidden = !currentAlbum();
  $("album-download").hidden = !currentAlbum();
  const empty = shown === 0 && state.next === null;
  $("empty").hidden = !empty;
  if (empty) {
    $("empty-title").textContent = narrowed ? "Nothing here" : "No photos yet";
    $("empty-text").textContent = state.scope.album
      ? "This album is empty. Open a photo and choose Add to album."
      : state.scope.tag
        ? "No photos with this tag yet. Open a photo and choose Add tag…"
        : state.scope.favorite
          ? "No favorites yet. Open a photo and press ♡ Favorite."
          : state.scope.archived
          ? "Nothing archived. Open a photo and choose Archive to hide it from the timeline."
          : state.scope.place
            ? "No photos with a location here."
            : state.scope.camera
              ? "No photos from this camera."
              : state.scope.lens
                ? "No photos from this lens."
                : state.scope.day
                ? "No photos from this day in other years."
                : narrowed
              ? "No photo matches. Try another month or search."
              : "Once the iPhone Shortcut runs on your home Wi-Fi, photos appear here, newest first. You can also drop files here or use Upload.";
    $("empty-action").hidden = narrowed;
  }
}

function markScope() {
  const active = state.scope.album || state.scope.tag || state.scope.place
    || state.scope.camera || state.scope.lens ? null
    : state.scope.archived ? "archive"
      : state.scope.day ? "memories"
        : state.scope.favorite ? "favorite"
          : state.scope.month || state.scope.kind || "all";
  for (const item of document.querySelectorAll(".rail-item[data-scope]")) {
    item.setAttribute("aria-pressed", String(item.dataset.scope === active));
  }
  for (const item of document.querySelectorAll("[data-album]")) {
    item.setAttribute("aria-pressed", String(Number(item.dataset.album) === state.scope.album));
  }
  for (const item of document.querySelectorAll("[data-tag]")) {
    item.setAttribute("aria-pressed", String(Number(item.dataset.tag) === state.scope.tag));
  }
  for (const item of document.querySelectorAll("[data-place]")) {
    item.setAttribute("aria-pressed", String(item.dataset.place === state.scope.place));
  }
  for (const item of document.querySelectorAll("[data-camera]")) {
    item.setAttribute("aria-pressed", String(item.dataset.camera === state.scope.camera));
  }
  for (const item of document.querySelectorAll("[data-lens]")) {
    item.setAttribute("aria-pressed", String(item.dataset.lens === state.scope.lens));
  }
  $("date-filter").setAttribute("aria-pressed",
    String(Boolean(state.scope.start || state.scope.end)));
}

function setScope(kind, month, extra = {}) {
  if (state.selecting) setSelecting(false);
  state.scope = { kind, month, favorite: false, album: null, tag: null, place: null,
    camera: null, lens: null, start: null, end: null, day: null, archived: false,
    order: state.scope.order || "newest", ...extra };
  hideDatePanel();
  markScope();
  renderScrubber();
  window.scrollTo({ top: 0 });
  resetPhotos();
}

function hideDatePanel() {
  $("date-panel").hidden = true;
  $("date-filter").setAttribute("aria-expanded", "false");
}

function toggleDatePanel() {
  hideSelectAlbums();
  const panel = $("date-panel");
  if (!panel.hidden) {
    hideDatePanel();
    return;
  }
  $("date-from").value = state.scope.start || "";
  $("date-to").value = state.scope.end || "";
  panel.hidden = false;
  $("date-filter").setAttribute("aria-expanded", "true");
}

function applyDates() {
  const start = $("date-from").value || null;
  const end = $("date-to").value || null;
  if (start && end && start > end) {
    toast("Choose a From date on or before To");
    return;
  }
  setScope(null, null, { start, end });
}

function clearDates() {
  $("date-from").value = "";
  $("date-to").value = "";
  setScope(null, null);
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
  const outline = await api(state.profile ? `/api/outline?profile=${encodeURIComponent(state.profile)}` : "/api/outline");
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
  const placesRail = $("rail-places");
  placesRail.replaceChildren();
  if (outline.places?.length) {
    placesRail.append(el("h4", "rail-year", "Places"));
    for (const place of outline.places) {
      const button = el("button", "rail-item");
      button.type = "button";
      button.dataset.place = place.key;
      button.setAttribute("aria-pressed", String(place.key === state.scope.place));
      button.append(el("span", "", placeLabel(place.key)),
        el("b", "", place.count.toLocaleString()));
      button.addEventListener("click", () => selectPlace(place.key));
      placesRail.append(button);
    }
  }
  const camerasRail = $("rail-cameras");
  camerasRail.replaceChildren();
  if (outline.cameras?.length) {
    camerasRail.append(el("h4", "rail-year", "Cameras"));
    for (const cameraItem of outline.cameras) {
      const button = el("button", "rail-item");
      button.type = "button";
      button.dataset.camera = cameraItem.name;
      button.setAttribute("aria-pressed", String(cameraItem.name === state.scope.camera));
      button.append(el("span", "", cameraItem.name),
        el("b", "", cameraItem.count.toLocaleString()));
      button.addEventListener("click", () => selectCamera(cameraItem.name));
      camerasRail.append(button);
    }
  }
  const lensesRail = $("rail-lenses");
  lensesRail.replaceChildren();
  if (outline.lenses?.length) {
    lensesRail.append(el("h4", "rail-year", "Lenses"));
    for (const lens of outline.lenses) {
      const button = el("button", "rail-item");
      button.type = "button";
      button.dataset.lens = lens.name;
      button.setAttribute("aria-pressed", String(lens.name === state.scope.lens));
      button.append(el("span", "", lens.name),
        el("b", "", lens.count.toLocaleString()));
      button.addEventListener("click", () => selectLens(lens.name));
      lensesRail.append(button);
    }
  }
  state.months = outline.months || [];
  $("rail-videos").textContent = outline.videos.toLocaleString();
  state.favorites = outline.favorites || 0;
  state.visible = outline.total || 0;
  state.archived = outline.archived || 0;
  $("rail-all").textContent = state.visible.toLocaleString();
  $("rail-favorites").textContent = state.favorites.toLocaleString();
  $("rail-archived").textContent = state.archived.toLocaleString();
  document.querySelector('[data-scope="video"]').hidden = outline.videos === 0;
  markScope();
  renderScrubber();
  renderScope();
}

function renderScrubber() {
  const bar = $("timeline-scrubber");
  if (state.months.length === 0) {
    bar.hidden = true;
    return;
  }
  bar.hidden = false;
  const selected = state.months.find((month) => month.month === state.scope.month)
    || state.months[0];
  const currentYear = selected.month.slice(0, 4);
  const years = [...new Set(state.months.map((month) => month.month.slice(0, 4)))];
  $("scrubber-year").replaceChildren(...years.map((year) =>
    new Option(year, year, false, year === currentYear)));
  const months = state.months.filter((month) => month.month.startsWith(`${currentYear}-`));
  $("scrubber-month").replaceChildren(...months.map((month) =>
    new Option(`${capitalise(monthFormat.format(monthDate(month.month)))} · ${month.count}`,
      month.month, false, month.month === selected.month)));
  $("scrubber-current").textContent =
    `${capitalise(monthYearFormat.format(monthDate(selected.month)))} · ${items(selected.count)}`;
  const index = state.months.findIndex((month) => month.month === selected.month);
  $("scrubber-newer").disabled = index <= 0;
  $("scrubber-older").disabled = index < 0 || index >= state.months.length - 1;
}

function jumpToMonth(month) {
  if (!month) return;
  setScope(null, month);
}

function stepScrubber(delta) {
  const current = state.scope.month || state.months[0]?.month;
  const index = state.months.findIndex((month) => month.month === current);
  const target = state.months[index + delta];
  if (target) jumpToMonth(target.month);
}

// ---------- people ----------

function personButton(id, label, count) {
  const button = el("button", "rail-item");
  button.type = "button";
  button.dataset.person = id || "";
  button.setAttribute("aria-pressed", String((state.profile || "") === (id || "")));
  button.append(el("span", "", label), el("b", "", count.toLocaleString()));
  button.addEventListener("click", () => selectPerson(id));
  return button;
}

function selectPerson(id) {
  if (state.selecting) setSelecting(false);
  hideDatePanel();
  state.profile = id;
  for (const item of document.querySelectorAll("[data-person]")) {
    item.setAttribute("aria-pressed", String(item.dataset.person === (id || "")));
  }
  state.scope = { kind: null, month: null, favorite: false, album: null, tag: null,
    place: null, camera: null, lens: null, start: null, end: null, day: null,
    archived: false, order: state.scope.order || "newest" };
  markScope();
  window.scrollTo({ top: 0 });
  loadOutline().catch(handle);
  resetPhotos();
}

// ---------- albums and favorites ----------

function clearPersonScope() {
  if (!state.owner) return;
  state.profile = null;
  for (const item of document.querySelectorAll("[data-person]")) {
    item.setAttribute("aria-pressed", String(item.dataset.person === ""));
  }
}

function selectFavorites() {
  clearPersonScope();
  setScope(null, null, { favorite: true });
  loadOutline().catch(handle);
}

function todayMonthDay() {
  const now = new Date();
  return `${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function selectMemories() {
  setScope(null, null, { day: todayMonthDay() });
}

function selectArchive() {
  clearPersonScope();
  setScope(null, null, { archived: true });
  loadOutline().catch(handle);
}

function selectPlace(key) {
  clearPersonScope();
  setScope(null, null, { place: key });
}

function selectCamera(name) {
  clearPersonScope();
  setScope(null, null, { camera: name });
}

function selectLens(name) {
  clearPersonScope();
  setScope(null, null, { lens: name });
}

function selectAlbum(id) {
  if (!state.albums.some((album) => album.id === id)) return;
  clearPersonScope();
  setScope(null, null, { album: id });
  loadOutline().catch(handle);
  renderScope();
}

async function loadAlbums() {
  const listing = await api("/api/albums");
  state.favorites = listing.favorites;
  state.albums = listing.albums;
  $("rail-favorites").textContent = state.favorites.toLocaleString();
  const rail = $("rail-albums");
  rail.replaceChildren();
  for (const album of state.albums) {
    const button = el("button", "rail-item");
    button.type = "button";
    button.dataset.album = String(album.id);
    button.setAttribute("aria-pressed", String(album.id === state.scope.album));
    const label = el("span", "rail-label");
    if (album.cover) {
      const cover = el("img", "rail-cover");
      cover.src = album.cover;
      cover.alt = "";
      cover.loading = "lazy";
      cover.onerror = () => cover.remove();
      label.append(cover);
    }
    label.append(el("span", "", album.name));
    button.append(label, el("b", "", album.count.toLocaleString()));
    button.addEventListener("click", () => selectAlbum(album.id));
    rail.append(button);
  }
  renderScope();
  renderViewerCollections();
  return listing;
}

async function loadAlbumOverview() {
  const listing = await loadAlbums();
  $("albums-status").textContent =
    `${listing.albums.length.toLocaleString()} albums · ${listing.favorites.toLocaleString()} favorites`;
  const grid = $("albums-grid");
  grid.replaceChildren();
  if (listing.albums.length === 0) {
    grid.append(el("p", "hint", "No albums yet. Select photos and use Add to album…."));
    return;
  }
  for (const album of listing.albums) {
    const card = el("button", "album-card");
    card.type = "button";
    if (album.cover) {
      const img = el("img");
      img.src = album.cover;
      img.alt = "";
      img.loading = "lazy";
      img.onerror = () => img.replaceWith(el("div", "album-cover-empty", "No cover"));
      card.append(img);
    } else {
      card.append(el("div", "album-cover-empty", "No photos yet"));
    }
    card.append(el("span", "album-name", album.name),
      el("span", "album-count", items(album.count)));
    card.addEventListener("click", () => {
      selectAlbum(album.id);
      show("photos");
    });
    grid.append(card);
  }
}

function selectTag(id) {
  if (!state.tags.some((tag) => tag.id === id)) return;
  clearPersonScope();
  setScope(null, null, { tag: id });
  renderScope();
}

async function loadTags() {
  const listing = await api("/api/tags");
  state.tags = listing.tags || [];
  const rail = $("rail-tags");
  rail.replaceChildren();
  if (state.tags.length) {
    rail.append(el("h4", "rail-year", "Tags"));
  }
  for (const tag of state.tags) {
    const button = el("button", "rail-item");
    button.type = "button";
    button.dataset.tag = String(tag.id);
    button.setAttribute("aria-pressed", String(tag.id === state.scope.tag));
    button.append(el("span", "", tag.name), el("b", "", tag.count.toLocaleString()));
    button.addEventListener("click", () => selectTag(tag.id));
    rail.append(button);
  }
  markScope();
  renderScope();
  renderViewerCollections();
  return listing;
}

async function loadTagOverview() {
  const listing = await loadTags();
  const count = listing.tags.length;
  $("tags-status").textContent =
    `${count.toLocaleString()} ${count === 1 ? "tag" : "tags"}`;
  const grid = $("tags-grid");
  grid.replaceChildren();
  if (listing.tags.length === 0) {
    grid.append(el("p", "hint", "No tags yet. Add one from Photos."));
    return;
  }
  for (const tag of listing.tags) {
    const card = el("button", "tag-card");
    card.type = "button";
    const copy = el("span", "tag-copy");
    copy.append(el("span", "tag-name", tag.name),
      el("span", "tag-count", items(tag.count)));
    card.append(el("span", "tag-mark", "#"), copy);
    card.addEventListener("click", () => {
      selectTag(tag.id);
      show("photos");
    });
    grid.append(card);
  }
}

function healthRow(label, value, warning = false) {
  const row = el("div", "health-row");
  row.append(el("span", "", label), el("b", warning ? "health-warning" : "", String(value)));
  return row;
}

function healthPanel(title) {
  const panel = el("article", "card explore-panel");
  panel.append(el("h2", "", title));
  return panel;
}

async function loadHealth() {
  const jobs = [api("/api/status"), api("/api/storage"), api("/api/trash")];
  jobs.push(state.owner ? api("/api/backup") : Promise.resolve(null));
  const [status, storage, trash, backup] = await Promise.all(jobs);
  const trashBytes = trash.items.reduce((sum, item) => sum + item.size, 0);
  const cards = [
    ["Photos", status.count.toLocaleString()],
    ["Library size", bytes(status.bytes)],
    ["Free disk", bytes(status.disk.free)],
    ["Trash", trash.items.length.toLocaleString()],
    ["Missing", status.missing.length.toLocaleString()],
    ["Backup", backup === null ? "Owner only" : backup.configured ? "On" : "Off"],
  ];
  const cardsBox = $("health-cards");
  cardsBox.replaceChildren();
  for (const [label, value] of cards) {
    const card = el("div", "explore-card");
    card.append(el("span", "", label), el("b", "", value));
    cardsBox.append(card);
  }
  $("health-status").textContent =
    `${status.count.toLocaleString()} photos · ${bytes(status.bytes)}`
    + ` · ${trash.items.length.toLocaleString()} in trash`;
  const panels = $("health-panels");
  panels.replaceChildren();
  const library = healthPanel("Library");
  library.append(
    healthRow("Photos", storage.photos.toLocaleString()),
    healthRow("Videos", storage.videos.toLocaleString()),
    healthRow("Shared", storage.shared.toLocaleString()),
    healthRow("People", storage.people.length.toLocaleString()));
  for (const person of storage.people) {
    library.append(healthRow(`${personName(person.profile)} share`,
      `${items(person.count)} · ${bytes(person.bytes)}`));
  }
  panels.append(library);
  const disk = healthPanel("Disk");
  disk.append(healthRow("Free", bytes(status.disk.free), status.disk.low),
    healthRow("Total", bytes(status.disk.total)));
  if (status.disk.low) disk.append(el("p", "hint health-warning", "Free space is below the safe threshold."));
  panels.append(disk);
  const backupPanel = healthPanel("Backup");
  if (backup === null) {
    backupPanel.append(el("p", "hint", "Only the main profile can see the backup."));
  } else if (!backup.configured) {
    backupPanel.append(el("p", "hint", "No backup target configured."));
  } else {
    backupPanel.append(healthRow("Target", backup.target),
      healthRow("Last attempt", ago(backup.last_at)),
      healthRow("Copied", items(backup.copied)),
      healthRow("Unchanged", items(backup.unchanged)),
      healthRow("Bytes copied", bytes(backup.bytes)));
    if (backup.error) backupPanel.append(el("p", "hint health-warning", backup.error));
  }
  panels.append(backupPanel);
  const trashPanel = healthPanel("Trash");
  trashPanel.append(healthRow("Items", trash.items.length.toLocaleString()),
    healthRow("Bytes", bytes(trashBytes)));
  trashPanel.append(el("p", "hint", "Manage Trash from its own tab."));
  panels.append(trashPanel);
  const missingPanel = healthPanel("Missing reports");
  if (status.missing.length === 0) {
    missingPanel.append(el("p", "hint", "Nothing missing. Every checked photo is on the PC."));
  } else {
    for (const entry of status.missing.slice(0, 10)) {
      missingPanel.append(healthRow(
        entry.name || `${entry.sha256.slice(0, 12)}…`, ago(entry.reported_at)));
    }
  }
  panels.append(missingPanel);
  const previews = healthPanel("Previews");
  previews.append(healthRow("Thumbnails", status.previews ? "On" : "Off"));
  if (!status.previews) {
    previews.append(el("p", "hint", "Install Pillow and pillow-heif for HEIC thumbnails."));
  }
  panels.append(previews);
}

const ACTIVITY_LABELS = {
  stored: "Stored",
  duplicate: "Already present",
  rejected: "Rejected",
  sync_done: "Sync finished",
  missing: "Reported missing",
  scanned: "Folder scan",
  checked: "Library check",
  removed: "Removed",
  damaged: "Damaged",
};

async function loadActivity() {
  const data = await api("/api/activity?limit=100");
  const events = data.events || [];
  $("activity-status").textContent =
    `${events.length.toLocaleString()} recent ${events.length === 1 ? "event" : "events"}`;
  const list = $("activity-list");
  list.replaceChildren();
  if (events.length === 0) {
    list.append(el("li", "none", "No activity yet."));
    return;
  }
  const showPerson = state.people.length > 1;
  for (const event of events) {
    const row = el("li", "activity-item");
    const when = el("span", "activity-when", ago(event.at));
    when.title = event.at;
    const detail = event.detail
      || (event.sha256 ? `${event.sha256.slice(0, 12)}…` : "");
    row.append(when,
      el("span", "activity-kind", ACTIVITY_LABELS[event.kind] || event.kind),
      el("span", "activity-detail", detail));
    if (showPerson) row.append(el("span", "activity-person", personName(event.profile)));
    list.append(row);
  }
}

async function newTag() {
  const name = prompt("Name for the new tag:");
  if (!name) return;
  try {
    const tag = await post("/api/tags", { name });
    await loadTags();
    toast(`Tag “${tag.name}” created; open a photo to add it`);
  } catch (error) {
    handle(error);
  }
}

async function newAlbum() {
  const name = prompt("Name for the new album:");
  if (!name) return;
  try {
    const album = await post("/api/albums", { name });
    await loadAlbums();
    toast(`Album “${album.name}” created; open a photo to add it`);
  } catch (error) {
    handle(error);
  }
}

async function renameAlbum() {
  const album = currentAlbum();
  if (!album) return;
  const name = prompt("Rename this album:", album.name);
  if (!name || name.trim() === album.name) return;
  try {
    await post(`/api/albums/${album.id}`, { name });
    await loadAlbums();
    toast("Album renamed");
  } catch (error) {
    handle(error);
  }
}

async function deleteAlbum() {
  const album = currentAlbum();
  if (!album) return;
  if (!confirm(`Delete the album “${album.name}”? The photos stay in the library.`)) return;
  try {
    await post(`/api/albums/${album.id}`, { delete: true });
    state.scope = { kind: null, month: null, favorite: false, album: null, tag: null,
      place: null, camera: null, lens: null, day: null, archived: false,
      order: state.scope.order || "newest" };
    markScope();
    await loadAlbums();
    resetPhotos();
    toast("Album deleted; its photos are still in the library");
  } catch (error) {
    handle(error);
  }
}

function renderPeopleRail() {
  const rail = $("rail-people");
  rail.replaceChildren();
  if (state.people.length < 2) return;
  rail.append(el("h4", "rail-year", "People"));
  const total = state.people.reduce((sum, p) => sum + p.count, 0);
  rail.append(personButton(null, "Everyone", total));
  for (const person of state.people) rail.append(personButton(person.id, person.name, person.count));
}

// ---------- selecting many photos ----------

function clearSelected() {
  state.selected.clear();
  for (const item of document.querySelectorAll(".tile.selected")) item.classList.remove("selected");
  renderSelection();
}

function setSelecting(on) {
  state.selecting = on;
  $("select-mode").textContent = on ? "Done" : "Select";
  $("select-mode").setAttribute("aria-pressed", String(on));
  $("select-bar").hidden = !on;
  if (on) renderSelection();
  else clearSelected();
}

function toggleSelected(sha256) {
  if (state.selected.has(sha256)) state.selected.delete(sha256);
  else state.selected.add(sha256);
  for (const item of document.querySelectorAll(`.tile[data-sha="${sha256}"]`)) {
    item.classList.toggle("selected", state.selected.has(sha256));
  }
  renderSelection();
}

function updateTileFavorite(photo) {
  const button = document.querySelector(`.tile[data-sha="${photo.sha256}"]`);
  if (!button) return;
  const heart = button.querySelector(".heart");
  if (photo.favorite && !heart) button.append(favoriteMark());
  if (!photo.favorite && heart) heart.remove();
}

function hideSelectAlbums() {
  $("select-albums").hidden = true;
  $("select-album").setAttribute("aria-expanded", "false");
}

function hideSelectTags() {
  $("select-tags").hidden = true;
  $("select-tag").setAttribute("aria-expanded", "false");
}

function hideSelectSidecars() {
  $("select-sidecars").hidden = true;
  $("select-sidecar").setAttribute("aria-expanded", "false");
}

function renderSelection() {
  const count = state.selected.size;
  $("select-count").textContent = `${count.toLocaleString()} selected`;
  $("select-archive").textContent = state.scope.archived ? "Unarchive" : "Archive";
  for (const id of ["select-favorite", "select-unfavorite", "select-download", "select-trash",
    "select-album", "select-tag", "select-sidecar", "select-archive", "select-clear"]) {
    $(id).disabled = count === 0;
  }
  if (count === 0) {
    hideSelectAlbums();
    hideSelectTags();
    hideSelectSidecars();
  }
}

function selectLoaded() {
  for (const photo of state.photos) state.selected.add(photo.sha256);
  for (const item of document.querySelectorAll(".tile")) item.classList.add("selected");
  renderSelection();
}

async function selectMatching() {
  try {
    const found = await api(`/api/photos/hashes?${filterParams()}`);
    for (const sha256 of found.hashes) state.selected.add(sha256);
    for (const item of document.querySelectorAll(".tile")) item.classList.add("selected");
    renderSelection();
    toast(found.truncated
      ? "Selected the first 10,000 matching photos; narrow the filters for the rest"
      : `Selected ${found.hashes.length.toLocaleString()} matching photos`);
  } catch (error) {
    handle(error);
  }
}

function batches(items) {
  const out = [];
  for (let start = 0; start < items.length; start += BATCH) {
    out.push(items.slice(start, start + BATCH));
  }
  return out;
}

async function bulkFavorite(favorite) {
  const sha256s = [...state.selected];
  if (sha256s.length === 0) return;
  try {
    let changed = 0;
    for (const batch of batches(sha256s)) {
      changed += (await post("/api/favorite", { sha256s: batch, favorite })).changed;
    }
    for (const photo of state.photos) {
      if (!state.selected.has(photo.sha256)) continue;
      photo.favorite = favorite;
      updateTileFavorite(photo);
    }
    await loadAlbums();
    toast(`${changed} photo${changed === 1 ? "" : "s"} ${favorite ? "added to" : "removed from"} Favorites`);
    if (state.scope.favorite && !favorite) {
      setSelecting(false);
      resetPhotos();
    }
  } catch (error) {
    handle(error);
  }
}

async function bulkArchive(archived) {
  const sha256s = [...state.selected];
  if (sha256s.length === 0) return;
  try {
    let changed = 0;
    for (const batch of batches(sha256s)) {
      changed += (await post("/api/archive", { sha256s: batch, archived })).changed;
    }
    const leaving = archived !== Boolean(state.scope.archived);
    await Promise.all([loadOutline(), loadTags()]);
    if (leaving) {
      setSelecting(false);
      closeViewer();
      resetPhotos();
    }
    toast(`${items(changed)} ${archived ? "archived" : "restored"}`);
  } catch (error) {
    handle(error);
  }
}

async function bulkAlbum(album) {
  const sha256s = [...state.selected];
  if (sha256s.length === 0) return;
  try {
    let changed = 0;
    for (const batch of batches(sha256s)) {
      changed += (await post("/api/album-photos",
        { album: album.id, sha256s: batch, member: true })).changed;
    }
    hideSelectAlbums();
    toast(`${changed} photo${changed === 1 ? "" : "s"} added to “${album.name}”`);
    await loadAlbums();
  } catch (error) {
    handle(error);
  }
}

async function bulkTag(tag) {
  const sha256s = [...state.selected];
  if (sha256s.length === 0) return;
  try {
    let changed = 0;
    for (const batch of batches(sha256s)) {
      changed += (await post("/api/photo-tags",
        { tag: tag.id, sha256s: batch, member: true })).changed;
    }
    hideSelectTags();
    toast(`${changed} photo${changed === 1 ? "" : "s"} tagged “${tag.name}”`);
    await loadTags();
  } catch (error) {
    handle(error);
  }
}

async function createTagForSelection() {
  const name = prompt("Name for the new tag:");
  if (!name) return;
  try {
    const tag = await post("/api/tags", { name });
    await loadTags();
    await bulkTag(tag);
  } catch (error) {
    handle(error);
  }
}

async function startDownload(payload, button) {
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Preparing…";
  try {
    const result = await post("/api/download", payload);
    toast(`Preparing ${result.count.toLocaleString()} photo${result.count === 1 ? "" : "s"}…`);
    window.location.href = result.url;
  } catch (error) {
    handle(error);
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

async function downloadSidecars(sha256s, format) {
  if (sha256s.length === 0) return;
  try {
    const response = await fetch("/api/sidecar", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sha256s, format }),
    });
    if (response.status === 401) throw new Unauthorised();
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `harbor-sidecars-${format}.zip`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast(`Exported ${items(sha256s.length)} as ${format.toUpperCase()} sidecars`);
  } catch (error) {
    handle(error);
  }
}

function sidecarCurrent() {
  const photo = state.photos[state.viewing];
  if (photo) downloadSidecars([photo.sha256], "json");
}

function downloadSelection() {
  if (state.selected.size === 0) return;
  if (state.selected.size > BATCH) {
    toast(`Download at most ${BATCH} photos at once; add them to an album for a larger set`);
    return;
  }
  startDownload({ sha256s: [...state.selected] }, $("select-download"));
}

function downloadAlbum() {
  const album = currentAlbum();
  if (!album) return;
  startDownload({ album: album.id }, $("album-download"));
}

// ---------- trash ----------

async function loadTrash() {
  const data = await api("/api/trash");
  $("trash-count").textContent = items(data.items.length);
  const list = $("trash-list");
  list.replaceChildren();
  if (data.items.length === 0) {
    list.append(el("li", "none", "Trash is empty."));
    return;
  }
  for (const item of data.items) {
    const row = el("li");
    row.append(el("span", "trash-name", item.name),
      el("span", "hint", `${bytes(item.size)} · ${ago(item.trashed)}`));
    const actions = el("div", "trash-actions");
    const restore = el("button", "ghost", "Restore");
    restore.type = "button";
    restore.addEventListener("click", () => restoreTrash(item.id));
    const remove = el("button", "ghost", "Delete forever");
    remove.type = "button";
    remove.addEventListener("click", () => deleteTrash(item));
    actions.append(restore, remove);
    row.append(actions);
    list.append(row);
  }
}

async function trashPhotos(sha256s) {
  if (sha256s.length === 0) return;
  if (!confirm(`Move ${items(sha256s.length)} to Trash? You can restore them from the Trash tab.`)) return;
  try {
    let moved = 0;
    for (const batch of batches(sha256s)) {
      moved += (await post("/api/trash", { sha256s: batch })).moved;
    }
    setSelecting(false);
    closeViewer();
    resetPhotos();
    await Promise.all([loadAlbums(), loadOutline(), loadTags(), refreshStatus()]);
    toast(`${items(moved)} moved to Trash`);
    if (!$("view-trash").hidden) loadTrash().catch(handle);
  } catch (error) {
    handle(error);
  }
}

function trashCurrent() {
  const photo = state.photos[state.viewing];
  if (photo) trashPhotos([photo.sha256]);
}

async function restoreTrash(id) {
  try {
    await post(`/api/trash/${id}`, { restore: true });
    await Promise.all([loadTrash(), loadOutline(), loadAlbums(), loadTags(), refreshStatus()]);
    resetPhotos();
    toast("Photo restored");
  } catch (error) {
    handle(error);
  }
}

async function deleteTrash(item) {
  if (!confirm(`Delete “${item.name}” forever? This cannot be undone.`)) return;
  try {
    await post(`/api/trash/${item.id}`, { delete: true });
    await loadTrash();
    toast("Deleted forever");
  } catch (error) {
    handle(error);
  }
}

async function emptyTrash() {
  if (!confirm("Delete everything in Trash forever? This cannot be undone.")) return;
  try {
    const result = await post("/api/trash/empty", {});
    await loadTrash();
    toast(`${items(result.deleted)} deleted forever`);
  } catch (error) {
    handle(error);
  }
}

async function loadSimilar() {
  const data = await api("/api/similar");
  const status = data.status;
  $("similar-threshold").textContent = data.threshold;
  $("similar-status").textContent =
    `${status.indexed.toLocaleString()} hashed · ${status.grouped.toLocaleString()} grouped`
    + ` · ${status.ungrouped.toLocaleString()} waiting · ${status.missing.toLocaleString()} unscanned`
    + ` · ${status.skipped.toLocaleString()} skipped`
    + (data.building ? " · grouping…" : data.build_error ? ` · ${data.build_error}` : "");
  const build = $("similar-build");
  build.disabled = data.building;
  build.textContent = data.building ? "Grouping…" : "Build groups";
  clearTimeout(state.similarTimer);
  state.similarTimer = null;
  if (data.building) {
    state.similarTimer = setTimeout(() => loadSimilar().catch(handle), 2000);
  }
  const box = $("similar-groups");
  box.replaceChildren();
  if (data.groups.length === 0) {
    box.append(el("p", "hint", status.missing
      ? "No matching groups yet. Press Scan library to index more photos."
      : status.ungrouped
        ? "Hashes are ready. Press Build groups to group them."
        : "No similar photos found in the indexed photos."));
    return;
  }
  for (const group of data.groups) {
    const card = el("article", "card similar-group");
    const head = el("div", "similar-group-head");
    head.append(el("h2", "", `${group.count.toLocaleString()} similar photos`));
    const compare = el("button", "ghost", "Compare side by side");
    compare.type = "button";
    compare.addEventListener("click", () => openCompare(group));
    head.append(compare);
    card.append(head);
    const grid = el("div", "similar-grid");
    for (const photo of group.photos) {
      const link = el("a", "similar-photo");
      link.href = photo.media;
      link.target = "_blank";
      link.rel = "noopener";
      const img = el("img");
      img.src = photo.thumb;
      img.alt = photo.name;
      img.loading = "lazy";
      link.append(img, el("span", "", photo.name));
      grid.append(link);
    }
    card.append(grid);
    box.append(card);
  }
}

async function scanSimilar() {
  const button = $("similar-scan");
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Scanning…";
  let processed = 0;
  let indexed = 0;
  let skipped = 0;
  let status = null;
  try {
    for (let batch = 0; batch < 100; batch += 1) {
      const result = await post("/api/similar/scan", { limit: 100 });
      processed += result.processed;
      indexed += result.indexed;
      skipped += result.skipped;
      status = result.status;
      $("similar-status").textContent = `Scanned ${processed.toLocaleString()}…`
        + ` ${status.missing.toLocaleString()} unscanned`;
      if (result.processed === 0 || status.missing === 0) break;
    }
    await loadSimilar();
    if (status && status.ungrouped > 0) await startSimilarBuild();
    toast(`Scanned ${processed.toLocaleString()}; ${indexed.toLocaleString()} hashed,`
      + ` ${skipped.toLocaleString()} skipped`);
  } catch (error) {
    handle(error);
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

function openCompare(group) {
  state.compareReturnFocus = document.activeElement;
  const stage = $("compare-stage");
  stage.replaceChildren();
  for (const photo of group.photos) {
    const figure = el("figure", "compare-item");
    const img = el("img");
    img.src = photo.media;
    img.alt = photo.name;
    img.loading = "eager";
    const caption = el("figcaption");
    caption.append(el("b", "", photo.name),
      el("span", "", parseTime(photo.time) ? timeFormat.format(parseTime(photo.time)) : ""));
    figure.append(img, caption);
    stage.append(figure);
  }
  $("similar-compare").hidden = false;
  document.body.style.overflow = "hidden";
  $("compare-close").focus();
}

function closeCompare() {
  const target = state.compareReturnFocus;
  state.compareReturnFocus = null;
  $("similar-compare").hidden = true;
  $("compare-stage").replaceChildren();
  document.body.style.overflow = "";
  if (target && target.isConnected) target.focus();
}

async function startSimilarBuild() {
  try {
    await post("/api/similar/build", {});
    await loadSimilar();
  } catch (error) {
    handle(error);
  }
}

function mapPoint(lat, lon) {
  return [((Number(lon) + 180) / 360) * 800, ((90 - Number(lat)) / 180) * 400];
}

async function loadMap() {
  const query = state.profile ? `?profile=${encodeURIComponent(state.profile)}` : "";
  const data = await api(`/api/outline${query}`);
  const places = data.places || [];
  const points = $("map-points");
  points.replaceChildren();
  const list = $("map-list");
  list.replaceChildren();
  const total = places.reduce((sum, place) => sum + place.count, 0);
  $("map-status").textContent =
    `${places.length.toLocaleString()} places · ${total.toLocaleString()} photos`;
  if (places.length === 0) {
    list.append(el("li", "none", "No GPS places yet. Upload a photo with EXIF GPS."));
    return;
  }
  for (const place of places) {
    const [x, y] = mapPoint(place.lat, place.lon);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", x.toFixed(1));
    circle.setAttribute("cy", y.toFixed(1));
    circle.setAttribute("r", String(4 + Math.min(place.count, 10)));
    circle.setAttribute("class", "map-point");
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${placeLabel(place.key)} · ${place.count} photos`;
    circle.append(title);
    points.append(circle);
    const item = el("li");
    const button = el("button", "map-place",
      `${placeLabel(place.key)} · ${items(place.count)}`);
    button.type = "button";
    button.addEventListener("click", () => {
      selectPlace(place.key);
      show("photos");
    });
    item.append(button);
    list.append(item);
  }
}

async function loadFolders() {
  const data = await api("/api/folders");
  const box = $("folders-tree");
  box.replaceChildren();
  let months = 0;
  for (const folder of data.folders) {
    months += folder.months.length;
    const card = el("article", "card folder-person");
    const label = folder.folder && folder.folder !== folder.name
      ? `${folder.name} · ${folder.folder}` : folder.name;
    card.append(el("h2", "", label));
    const years = new Map();
    for (const month of folder.months) {
      const year = month.month.slice(0, 4);
      if (!years.has(year)) years.set(year, []);
      years.get(year).push(month);
    }
    for (const [year, entries] of years) {
      card.append(el("h3", "", year));
      const row = el("div", "folder-months");
      for (const month of entries) {
        const button = el("button", "folder-month");
        button.type = "button";
        button.title = month.path;
        const monthLabel = capitalise(monthYearFormat.format(monthDate(month.month)));
        button.setAttribute("aria-label", `${monthLabel}, ${items(month.count)}`);
        button.append(
          el("span", "", monthLabel),
          el("b", "", month.count.toLocaleString()));
        button.addEventListener("click", () => openFolder(folder.profile, month.month));
        row.append(button);
      }
      card.append(row);
    }
    box.append(card);
  }
  const people = data.folders.length;
  $("folders-status").textContent = people
    ? `${people.toLocaleString()} ${people === 1 ? "person" : "people"} ·`
      + ` ${months.toLocaleString()} ${months === 1 ? "month" : "months"}`
    : "No folders yet";
  if (data.folders.length === 0) {
    box.append(el("p", "hint", "No folders have photos yet."));
  }
}

function openFolder(profileId, month) {
  state.profile = profileId;
  for (const item of document.querySelectorAll("[data-person]")) {
    item.setAttribute("aria-pressed", String(item.dataset.person === profileId));
  }
  setScope(null, month);
  loadOutline().catch(handle);
  show("photos");
}

function explorePanel(title) {
  const panel = el("article", "card explore-panel");
  panel.append(el("h2", "", title));
  return panel;
}

function exploreList(title, items, label, count, action) {
  const panel = explorePanel(title);
  if (!items || items.length === 0) {
    panel.append(el("p", "hint", "None yet."));
    return panel;
  }
  for (const item of items) {
    const button = el("button", "explore-row explore-link");
    button.type = "button";
    button.append(el("span", "", label(item)),
      el("b", "", count(item).toLocaleString()));
    button.addEventListener("click", () => {
      action(item);
      show("photos");
    });
    panel.append(button);
  }
  return panel;
}

async function loadExplore() {
  const query = state.profile ? `?profile=${encodeURIComponent(state.profile)}` : "";
  const outline = await api(`/api/outline${query}`);
  const months = outline.months || [];
  const years = new Map();
  for (const month of months) {
    const year = month.month.slice(0, 4);
    years.set(year, (years.get(year) || 0) + month.count);
  }
  const cards = [
    ["Photos", outline.total],
    ["Favorites", outline.favorites],
    ["Videos", outline.videos],
    ["Archived", outline.archived],
    ["Years", years.size],
    ["Months", months.length],
    ["Places", outline.places?.length || 0],
    ["Cameras", outline.cameras?.length || 0],
    ["Lenses", outline.lenses?.length || 0],
  ];
  const cardsBox = $("explore-cards");
  cardsBox.replaceChildren();
  for (const [label, value] of cards) {
    const card = el("div", "explore-card");
    card.append(el("span", "", label), el("b", "", Number(value || 0).toLocaleString()));
    cardsBox.append(card);
  }
  $("explore-status").textContent =
    `${Number(outline.total || 0).toLocaleString()} photos · ${months.length.toLocaleString()} months`
    + ` · ${years.size.toLocaleString()} years`;
  const sections = $("explore-sections");
  sections.replaceChildren();
  const yearPanel = explorePanel("Years");
  if (years.size === 0) {
    yearPanel.append(el("p", "hint", "No dated photos yet."));
  } else {
    const largest = Math.max(...years.values(), 1);
    for (const [year, count] of years) {
      const row = el("div", "explore-row");
      const track = el("div", "explore-track");
      const fill = el("i", "explore-fill");
      fill.style.width = `${Math.max(2, (count / largest) * 100)}%`;
      track.append(fill);
      row.append(el("span", "", year), el("b", "", count.toLocaleString()), track);
      yearPanel.append(row);
    }
  }
  sections.append(yearPanel);
  sections.append(exploreList("Places", outline.places, (item) => placeLabel(item.key),
    (item) => item.count, (item) => selectPlace(item.key)));
  sections.append(exploreList("Cameras", outline.cameras, (item) => item.name,
    (item) => item.count, (item) => selectCamera(item.name)));
  sections.append(exploreList("Lenses", outline.lenses, (item) => item.name,
    (item) => item.count, (item) => selectLens(item.name)));
}

async function createAlbumForSelection() {
  const name = prompt("Name for the new album:");
  if (!name) return;
  try {
    const album = await post("/api/albums", { name });
    await bulkAlbum(album);
  } catch (error) {
    handle(error);
  }
}

function toggleSelectAlbums() {
  const box = $("select-albums");
  if (!box.hidden) {
    hideSelectAlbums();
    return;
  }
  hideSelectTags();
  hideSelectSidecars();
  box.replaceChildren();
  const create = el("button", "ghost", "New album…");
  create.type = "button";
  create.setAttribute("role", "menuitem");
  create.addEventListener("click", createAlbumForSelection);
  box.append(create);
  for (const album of state.albums) {
    const button = el("button", "ghost", album.name);
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.addEventListener("click", () => bulkAlbum(album));
    box.append(button);
  }
  box.hidden = false;
  $("select-album").setAttribute("aria-expanded", "true");
}

function toggleSelectTags() {
  const box = $("select-tags");
  if (!box.hidden) {
    hideSelectTags();
    return;
  }
  hideSelectAlbums();
  hideSelectSidecars();
  box.replaceChildren();
  const create = el("button", "ghost", "New tag…");
  create.type = "button";
  create.setAttribute("role", "menuitem");
  create.addEventListener("click", createTagForSelection);
  box.append(create);
  for (const tag of state.tags) {
    const button = el("button", "ghost", tag.name);
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.addEventListener("click", () => bulkTag(tag));
    box.append(button);
  }
  box.hidden = false;
  $("select-tag").setAttribute("aria-expanded", "true");
}

function toggleSelectSidecars() {
  const box = $("select-sidecars");
  if (!box.hidden) {
    hideSelectSidecars();
    return;
  }
  hideSelectAlbums();
  hideSelectTags();
  box.hidden = false;
  $("select-sidecar").setAttribute("aria-expanded", "true");
}

function keyRow(person) {
  const row = el("div", "person");
  const code = el("code", "", person.key);
  const copy = el("button", "ghost", "Copy key");
  copy.type = "button";
  copy.addEventListener("click", () => copyText(person.key));
  row.append(el("b", "", person.name), code, copy);
  const tools = el("div", "person-tools");
  if (state.owner) {
    const path = `/api/profiles/${encodeURIComponent(person.id)}`;
    tools.append(toolButton("Password", () => inlineEdit(row, "password", `New password for ${person.name}`,
      (value) => post(path, { password: value }).then(() => toast(`${person.name} can now sign in with it`)))));
    tools.append(toolButton("Rename", () => inlineEdit(row, "text", person.name,
      (value) => post(path, { name: value }).then(() => toast(`Renamed; their folder is now "${value}"`)))));
    if (person.id !== "main") {
      tools.append(toolButton("New key", async () => {
        if (!confirm(`Give ${person.name} a new key? Their Shortcut stops working until it gets the new one.`)) return;
        await post(path, { new_key: true }).catch(handle);
        loadPeople().catch(handle);
      }));
    }
  }
  row.append(tools);
  row.title = `Folder: ${person.folder}`;
  return row;
}

function toolButton(label, action) {
  const button = el("button", "ghost", label);
  button.type = "button";
  button.addEventListener("click", action);
  return button;
}

// A one-line form under a person's row: Save runs ``save(value)`` and reloads the list.
function inlineEdit(row, type, placeholder, save) {
  row.querySelector(".inline-edit")?.remove();
  const form = el("form", "inline-edit");
  const input = el("input");
  input.type = type;
  input.placeholder = placeholder;
  if (type === "text") input.value = placeholder;
  input.required = true;
  const ok = el("button", "primary", "Save");
  const cancel = toolButton("Cancel", () => form.remove());
  form.append(input, ok, cancel);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await save(input.value.trim());
      form.remove();
      await loadPeople();
    } catch (error) {
      handle(error);
    }
  });
  row.append(form);
  input.focus();
}

function renderPeopleSetup() {
  const list = $("setup-people");
  list.replaceChildren(...state.people.filter((p) => p.key).map(keyRow));
  $("add-person").hidden = !state.owner;
  const me = state.people.find((p) => p.id === state.me);
  if (me) {
    $("account-name").textContent = me.name;
    $("account-avatar").textContent = initials(me.name);
    $("pw-current").hidden = !me.has_password;
    $("pw-current").required = me.has_password;
    $("pw-hint").textContent = me.has_password ? "Changing it signs you out on your other devices."
      : "You have no password yet: choose one so you can sign in with your name.";
  }
  const sync = $("sync-people");
  sync.replaceChildren();
  for (const person of state.people) {
    const row = el("li");
    row.append(el("span", "", `${person.name} · ${items(person.count)}`),
      el("span", "hint", `synced ${ago(person.last_sync)}`));
    sync.append(row);
  }
}

async function loadPeople() {
  const listing = await api("/api/profiles");
  state.people = listing.profiles;
  state.me = listing.me;
  state.owner = listing.owner;
  renderPeopleRail();
  renderPeopleSetup();
  renderScope();
  return listing;
}

async function loadPeopleOverview() {
  const listing = await loadPeople();
  const count = listing.profiles.length;
  $("people-status").textContent =
    `${count.toLocaleString()} ${count === 1 ? "person" : "people"}`;
  const grid = $("people-grid");
  grid.replaceChildren();
  for (const person of listing.profiles) {
    const card = el("button", "people-card");
    card.type = "button";
    const copy = el("span", "people-copy");
    copy.append(el("span", "people-name", person.name),
      el("span", "people-meta", `${person.folder} · ${items(person.count)} · ${bytes(person.bytes)}`),
      el("span", "people-meta", `synced ${ago(person.last_sync)}`));
    card.append(el("span", "people-avatar", initials(person.name)), copy);
    card.addEventListener("click", () => {
      selectPerson(person.id);
      show("photos");
    });
    grid.append(card);
  }
}

function wirePeople() {
  $("add-person").addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = $("add-person-name").value.trim();
    if (!name) return;
    try {
      const added = await api("/api/profiles", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
      });
      $("add-person-name").value = "";
      toast(`${added.name} added. Copy their key into their Shortcut.`);
      await loadPeople();
    } catch (error) {
      handle(error);
    }
  });
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied");
  } catch (_) {
    toast("Select the text and copy it by hand");
  }
}

function wireBrowser() {
  document.querySelector('[data-scope="all"]').addEventListener("click", () => setScope(null, null));
  document.querySelector('[data-scope="video"]').addEventListener("click", () => setScope("video", null));
  document.querySelector('[data-scope="favorite"]').addEventListener("click", selectFavorites);
  document.querySelector('[data-scope="memories"]').addEventListener("click", selectMemories);
  document.querySelector('[data-scope="archive"]').addEventListener("click", selectArchive);
  $("select-archive").addEventListener("click", () => bulkArchive(!state.scope.archived));
  $("album-new").addEventListener("click", newAlbum);
  $("tag-new").addEventListener("click", newTag);
  $("album-rename").addEventListener("click", renameAlbum);
  $("album-delete").addEventListener("click", deleteAlbum);
  $("album-download").addEventListener("click", downloadAlbum);
  $("trash-empty").addEventListener("click", emptyTrash);
  $("date-filter").addEventListener("click", toggleDatePanel);
  $("date-apply").addEventListener("click", applyDates);
  $("date-clear").addEventListener("click", clearDates);
  $("scrubber-year").addEventListener("change", (event) => {
    const target = state.months.find((month) => month.month.startsWith(`${event.target.value}-`));
    if (target) jumpToMonth(target.month);
  });
  $("scrubber-month").addEventListener("change", (event) => jumpToMonth(event.target.value));
  $("scrubber-newer").addEventListener("click", () => stepScrubber(-1));
  $("scrubber-older").addEventListener("click", () => stepScrubber(1));
  $("sort-order").addEventListener("change", (event) => {
    state.scope = { ...state.scope, order: event.target.value };
    window.scrollTo({ top: 0 });
    resetPhotos();
  });
  $("select-mode").addEventListener("click", () => setSelecting(!state.selecting));
  $("select-all").addEventListener("click", selectLoaded);
  $("select-matching").addEventListener("click", selectMatching);
  $("select-clear").addEventListener("click", clearSelected);
  $("select-favorite").addEventListener("click", () => bulkFavorite(true));
  $("select-unfavorite").addEventListener("click", () => bulkFavorite(false));
  $("select-download").addEventListener("click", downloadSelection);
  $("select-trash").addEventListener("click", () => trashPhotos([...state.selected]));
  $("select-album").addEventListener("click", toggleSelectAlbums);
  $("select-tag").addEventListener("click", toggleSelectTags);
  $("select-sidecar").addEventListener("click", toggleSelectSidecars);
  $("sidecar-json").addEventListener("click", () => {
    hideSelectSidecars();
    downloadSidecars([...state.selected], "json");
  });
  $("sidecar-xmp").addEventListener("click", () => {
    hideSelectSidecars();
    downloadSidecars([...state.selected], "xmp");
  });
  $("similar-scan").addEventListener("click", scanSimilar);
  $("similar-build").addEventListener("click", startSimilarBuild);
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".select-album-wrap")) {
      hideSelectAlbums();
      hideSelectTags();
      hideSelectSidecars();
    }
    if (!event.target.closest("#date-panel") && event.target.id !== "date-filter") {
      hideDatePanel();
    }
  });
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
      resetPhotos();
    }, 250);
  });
}

// ---------- uploads from the browser ----------

const uploads = { queue: [], running: false, done: 0, total: 0, stored: 0 };
// A few uploads at once hide per-file latency for many small photos; big videos share the link.
const PARALLEL_UPLOADS = 3;

function uploadOne(item) {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open("POST", "/api/upload");
    // Header values must be Latin-1, so the name travels percent-encoded.
    request.setRequestHeader("X-Name", encodeURIComponent(item.file.name));
    if (item.profile) request.setRequestHeader("X-Profile", item.profile);
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
    ? `Uploading · ${uploads.done} of ${uploads.total} done · to ${personName(uploadTarget() || state.me)}`
    : `${uploads.stored} added · ${uploads.total - uploads.stored} skipped or failed`;
  $("uploads-progress").style.width = `${uploads.total ? (uploads.done / uploads.total) * 100 : 0}%`;
}

async function runUploads() {
  if (uploads.running) return;
  uploads.running = true;
  const lane = async () => {
    while (uploads.queue.length) {
      renderUploads();
      await uploadOne(uploads.queue.shift());
      uploads.done += 1;
    }
  };
  await Promise.all(Array.from({ length: PARALLEL_UPLOADS }, lane));
  uploads.running = false;
  renderUploads();
  if (uploads.stored) {
    toast(`${uploads.stored} added to Harbor`);
    refreshStatus().catch(handle);
    loadPeople().catch(handle);
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
    uploads.queue.push({ file, row, state: label, profile: uploadTarget() });
  }
  uploads.total += media.length;
  $("uploads").hidden = false;
  runUploads();
}

// The owner uploads into whichever person is selected; everyone else into their own profile.
function uploadTarget() {
  return state.owner && state.profile ? state.profile : null;
}

function toggleUploadMenu(open) {
  $("upload-menu").hidden = !open;
  $("upload-button").setAttribute("aria-expanded", String(open));
  if (open) $("upload-target").textContent = `Goes to ${personName(uploadTarget() || state.me)}`;
}

function wireUploads() {
  $("upload-button").addEventListener("click", (event) => {
    event.stopPropagation();
    toggleUploadMenu($("upload-menu").hidden);
  });
  document.addEventListener("click", () => toggleUploadMenu(false));
  $("pick-files").addEventListener("click", () => $("upload-input").click());
  $("pick-folder").addEventListener("click", () => $("upload-folder").click());
  // iPhone and iPad Safari cannot pick a folder; they offer the photo library instead.
  $("pick-folder").hidden = /iPhone|iPad|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  for (const input of [$("upload-input"), $("upload-folder")]) {
    input.addEventListener("change", (event) => {
      enqueue(event.target.files);
      event.target.value = "";
    });
  }
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
  if (state.viewing < 0) state.viewerReturnFocus = document.activeElement;
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
  $("viewer-next").disabled = index === state.photos.length - 1 && state.next === null;
  renderViewerCollections();
  hideDetails();
  $("viewer").hidden = false;
  document.body.style.overflow = "hidden";
  $("viewer-close").focus();
}

function renderViewerCollections() {
  const photo = state.photos[state.viewing];
  const favorite = $("viewer-favorite");
  favorite.textContent = photo?.favorite ? "♥ Favorited" : "♡ Favorite";
  favorite.setAttribute("aria-pressed", String(Boolean(photo?.favorite)));
  $("viewer-album-add").hidden = !photo || state.albums.length === 0;
  $("viewer-album-remove").hidden = !photo || !state.scope.album;
  $("viewer-cover").hidden = !photo || !state.scope.album;
  $("viewer-archive").textContent = state.scope.archived ? "Unarchive" : "Archive";
  $("viewer-tag-add").hidden = !photo;
  $("viewer-tag-add").setAttribute("aria-expanded", "false");
  $("viewer-albums").hidden = true;
  $("viewer-albums").replaceChildren();
  $("viewer-tags").hidden = true;
  $("viewer-tags").replaceChildren();
}

function hideDetails() {
  $("viewer-details").hidden = true;
  $("viewer-details").replaceChildren();
  $("viewer-info").textContent = "Details";
  $("viewer-info").setAttribute("aria-expanded", "false");
}

function renderDetails(details) {
  const rows = [
    ["File", details.name],
    ["Type", details.type],
    ["Size", bytes(details.size)],
    ["Taken", details.taken ? timeFormat.format(parseTime(details.taken)) : "Not recorded"],
    ["Added", details.received ? timeFormat.format(parseTime(details.received)) : null],
    ["Location", details.latitude !== null && details.longitude !== null
      ? `${Number(details.latitude).toFixed(4)}, ${Number(details.longitude).toFixed(4)}` : null],
    ["Dimensions", details.width && details.height ? `${details.width} × ${details.height}` : null],
    ["Camera", details.camera],
    ["Lens", details.lens],
    ["Exposure", details.exposure],
    ["Aperture", details.aperture],
    ["ISO", details.iso],
    ["Focal length", details.focal_length],
  ];
  const list = el("dl");
  for (const [label, value] of rows) {
    if (value === null || value === undefined || value === "") continue;
    list.append(el("dt", "", label), el("dd", "", String(value)));
  }
  $("viewer-details").replaceChildren(list);
}

async function toggleDetails() {
  const box = $("viewer-details");
  if (!box.hidden) {
    hideDetails();
    return;
  }
  const photo = state.photos[state.viewing];
  if (!photo) return;
  try {
    const details = await api(`/api/details/${photo.sha256}`);
    renderDetails(details);
    $("viewer-albums").hidden = true;
    $("viewer-albums").replaceChildren();
    $("viewer-tags").hidden = true;
    $("viewer-tags").replaceChildren();
    $("viewer-tag-add").setAttribute("aria-expanded", "false");
    $("viewer-album-add").setAttribute("aria-expanded", "false");
    box.hidden = false;
    $("viewer-info").textContent = "Hide details";
    $("viewer-info").setAttribute("aria-expanded", "true");
  } catch (error) {
    handle(error);
  }
}

async function toggleFavorite() {
  const photo = state.photos[state.viewing];
  if (!photo) return;
  try {
    const result = await post("/api/favorite", { sha256: photo.sha256, favorite: !photo.favorite });
    photo.favorite = result.favorite;
    renderViewerCollections();
    updateTileFavorite(photo);
    await loadAlbums();
    if (state.scope.favorite && !photo.favorite) {
      closeViewer();
      resetPhotos();
    }
    toast(photo.favorite ? "Added to Favorites" : "Removed from Favorites");
  } catch (error) {
    handle(error);
  }
}

async function toggleArchiveCurrent() {
  const photo = state.photos[state.viewing];
  if (!photo) return;
  const archived = !state.scope.archived;
  try {
    await post("/api/archive", { sha256: photo.sha256, archived });
    const leaving = archived !== Boolean(state.scope.archived);
    await Promise.all([loadOutline(), loadTags()]);
    if (leaving) {
      closeViewer();
      resetPhotos();
    }
    toast(archived ? "Moved to Archive" : "Restored from Archive");
  } catch (error) {
    handle(error);
  }
}

function toggleAlbumMenu() {
  const box = $("viewer-albums");
  if (!box.hidden) {
    box.hidden = true;
    return;
  }
  hideDetails();
  $("viewer-tags").hidden = true;
  $("viewer-tag-add").setAttribute("aria-expanded", "false");
  const photo = state.photos[state.viewing];
  if (!photo) return;
  box.replaceChildren();
  for (const album of state.albums) {
    const button = el("button", "ghost", album.name);
    button.type = "button";
    button.addEventListener("click", async () => {
      try {
        const result = await post("/api/album-photos",
          { album: album.id, sha256: photo.sha256, member: true });
        box.hidden = true;
        toast(result.changed ? `Added to “${album.name}”` : `Already in “${album.name}”`);
        await loadAlbums();
      } catch (error) {
        handle(error);
      }
    });
    box.append(button);
  }
  box.hidden = false;
}

async function toggleTagMenu() {
  const box = $("viewer-tags");
  if (!box.hidden) {
    box.hidden = true;
    $("viewer-tag-add").setAttribute("aria-expanded", "false");
    return;
  }
  hideDetails();
  $("viewer-albums").hidden = true;
  const photo = state.photos[state.viewing];
  if (!photo) return;
  try {
    const listing = await api(`/api/tags?sha256=${photo.sha256}`);
    box.replaceChildren();
    const create = el("button", "ghost", "New tag…");
    create.type = "button";
    create.addEventListener("click", createViewerTag);
    box.append(create);
    for (const tag of listing.tags) {
      const button = el("button", "ghost", `${tag.member ? "✓ " : ""}${tag.name}`);
      button.type = "button";
      button.addEventListener("click", async () => {
        try {
          const result = await post("/api/photo-tags",
            { tag: tag.id, sha256: photo.sha256, member: !tag.member });
          box.hidden = true;
          $("viewer-tag-add").setAttribute("aria-expanded", "false");
          await loadTags();
          if (state.scope.tag === tag.id && tag.member) {
            closeViewer();
            resetPhotos();
          }
          toast(result.changed
            ? `${tag.member ? "Removed" : "Added"} tag “${tag.name}”`
            : `Already ${tag.member ? "without" : "with"} “${tag.name}”`);
        } catch (error) {
          handle(error);
        }
      });
      box.append(button);
    }
    box.hidden = false;
    $("viewer-tag-add").setAttribute("aria-expanded", "true");
  } catch (error) {
    handle(error);
  }
}

async function createViewerTag() {
  const photo = state.photos[state.viewing];
  if (!photo) return;
  const name = prompt("Name for the new tag:");
  if (!name) return;
  try {
    const tag = await post("/api/tags", { name, sha256: photo.sha256 });
    $("viewer-tags").hidden = true;
    $("viewer-tag-add").setAttribute("aria-expanded", "false");
    await loadTags();
    toast(`Tagged “${tag.name}”`);
  } catch (error) {
    handle(error);
  }
}

async function setAlbumCover() {
  const photo = state.photos[state.viewing];
  const album = currentAlbum();
  if (!photo || !album) return;
  try {
    await post(`/api/albums/${album.id}`, { cover: photo.sha256 });
    await loadAlbums();
    toast(`“${album.name}” now uses this photo as its cover`);
  } catch (error) {
    handle(error);
  }
}

async function removeFromAlbum() {
  const photo = state.photos[state.viewing];
  const album = currentAlbum();
  if (!photo || !album) return;
  try {
    const result = await post("/api/album-photos",
      { album: album.id, sha256: photo.sha256, member: false });
    await loadAlbums();
    closeViewer();
    resetPhotos();
    toast(result.changed ? `Removed from “${album.name}”` : "It was not in this album");
  } catch (error) {
    handle(error);
  }
}

function closeViewer() {
  const target = state.viewerReturnFocus;
  state.viewerReturnFocus = null;
  hideDetails();
  $("viewer-tags").hidden = true;
  $("viewer-tags").replaceChildren();
  $("viewer").hidden = true;
  $("viewer-stage").replaceChildren();
  document.body.style.overflow = "";
  state.viewing = -1;
  if (target && target.isConnected) target.focus();
}

async function step(delta) {
  if (state.viewing < 0) return;
  const target = state.viewing + delta;
  if (target >= state.photos.length - 6) await loadMore();
  if (target >= 0 && target < state.photos.length) openViewer(target);
}

function wireViewer() {
  $("viewer-close").addEventListener("click", closeViewer);
  $("viewer-prev").addEventListener("click", () => step(-1));
  $("viewer-next").addEventListener("click", () => step(1));
  $("viewer-favorite").addEventListener("click", toggleFavorite);
  $("viewer-album-add").addEventListener("click", toggleAlbumMenu);
  $("viewer-tag-add").addEventListener("click", toggleTagMenu);
  $("viewer-album-remove").addEventListener("click", removeFromAlbum);
  $("viewer-cover").addEventListener("click", setAlbumCover);
  $("viewer-sidecar").addEventListener("click", sidecarCurrent);
  $("viewer-archive").addEventListener("click", toggleArchiveCurrent);
  $("viewer-info").addEventListener("click", toggleDetails);
  $("viewer-trash").addEventListener("click", trashCurrent);
  document.addEventListener("keydown", (event) => {
    if (state.viewing < 0) return;
    if (event.key === "Escape") closeViewer();
    if (event.key === "ArrowLeft") step(-1);
    if (event.key === "ArrowRight") step(1);
    if (event.key === "Tab") {
      const focusable = [...$("viewer").querySelectorAll(
        "button, a[href], input, select, textarea, [tabindex]:not([tabindex='-1'])")]
        .filter((item) => !item.disabled && !item.hidden && item.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    if (event.key.toLowerCase() === "f" && !event.ctrlKey && !event.metaKey && !event.altKey
      && event.target.tagName !== "BUTTON") toggleFavorite();
    if (event.key.toLowerCase() === "i" && !event.ctrlKey && !event.metaKey && !event.altKey
      && event.target.tagName !== "BUTTON") toggleDetails();
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
  const gb = (n) => (n / 1024 ** 3).toFixed(n < 10 * 1024 ** 3 ? 1 : 0);
  $("disk-banner").hidden = !s.disk.low;
  $("disk-banner").textContent = `Only ${gb(s.disk.free)} GB of ${gb(s.disk.total)} GB left on the photo drive. Free some space or move the library to a bigger drive (Harbor window → Choose…).`;
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

async function loadStorage() {
  const report = await api("/api/storage");
  const shared = report.shared ? ` · ${report.shared.toLocaleString()} shared` : "";
  $("storage-summary").textContent = `${report.count.toLocaleString()} files · ${bytes(report.bytes)} · ${report.photos.toLocaleString()} photos · ${report.videos.toLocaleString()} videos${shared}`;
  const people = $("storage-people");
  people.replaceChildren();
  for (const person of report.people) {
    const row = el("div", "storage-person");
    row.append(el("b", "", personName(person.profile)),
      el("span", "", items(person.count)),
      el("span", "hint", bytes(person.bytes)));
    people.append(row);
  }
  const largest = $("storage-largest");
  largest.replaceChildren();
  if (report.largest.length === 0) {
    largest.append(el("li", "none", "No files yet."));
    return;
  }
  for (const item of report.largest) {
    const row = el("li");
    const link = el("a", "", item.name);
    link.href = `/media/${item.sha256}`;
    link.target = "_blank";
    link.rel = "noopener";
    row.append(link, el("span", "hint", `${bytes(item.size)} · ${ago(item.time)}`));
    largest.append(row);
  }
}

async function loadBackup() {
  try {
    const report = await api("/api/backup");
    $("backup-panel").hidden = false;
    if (!report.configured) {
      $("backup-status").textContent =
        "No backup folder is configured. Start Harbor with --backup-to <folder> or use the Harbor window.";
      return;
    }
    if (report.error) {
      $("backup-status").textContent =
        `Backup to ${report.target} failed ${report.last_at ? ago(report.last_at) : "at the last attempt"}: ${report.error}`;
      return;
    }
    $("backup-status").textContent =
      `Backup to ${report.target} · ${report.last_at ? ago(report.last_at) : "starting"} · `
      + `${report.copied.toLocaleString()} copied last time · ${bytes(report.bytes)}`;
  } catch (error) {
    if (error instanceof Unauthorised) handle(error);
    else $("backup-panel").hidden = true;
  }
}

async function loadSetup() {
  const setup = await api("/api/setup");
  $("setup-server").textContent = setup.server;
  await loadPeople();
  await loadAndroid();
  $("this-pc").hidden = !(state.owner && setup.startup.supported);
  $("startup-toggle").checked = setup.startup.enabled;
}

async function loadAndroid() {
  const meta = $("android-meta");
  const download = $("android-download");
  try {
    const info = await api("/api/android");
    if (!info.available) {
      meta.textContent = "The APK is not built yet. On the PC run: python android/build.py";
      download.hidden = true;
      return;
    }
    meta.textContent = `Version ${info.version} · ${bytes(info.size)} · SHA-256 ${info.sha256}`;
    download.hidden = false;
    download.href = info.apk;
    download.setAttribute("download", `Harbor-${info.version}.apk`);
  } catch (error) {
    meta.textContent = "The Android build details could not be read.";
    download.hidden = true;
    if (error instanceof Unauthorised) throw error;
  }
}

function wireAndroid() {
  $("android-copy").addEventListener("click", () => copyText(new URL("/android/", location.origin).href));
}

function wireStartup() {
  $("startup-toggle").addEventListener("change", async (event) => {
    try {
      const reply = await api("/api/startup", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: event.target.checked }),
      });
      event.target.checked = reply.enabled;
      toast(reply.enabled ? "Harbor will start when you sign in to Windows" : "Harbor will no longer start with Windows");
    } catch (error) {
      event.target.checked = !event.target.checked;
      handle(error);
    }
  });
}

function show(view) {
  if (view !== "photos" && state.selecting) setSelecting(false);
  if (view !== "photos") hideDatePanel();
  if (view !== "similar") {
    clearTimeout(state.similarTimer);
    state.similarTimer = null;
    if (!$("similar-compare").hidden) closeCompare();
  }
  for (const tab of document.querySelectorAll("[role=tab]")) {
    tab.setAttribute("aria-selected", String(tab.dataset.view === view));
  }
  for (const name of ["photos", "folders", "explore", "albums", "tags", "people",
    "activity", "health", "sync", "setup", "similar", "map", "trash"]) {
    $(`view-${name}`).hidden = name !== view;
  }
  if (view === "folders") loadFolders().catch(handle);
  if (view === "explore") loadExplore().catch(handle);
  if (view === "albums") loadAlbumOverview().catch(handle);
  if (view === "tags") loadTagOverview().catch(handle);
  if (view === "people") loadPeopleOverview().catch(handle);
  if (view === "activity") loadActivity().catch(handle);
  if (view === "health") loadHealth().catch(handle);
  if (view === "sync") {
    refreshStatus().catch(handle);
    loadStorage().catch(handle);
    loadBackup().catch(handle);
  }
  if (view === "setup") loadSetup().catch(handle);
  if (view === "similar") loadSimilar().catch(handle);
  if (view === "map") loadMap().catch(handle);
  if (view === "trash") loadTrash().catch(handle);
  if (view === "photos") scheduleWindow();
  try { localStorage.setItem("harbor-view", view); } catch (_) { /* private mode */ }
}

function wireShell() {
  $("compare-close").addEventListener("click", closeCompare);
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
  window.addEventListener("scroll", scheduleWindow, { passive: true });
  window.addEventListener("resize", () => {
    layoutDays();
    scheduleWindow();
  });
  const bar = document.querySelector(".topbar");
  new ResizeObserver(() => {
    document.documentElement.style.setProperty("--topbar-h", `${bar.offsetHeight}px`);
  }).observe(bar);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible" || $("shell").hidden) return;
    refreshStatus().catch(handle);
    if (!$("view-sync").hidden) {
      loadStorage().catch(handle);
      loadBackup().catch(handle);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || state.viewing >= 0) return;
    if (!$("similar-compare").hidden) {
      closeCompare();
      return;
    }
    hideDatePanel();
    hideSelectAlbums();
    hideSelectTags();
    hideSelectSidecars();
    hideDetails();
  });
}

// ---------- sign-in ----------

function handle(error) {
  if (error instanceof Unauthorised) {
    showLogin();
    return;
  }
  toast(error.message || "Something went wrong");
}

const login = { profile: null, useKey: false };

function renderLogin() {
  $("login-intro").textContent = login.useKey ? "Paste the key shown for you in the Harbor window." : "Who is looking?";
  $("login-people").hidden = login.useKey;
  $("login-password").hidden = login.useKey || !login.profile;
  $("login-key").hidden = !login.useKey;
  $("login-submit").hidden = !login.useKey && !login.profile;
  $("login-mode").textContent = login.useKey ? "Sign in with my name and password" : "Sign in with a key instead";
}

async function showLogin() {
  $("shell").hidden = true;
  $("login").hidden = false;
  let people = [];
  try { people = (await api("/api/people")).profiles; } catch (_) { /* the key still works */ }
  const box = $("login-people");
  box.replaceChildren();
  for (const person of people) {
    const choice = el("button");
    choice.type = "button";
    choice.setAttribute("role", "radio");
    choice.setAttribute("aria-checked", String(login.profile === person.id));
    choice.append(Object.assign(el("span", "avatar", initials(person.name))), el("span", "", person.name));
    choice.addEventListener("click", () => {
      login.profile = person.id;
      $("login-user").value = person.name;
      for (const other of box.children) other.setAttribute("aria-checked", String(other === choice));
      $("login-error").textContent = person.has_password ? ""
        : `${person.name} has no password yet. Ask the main profile to set one, or sign in with your key.`;
      renderLogin();
      $("login-password").focus();
    });
    box.append(choice);
  }
  if (people.length === 0) login.useKey = true;
  renderLogin();
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
  loadPeople().catch(handle);
  loadOutline().catch(handle);
  loadAlbums().catch(handle);
  loadTags().catch(handle);
  resetPhotos();
}

$("login-mode").addEventListener("click", () => {
  login.useKey = !login.useKey;
  $("login-error").textContent = "";
  renderLogin();
});

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("login-error").textContent = "";
  const body = login.useKey ? { key: $("login-key").value.trim() }
    : { profile: login.profile, password: $("login-password").value };
  try {
    await post("/api/login", body);
    $("login-password").value = "";
    $("login-key").value = "";
    start();
  } catch (error) {
    $("login-error").textContent = error instanceof Unauthorised
      ? (login.useKey ? "That key is not right." : "That password is not right.") : error.message;
  }
});

function wireAccount() {
  $("account-button").addEventListener("click", (event) => {
    event.stopPropagation();
    const open = $("account-menu").hidden;
    $("account-menu").hidden = !open;
    $("account-button").setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", () => { $("account-menu").hidden = true; });
  $("menu-password").addEventListener("click", () => {
    show("setup");
    $("my-account").scrollIntoView({ behavior: "smooth" });
    ($("pw-current").hidden ? $("pw-new") : $("pw-current")).focus();
  });
  $("menu-signout").addEventListener("click", async () => {
    await post("/api/logout", {}).catch(() => null);
    login.profile = null;
    showLogin();
  });
  $("password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await post("/api/password", { current: $("pw-current").value, new: $("pw-new").value });
      $("pw-current").value = "";
      $("pw-new").value = "";
      toast("Password changed");
      loadPeople().catch(handle);
    } catch (error) {
      handle(error);
    }
  });
}

wireShell();
wireBrowser();
wireAccount();
wirePeople();
wireStartup();
wireAndroid();
wireUploads();
wireViewer();
start();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
