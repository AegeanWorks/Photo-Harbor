"""Build a signed debug APK with the Android SDK tools; no Gradle or runtime libraries."""

import datetime
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
BUILD = ROOT / "build"
OUTPUT = PROJECT / "photo_harbor" / "web" / "android" / "Harbor.apk"
KEYSTORE = Path.home() / ".harbor-android" / "debug.keystore"
STOREPASS = "android"
VERSION = "1.0"
VERSION_CODE = 1


def find_sdk() -> Path:
    candidates = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
                  str(Path.home() / "AppData" / "Local" / "Android" / "Sdk"),
                  str(Path.home() / "Android" / "Sdk"), "C:/Android/Sdk"]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if (path / "platforms" / "android-34" / "android.jar").is_file():
            return path
    raise SystemExit("Android SDK 34 not found; set ANDROID_HOME or install platforms;android-34")


def find_java() -> Path:
    candidates = [os.environ.get("JAVA_HOME"),
                  *glob.glob("C:/Program Files/Microsoft/jdk-17*"),  # hygiene: allow JDK install root
                  *glob.glob("C:/Program Files/Eclipse Adoptium/jdk-17*")]  # hygiene: allow JDK root
    for candidate in candidates:
        if candidate and (Path(candidate) / "bin" / "javac.exe").is_file():
            return Path(candidate)
    javac = shutil.which("javac")
    if javac:
        return Path(javac).resolve().parent.parent
    raise SystemExit("JDK 17 not found; set JAVA_HOME or install OpenJDK 17")


def run(command, env, cwd=None):
    print("+", " ".join(str(part) for part in command))
    subprocess.run([str(part) for part in command], check=True, env=env, cwd=cwd, timeout=600)


def main() -> int:
    sdk = find_sdk()
    java = find_java()
    build_tools = sdk / "build-tools" / "34.0.0"
    android_jar = sdk / "platforms" / "android-34" / "android.jar"
    aapt2 = build_tools / "aapt2.exe"
    d8 = build_tools / "d8.bat"
    zipalign = build_tools / "zipalign.exe"
    apksigner = build_tools / "apksigner.bat"
    for tool in (aapt2, d8, zipalign, apksigner, android_jar):
        if not tool.exists():
            raise SystemExit(f"missing Android tool: {tool}")

    env = dict(os.environ)
    env["JAVA_HOME"] = str(java)
    env["PATH"] = str(java / "bin") + os.pathsep + env.get("PATH", "")
    java_bin = java / "bin"
    keytool = java_bin / ("keytool.exe" if os.name == "nt" else "keytool")

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    res_zip = BUILD / "resources.zip"
    unsigned = BUILD / "unsigned.apk"
    aligned = BUILD / "aligned.apk"
    classes = BUILD / "classes"
    dex = BUILD / "dex"
    classes.mkdir()
    dex.mkdir()

    run([aapt2, "compile", "--dir", ROOT / "res", "-o", res_zip], env)
    run([aapt2, "link", "-o", unsigned, "-I", android_jar,
         "--manifest", ROOT / "AndroidManifest.xml", res_zip], env)

    sources = [str(path) for path in (ROOT / "src").rglob("*.java")]
    run([java_bin / "javac", "-source", "8", "-target", "8", "-classpath", android_jar,
         "-d", classes, *sources], env)
    class_files = [str(path) for path in classes.rglob("*.class")]
    run([d8, "--lib", android_jar, "--min-api", "26", "--output", dex, *class_files], env)

    with zipfile.ZipFile(unsigned, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.write(dex / "classes.dex", "classes.dex")
    run([zipalign, "-f", "4", unsigned, aligned], env)

    KEYSTORE.parent.mkdir(parents=True, exist_ok=True)
    if not KEYSTORE.exists():
        run([keytool, "-genkeypair", "-noprompt", "-keystore", KEYSTORE,
             "-storepass", STOREPASS, "-keypass", STOREPASS,
             "-alias", "androiddebugkey", "-dname", "CN=Harbor Debug,O=AegeanWorks,C=TR",
             "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000"], env)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    run([apksigner, "sign", "--ks", KEYSTORE, "--ks-pass", f"pass:{STOREPASS}",
         "--key-pass", f"pass:{STOREPASS}", "--out", OUTPUT, aligned], env)
    run([apksigner, "verify", "--verbose", OUTPUT], env)
    run([aapt2, "dump", "badging", OUTPUT], env)
    data = OUTPUT.read_bytes()
    metadata = {
        "version": VERSION,
        "versionCode": VERSION_CODE,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    info_path = OUTPUT.with_name("Harbor.apk.json")
    info_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"\nBuilt {OUTPUT} ({metadata['size']} bytes, sha256 {metadata['sha256']})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f"build failed: {error}", file=sys.stderr)
        raise SystemExit(1)
