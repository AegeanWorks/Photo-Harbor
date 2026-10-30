"use strict";

const PAGE = 120;
const BATCH = 500;
const $ = (id) => document.getElementById(id);
const state = {
  photos: [], next: 0, loading: false, viewing: -1, dayEls: new Map(),
  scope: { kind: null, month: null, favorite: false, album: null, start: null, end: null,
    order: "newest" },
  query: "",
  generation: 0, total: 0, profile: null, people: [], me: null, owner: false,
  favorites: 0, albums: [], selecting: false, selected: new Set(), viewerReturnFocus: null,
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

function filterParams() {
  const params = new URLSearchParams();
  if (state.scope.kind) params.set("kind", state.scope.kind);
  if (state.scope.month) params.set("month", state.scope.month);
  if (state.scope.favorite) params.set("favorite", "1");
  if (state.scope.album) params.set("album", String(state.scope.album));
  if (state.scope.start) params.set("from", state.scope.start);
  if (state.scope.end) params.set("to", state.scope.end);
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
  $("days").replaceChildren();
  return loadMore();
}

// ---------- browsing: months, videos, search ----------

function currentAlbum() {
  return state.albums.find((album) => album.id === state.scope.album) || null;
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
  else if (state.scope.favorite) base = "Favorites";
  else if (state.scope.month) base = capitalise(monthYearFormat.format(monthDate(state.scope.month)));
  else if (state.scope.kind === "video") base = "Videos";
  const dates = dateTitle();
  return dates ? `${base} · ${dates}` : base;
}

function renderScope() {
  const extra = Boolean(state.scope.month || state.scope.kind || state.scope.start
    || state.scope.end || state.query);
  const narrowed = Boolean(extra || state.scope.favorite || state.scope.album);
  const shown = state.photos.length;
  const title = state.query ? `${scopeTitle()} · “${state.query}”` : scopeTitle();
  $("scope-title").textContent = state.profile ? `${personName(state.profile)} · ${title}` : title;
  if (extra) $("scope-count").textContent = state.next === null ? shown.toLocaleString() : `${shown.toLocaleString()}+`;
  else if (state.scope.album) $("scope-count").textContent = (currentAlbum()?.count ?? shown).toLocaleString();
  else if (state.scope.favorite) $("scope-count").textContent = state.favorites.toLocaleString();
  else if (!narrowed && !state.profile) $("scope-count").textContent = state.total.toLocaleString();
  else if (!narrowed) $("scope-count").textContent = (state.people.find((p) => p.id === state.profile)?.count ?? shown).toLocaleString();
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
      : state.scope.favorite
        ? "No favorites yet. Open a photo and press ♡ Favorite."
        : narrowed
          ? "No photo matches. Try another month or search."
          : "Once the iPhone Shortcut runs on your home Wi-Fi, photos appear here, newest first. You can also drop files here or use Upload.";
    $("empty-action").hidden = narrowed;
  }
}

function markScope() {
  const active = state.scope.album ? null
    : state.scope.favorite ? "favorite"
      : state.scope.month || state.scope.kind || "all";
  for (const item of document.querySelectorAll(".rail-item[data-scope]")) {
    item.setAttribute("aria-pressed", String(item.dataset.scope === active));
  }
  for (const item of document.querySelectorAll("[data-album]")) {
    item.setAttribute("aria-pressed", String(Number(item.dataset.album) === state.scope.album));
  }
  $("date-filter").setAttribute("aria-pressed",
    String(Boolean(state.scope.start || state.scope.end)));
}

function setScope(kind, month, extra = {}) {
  if (state.selecting) setSelecting(false);
  state.scope = { kind, month, favorite: false, album: null, start: null, end: null,
    order: state.scope.order || "newest", ...extra };
  hideDatePanel();
  markScope();
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
  $("rail-videos").textContent = outline.videos.toLocaleString();
  state.favorites = outline.favorites || 0;
  $("rail-favorites").textContent = state.favorites.toLocaleString();
  document.querySelector('[data-scope="video"]').hidden = outline.videos === 0;
  markScope();
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
  state.scope = { kind: null, month: null, favorite: false, album: null, start: null, end: null,
    order: state.scope.order || "newest" };
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
    state.scope = { kind: null, month: null, favorite: false, album: null };
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

function renderSelection() {
  const count = state.selected.size;
  $("select-count").textContent = `${count.toLocaleString()} selected`;
  for (const id of ["select-favorite", "select-unfavorite", "select-download", "select-trash",
    "select-album", "select-clear"]) {
    $(id).disabled = count === 0;
  }
  if (count === 0) hideSelectAlbums();
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
    await Promise.all([loadAlbums(), loadOutline(), refreshStatus()]);
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
    await Promise.all([loadTrash(), loadOutline(), loadAlbums(), refreshStatus()]);
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
  $("album-new").addEventListener("click", newAlbum);
  $("album-rename").addEventListener("click", renameAlbum);
  $("album-delete").addEventListener("click", deleteAlbum);
  $("album-download").addEventListener("click", downloadAlbum);
  $("trash-empty").addEventListener("click", emptyTrash);
  $("date-filter").addEventListener("click", toggleDatePanel);
  $("date-apply").addEventListener("click", applyDates);
  $("date-clear").addEventListener("click", clearDates);
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
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".select-album-wrap")) hideSelectAlbums();
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
  $("viewer-albums").hidden = true;
  $("viewer-albums").replaceChildren();
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

function toggleAlbumMenu() {
  const box = $("viewer-albums");
  if (!box.hidden) {
    box.hidden = true;
    return;
  }
  hideDetails();
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
  $("viewer-album-remove").addEventListener("click", removeFromAlbum);
  $("viewer-cover").addEventListener("click", setAlbumCover);
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

async function loadSetup() {
  const setup = await api("/api/setup");
  $("setup-server").textContent = setup.server;
  await loadPeople();
  $("this-pc").hidden = !(state.owner && setup.startup.supported);
  $("startup-toggle").checked = setup.startup.enabled;
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
  for (const tab of document.querySelectorAll("[role=tab]")) {
    tab.setAttribute("aria-selected", String(tab.dataset.view === view));
  }
  for (const name of ["photos", "sync", "setup", "trash"]) {
    $(`view-${name}`).hidden = name !== view;
  }
  if (view === "sync") {
    refreshStatus().catch(handle);
    loadStorage().catch(handle);
  }
  if (view === "setup") loadSetup().catch(handle);
  if (view === "trash") loadTrash().catch(handle);
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
    if (document.visibilityState !== "visible" || $("shell").hidden) return;
    refreshStatus().catch(handle);
    if (!$("view-sync").hidden) loadStorage().catch(handle);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || state.viewing >= 0) return;
    hideDatePanel();
    hideSelectAlbums();
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
wireUploads();
wireViewer();
start();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
