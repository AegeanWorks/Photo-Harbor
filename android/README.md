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
5. Press **Test** to check the address and key, then **Sync now**. The first sync sends photos
   and videos newer than the last finished sync. A background schedule (Wi-Fi only, every
   6 hours) is optional.

## Share from another app

Harbor appears in Android's share sheet for images and videos. Select one or more items in
Gallery (or any app with a share action), choose **Harbor**, and the app uploads them with the
same hash-first protocol. The first share requires the server and key to be saved in Harbor.

The app uses the same endpoints as the iPhone: `/api/sync/start`, `/api/has`, `/api/upload`,
`/api/sync/done`. Every upload carries the phone's SHA-256; the PC keeps it only on a match.
Nothing is deleted from the phone.

The home server is plain HTTP on the local network, so `usesCleartextTraffic` is enabled. Do not
expose the server to the public internet.

## Verified

Android 14 (API 34) emulator, APK installed with `adb install`, Harbor running on the host through
`adb reverse tcp:8642 tcp:8642`:

- **Test** showed `Connected: 0 photos on the PC.`
- First **Sync now** sent one PNG and the server catalog listed `android-test.png`.
- A second sync reported `Done: 0 sent, 1 already on the PC.`
- A share intent for a second PNG reported `Sent 1, 0 already on the PC.` and the server listed
  `android-share.png`.
- Ticking **Sync every 6 hours in the background** scheduled a `PERSISTED`, `NOT_METERED`,
  `PERIODIC interval=+6h` job for `.SyncJobService` (confirmed with `dumpsys jobscheduler`); a
  forced run uploaded the MediaStore images without the app in front.

The emulator test is not part of the Python gate; rerun it after changing the sync engine or
manifest.
