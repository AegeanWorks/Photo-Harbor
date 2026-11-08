"use strict";

fetch("/android/Harbor.apk.json", { cache: "no-store" })
  .then((response) => (response.ok ? response.json() : null))
  .then((data) => {
    if (!data) return;
    const kb = (data.size / 1024).toFixed(1);
    document.getElementById("apk-meta").textContent =
      `Version ${data.version} \u00b7 ${kb} KB \u00b7 SHA-256 ${data.sha256} ` +
      `\u00b7 Android 8 or newer, signed for sideloading`;
  })
  .catch(() => {});
