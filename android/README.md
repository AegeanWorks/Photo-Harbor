# Harbor for Android

A small native Android client (Android 8+, no AndroidX, no runtime dependencies) that sends new
photos and videos from the phone's MediaStore to the same Harbor server the iPhone Shortcut uses.

## Build the APK

Requirements on the build PC:

- JDK 17 (`JAVA_HOME`, or the Microsoft/Temurin install folders).
- Android SDK platform 34 and build-tools 34.0.0 (`ANDROID_HOME`, or the default
  `%LOCALAPPDATA%\Android\Sdk`).

```bash
python android/build.py
```

The script compiles the Java sources, links resources with `aapt2`, dexes with `d8`, aligns with
`zipalign`, signs with the debug key in `~/.harbor-android/debug.keystore` (created on first
build), verifies the signature, and writes:

```text
photo_harbor/web/android/Harbor.apk
```

Keep `~/.harbor-android/debug.keystore`: Android only installs an update signed with the same
key. The keystore is deliberately outside the repository.

## Install and use

1. Open the Harbor setup page from the PC or phone: `http://<pc>:8642/android/`.
2. Download `Harbor.apk` and allow installation from this browser when Android asks.
3. In Harbor, copy the person's key from the window or Setup → Server and keys.
4. In the app, enter the server address (e.g. `http://192.168.1.10:8642`) and the key.
5. Press **Sync now**. The first sync sends photos and videos newer than the last finished
   sync. A background schedule (Wi-Fi only, every 6 hours) is optional.

The app uses the same endpoints as the iPhone: `/api/sync/start`, `/api/has`, `/api/upload`,
`/api/sync/done`. Every upload carries the phone's SHA-256; the PC keeps it only on a match.
Nothing is deleted from the phone.

The home server is plain HTTP on the local network, so `usesCleartextTraffic` is enabled. Do not
expose the server to the public internet.
