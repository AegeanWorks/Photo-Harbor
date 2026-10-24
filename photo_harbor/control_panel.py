"""The Harbor window: Start/Stop the server, open the photo browser, manage people, import folders."""

import json
import os
import shutil
import subprocess
import queue
import sqlite3
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

from .atomic_file import write_atomic
from .autostart import Autostart
from .config import DEFAULT_LIBRARY
from .database import OWNER_PROFILE
from .errors import HarborError
from .runner import RunningServer, ServerRunner

PREFS_PATH = Path.home() / ".photo-harbor" / "panel.json"
PREFS_VERSION = 1
DEFAULT_PORT = 8642
POLL_MS = 120

BG = "#f6f4f0"
CARD = "#ffffff"
INK = "#1d1f22"
MUTED = "#6b6a66"
LINE = "#ddd8cf"
ACCENT = "#1f6f6b"
ACCENT_DARK = "#185a57"
DANGER = "#a33a2c"


def load_prefs(path: Path, default_library: Path) -> dict:
    """Saved window choices; defaults when the file is missing, damaged or from another version."""
    prefs = {"library": str(default_library), "backup": "", "port": DEFAULT_PORT,
             "autostart": False, "open_browser": False}
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return prefs
    if isinstance(saved, dict) and saved.get("version") == PREFS_VERSION:
        prefs.update({key: saved[key] for key in prefs if key in saved})
    return prefs


def save_prefs(path: Path, prefs: dict) -> None:
    payload = {"version": PREFS_VERSION, **prefs}
    write_atomic(path, json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))


def mask(key: str) -> str:
    return "•" * 8 + key[-4:]


class ControlPanel:
    """Builds the window; background work reports back through ``_inbox`` on the Tk thread."""

    def __init__(self, root, prefs_path: Path, default_library: Path, startup: bool = False,
                 autostart: Optional[Autostart] = None) -> None:
        """``startup``: launched by Windows at sign-in, so start serving at once, minimised."""
        import tkinter as tk
        from tkinter import ttk

        self.tk, self.ttk, self.root = tk, ttk, root
        self._prefs_path = prefs_path
        self._prefs = load_prefs(prefs_path, default_library)
        self._runner: Optional[ServerRunner] = None
        self._running: Optional[RunningServer] = None
        self._inbox: "queue.Queue[tuple]" = queue.Queue()
        self._stop_import = threading.Event()
        self._importing = False
        self._windows_start = autostart or Autostart()
        self._style()
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(POLL_MS, self._drain)
        if startup:
            root.iconify()
        if startup or self._prefs["autostart"]:
            # As soon as the window exists: the phone may already be trying to sync.
            root.after_idle(self._start_and_maybe_browse)

    # ---------- look ----------

    def _style(self) -> None:
        root, ttk = self.root, self.ttk
        root.title("Harbor")
        root.configure(bg=BG)
        root.minsize(560, 560)
        style = ttk.Style(root)
        style.theme_use("clam")
        base = ("Segoe UI", 10)
        style.configure(".", background=BG, foreground=INK, font=base, bordercolor=LINE,
                        lightcolor=LINE, darkcolor=LINE)
        style.configure("Card.TFrame", background=CARD, relief="flat")
        style.configure("Card.TLabel", background=CARD)
        style.configure("Muted.TLabel", background=CARD, foreground=MUTED)
        style.configure("Head.TLabel", background=CARD, font=("Georgia", 13, "bold"))
        style.configure("Title.TLabel", background=BG, font=("Georgia", 20, "bold"))
        style.configure("Status.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10, "bold"))
        style.configure("Card.TCheckbutton", background=CARD)
        style.map("Card.TCheckbutton", background=[("active", CARD)])
        style.configure("TEntry", fieldbackground=BG, padding=6)
        style.configure("TCombobox", fieldbackground=BG, padding=4)
        style.configure("TButton", padding=(12, 6), background=CARD)
        style.map("TButton", background=[("active", "#ece8e1")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                        font=("Segoe UI", 10, "bold"), padding=(16, 8), bordercolor=ACCENT)
        style.map("Accent.TButton", background=[("active", ACCENT_DARK), ("disabled", LINE)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#ece8e1",
                        bordercolor="#ece8e1", lightcolor=ACCENT, darkcolor=ACCENT)

    def _card(self, parent, title: str):
        frame = self.ttk.Frame(parent, style="Card.TFrame", padding=(16, 10))
        frame.pack(fill="x", pady=(0, 8))
        self.ttk.Label(frame, text=title, style="Head.TLabel").grid(row=0, column=0, columnspan=4,
                                                                    sticky="w", pady=(0, 4))
        frame.columnconfigure(1, weight=1)
        return frame

    # ---------- layout ----------

    def _build(self) -> None:
        tk, ttk = self.tk, self.ttk
        outer = ttk.Frame(self.root, padding=(18, 10, 18, 12))
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="⚓ Harbor", style="Title.TLabel").pack(side="left")
        self.status = ttk.Label(top, text="○  Stopped", style="Status.TLabel")
        self.status.pack(side="right")

        server = self._card(outer, "Server")
        self.library_var = tk.StringVar(value=self._prefs["library"])
        self.backup_var = tk.StringVar(value=self._prefs["backup"])
        self.port_var = tk.StringVar(value=str(self._prefs["port"]))
        self.autostart_var = tk.BooleanVar(value=bool(self._prefs["autostart"]))
        self._folder_row(server, 1, "Photo library", self.library_var)
        self._folder_row(server, 2, "Backup (optional)", self.backup_var)
        ttk.Label(server, text="Port", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(server, textvariable=self.port_var, width=8).grid(row=3, column=1, sticky="w")
        options = ttk.Frame(server, style="Card.TFrame")
        options.grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.windows_var = tk.BooleanVar(value=self._windows_start.enabled())
        self.browser_var = tk.BooleanVar(value=bool(self._prefs["open_browser"]))
        ttk.Checkbutton(options, text="Start Harbor when I sign in to Windows",
                        variable=self.windows_var, style="Card.TCheckbutton",
                        state="normal" if self._windows_start.supported else "disabled",
                        command=self._set_windows_start).pack(anchor="w")
        ttk.Checkbutton(options, text="Start the server when this window opens",
                        variable=self.autostart_var, style="Card.TCheckbutton",
                        command=self._save).pack(anchor="w")
        ttk.Checkbutton(options, text="Open the photo browser when the server starts",
                        variable=self.browser_var, style="Card.TCheckbutton",
                        command=self._save).pack(anchor="w")
        buttons = ttk.Frame(server, style="Card.TFrame")
        buttons.grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 4))
        self.start_button = ttk.Button(buttons, text="Start server", style="Accent.TButton",
                                       command=self.toggle_server)
        self.start_button.pack(side="left")
        self.browse_button = ttk.Button(buttons, text="Open photo browser", state="disabled",
                                        command=self.open_browser)
        self.browse_button.pack(side="left", padx=(8, 0))
        self.folder_button = ttk.Button(buttons, text="Open library folder",
                                        command=lambda: self.open_folder(None))
        self.folder_button.pack(side="left", padx=(8, 0))
        self.check_button = ttk.Button(buttons, text="Check all files", state="disabled",
                                       command=self.check_files)
        self.check_button.pack(side="left", padx=(8, 0))
        self.address = ttk.Label(server, text="Start the server to see the iPhone address.",
                                 style="Muted.TLabel")
        self.address.grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.copy_address = ttk.Button(server, text="Copy", state="disabled",
                                       command=lambda: self.copy(self._running.lan_url))
        self.copy_address.grid(row=6, column=3, sticky="e", pady=(6, 0))
        self.space = ttk.Label(server, text="", style="Muted.TLabel")
        self.space.grid(row=7, column=0, columnspan=4, sticky="w", pady=(2, 0))
        self.library_var.trace_add("write", lambda *_: self._show_space())
        self._show_space()

        self.people = self._card(outer, "People")
        self.people_rows = ttk.Frame(self.people, style="Card.TFrame")
        self.people_rows.grid(row=1, column=0, columnspan=4, sticky="ew")
        self.people_rows.columnconfigure(1, weight=1)
        self.new_name = tk.StringVar()
        ttk.Label(self.people, text="New person", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=(8, 0))
        self.new_entry = ttk.Entry(self.people, textvariable=self.new_name)
        self.new_entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        self.new_entry.bind("<Return>", lambda _event: self.add_person())
        self.add_button = ttk.Button(self.people, text="Add person", command=self.add_person)
        self.add_button.grid(row=2, column=3, sticky="e", padx=(8, 0), pady=(8, 0))

        imports = self._card(outer, "Import from this PC")
        ttk.Label(imports, text="Into", style="Card.TLabel").grid(row=1, column=0, sticky="w")
        self.target = ttk.Combobox(imports, state="readonly", width=24)
        self.target.grid(row=1, column=1, sticky="w")
        self.import_button = ttk.Button(imports, text="Import folder…", command=self.import_folder)
        self.import_button.grid(row=1, column=3, sticky="e")
        self.progress = ttk.Progressbar(imports, mode="determinate")
        self.progress.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        self.progress_label = ttk.Label(imports, text="Copies photos and videos in; the folder "
                                        "itself is not changed.", style="Muted.TLabel")
        self.progress_label.grid(row=3, column=0, columnspan=4, sticky="w")

        log_card = self._card(outer, "Activity")
        self.log_box = tk.Text(log_card, height=4, relief="flat", bg=BG, fg=INK, wrap="word",
                               font=("Segoe UI", 9), padx=8, pady=6, state="disabled")
        self.log_box.grid(row=1, column=0, columnspan=4, sticky="ew")
        self._set_running_ui()

    def _folder_row(self, parent, row: int, label: str, variable) -> None:
        from tkinter import filedialog

        self.ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w",
                                                                     padx=(0, 12), pady=4)
        self.ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, columnspan=2,
                                                            sticky="ew", pady=4)

        def choose():
            chosen = filedialog.askdirectory(parent=self.root, initialdir=variable.get() or None)
            if chosen:
                variable.set(str(Path(chosen)))
                self._save()

        self.ttk.Button(parent, text="Choose…",
                        command=choose).grid(row=row, column=3, sticky="e", padx=(8, 0))

    # ---------- actions ----------

    def toggle_server(self) -> None:
        if self._runner is not None:
            self._stop_import.set()
            self._runner.stop()
            self._runner = self._running = None
            self.log("Server stopped.")
            self._set_running_ui()
            return
        try:
            port = int(self.port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError(port)
        except ValueError:
            self.log("Port must be a number from 1 to 65535.", error=True)
            return
        library = Path(self.library_var.get()).expanduser()
        backup = Path(self.backup_var.get()).expanduser() if self.backup_var.get().strip() else None
        self._save()
        runner = ServerRunner(library, port, backup_to=backup,
                              log=lambda text: self._inbox.put(("log", text)), verbose=False)
        try:
            self._running = runner.start()
        except (HarborError, OSError) as error:
            self.log(getattr(error, "as_text", lambda: str(error))(), error=True)
            return
        self._runner = runner
        self.log(f"Server running. iPhone address {self._running.lan_url}")
        self._set_running_ui()

    def _start_and_maybe_browse(self) -> None:
        if self._runner is None:
            self.toggle_server()
        if self._runner is not None and self.browser_var.get():
            self.open_browser()

    def _set_windows_start(self) -> None:
        try:
            on = self._windows_start.set(bool(self.windows_var.get()))
        except HarborError as error:
            self.log(error.as_text(), error=True)
            on = self._windows_start.enabled()
        self.windows_var.set(on)
        self.log("Harbor will start when you sign in to Windows." if on else
                 "Harbor will no longer start with Windows.")

    def open_browser(self) -> None:
        if self._running is not None:
            webbrowser.open_new_tab(self._running.local_url)

    def add_person(self) -> None:
        name = self.new_name.get().strip()
        if not name or self._runner is None:
            return
        try:
            added = self._runner.app.profiles.create(name)
        except HarborError as error:
            self.log(error.as_text(), error=True)
            return
        self.new_name.set("")
        self.log(f"Added {added.name}. Copy their key into their iPhone Shortcut.")
        self._refresh_people()

    def open_folder(self, folder) -> None:
        """Open the library, or one person's folder, in File Explorer."""
        target = Path(self.library_var.get()).expanduser()
        if folder:
            target = target / folder
        if not target.is_dir():
            self.log(f"{target} does not exist yet; start the server once to create it.",
                     error=True)
            return
        if os.name == "nt":
            os.startfile(target)  # noqa: S606 - opening a folder the user chose
        else:
            subprocess.run(["xdg-open", str(target)], check=False, timeout=10)

    def check_files(self) -> None:
        if self._runner is not None:
            self._runner.app.schedule.run_now(full=True)
            self.log("Checking every file in the background; results appear here.")

    def set_password(self, ident: str, name: str) -> None:
        from tkinter import simpledialog

        password = simpledialog.askstring("Password", f"New password for {name} (6+ characters):",  # aikit:allow-secret typed by the user
                                          show="•", parent=self.root)
        if not password:
            return
        try:
            self._runner.app.passwords.set(ident, password)
            self._runner.app.sessions.close(profile=ident)
        except HarborError as error:
            self.log(error.as_text(), error=True)
            return
        self.log(f"{name} can now sign in to the photo browser with that password.")
        self._refresh_people()

    def rename(self, ident: str, name: str) -> None:
        from tkinter import simpledialog

        new_name = simpledialog.askstring("Rename", f"New name for {name}:", initialvalue=name,
                                          parent=self.root)
        if not new_name or new_name.strip() == name:
            return
        try:
            renamed = self._runner.app.layout.rename_person(ident, new_name)
        except HarborError as error:
            self.log(error.as_text(), error=True)
            return
        self.log(f"Renamed to {renamed.name}; their folder is now \"{renamed.folder}\".")
        self._refresh_people()

    def _person_menu(self, profile):
        menu = self.tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Copy key", command=lambda: self.copy(profile.key))
        menu.add_command(label="Set password…",
                         command=lambda: self.set_password(profile.id, profile.name))
        menu.add_command(label="Rename…", command=lambda: self.rename(profile.id, profile.name))
        menu.add_command(label="Open folder", command=lambda: self.open_folder(profile.folder))
        if profile.id != OWNER_PROFILE:
            menu.add_separator()
            menu.add_command(label="New key…", command=lambda: self.new_key(profile.id, profile.name))
        return menu

    def _show_space(self) -> None:
        """Free space on the library's drive; a warning under 20 GB or 10 %."""
        target = Path(self.library_var.get()).expanduser()
        while not target.exists() and target.parent != target:
            target = target.parent
        try:
            usage = shutil.disk_usage(target)
        except OSError:
            self.space.configure(text="")
            return
        low = usage.free < max(20 * 1024 ** 3, usage.total * 0.10)
        self.space.configure(
            text=f"{'⚠ ' if low else ''}{usage.free / 1024 ** 3:.0f} GB free of "
                 f"{usage.total / 1024 ** 3:.0f} GB on this drive"
                 + ("  —  choose a bigger drive for the library" if low else ""),
            foreground=DANGER if low else MUTED)

    def new_key(self, ident: str, name: str) -> None:
        from tkinter import messagebox

        if not messagebox.askyesno("New key", f"Give {name} a new key? Their current Shortcut "
                                   "stops working until it gets the new key.", parent=self.root):
            return
        self._runner.app.profiles.update(ident, new_key=True)
        self.log(f"{name} has a new key.")
        self._refresh_people()

    def import_folder(self) -> None:
        from tkinter import filedialog

        if self._importing:
            self._stop_import.set()
            return
        if self._runner is None:
            return
        folder = filedialog.askdirectory(parent=self.root, title="Choose a folder to import")
        if not folder:
            return
        profiles = self._runner.app.profiles.all()
        target = profiles[max(self.target.current(), 0)].id
        self._stop_import.clear()
        self._importing = True
        self.import_button.configure(text="Stop import")
        app, library = self._runner.app, Path(self.library_var.get()).expanduser()
        threading.Thread(target=self._import_worker, args=(app, Path(folder), library, target),
                         name="harbor-import", daemon=True).start()

    def _import_worker(self, app, folder: Path, library: Path, profile: str) -> None:
        from .importer import import_folder

        def progress(done, total, path):
            self._inbox.put(("progress", done, total, path.name))

        try:
            report = import_folder(app.store, folder, library, profile, progress,
                                   self._stop_import, ledger=app.imports)
            self._inbox.put(("imported", report.summary, report.errors))
        except (HarborError, OSError, sqlite3.Error) as error:
            # sqlite3.Error: the server was stopped mid-import and closed the catalog.
            self._inbox.put(("imported", f"stopped: {getattr(error, 'message', error)}", ()))

    def copy(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log("Copied to the clipboard.")

    def log(self, text: str, error: bool = False) -> None:
        stamp = datetime.now().strftime("%H:%M")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{stamp}  {'⚠ ' if error else ''}{text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def close(self) -> None:
        self._stop_import.set()
        if self._runner is not None:
            self._runner.stop()
        self._save()
        self.root.destroy()

    # ---------- state ----------

    def _save(self) -> None:
        try:
            port = int(self.port_var.get())
        except ValueError:
            port = DEFAULT_PORT
        prefs = {"library": self.library_var.get(), "backup": self.backup_var.get(),
                 "port": port, "autostart": bool(self.autostart_var.get()),
                 "open_browser": bool(self.browser_var.get())}
        try:
            save_prefs(self._prefs_path, prefs)
        except OSError as error:
            self.log(f"Could not save window settings: {error}", error=True)

    def _set_running_ui(self) -> None:
        on = self._runner is not None
        self.status.configure(text="●  Running" if on else "○  Stopped",
                              foreground=ACCENT if on else MUTED)
        self.start_button.configure(text="Stop server" if on else "Start server")
        state = "normal" if on else "disabled"
        for widget in (self.browse_button, self.copy_address, self.add_button, self.new_entry,
                       self.import_button, self.check_button):
            widget.configure(state=state)
        if not on:
            self.import_button.configure(text="Import folder…")
        self.address.configure(text=f"iPhone address  {self._running.lan_url}" if on else
                               "Start the server to see the iPhone address.")
        self._refresh_people()

    def _refresh_people(self) -> None:
        ttk = self.ttk
        for child in self.people_rows.winfo_children():
            child.destroy()
        if self._runner is None:
            ttk.Label(self.people_rows, text="Start the server to see and add people.",
                      style="Muted.TLabel").grid(row=0, column=0, sticky="w")
            self.target.configure(values=())
            self.target.set("")
            return
        profiles = self._runner.app.profiles.all()
        for row, profile in enumerate(profiles):
            ttk.Label(self.people_rows, text=profile.name, style="Card.TLabel").grid(
                row=row, column=0, sticky="w", pady=2, padx=(0, 16))
            password = "password set" if self._runner.app.passwords.has_password(profile.id) \
                else "no password yet"
            ttk.Label(self.people_rows, text=f"{profile.folder}\\   ·   {password}",
                      style="Muted.TLabel").grid(row=row, column=1, sticky="w")
            ttk.Button(self.people_rows, text="Copy key",
                       command=lambda key=profile.key: self.copy(key)).grid(row=row, column=2,  # aikit:allow-secret value from the catalog
                                                                            padx=(8, 0))
            more = ttk.Menubutton(self.people_rows, text="More")
            more["menu"] = self._person_menu(profile)
            more.grid(row=row, column=3, padx=(8, 0))
        names = [profile.name for profile in profiles]
        current = self.target.get()
        self.target.configure(values=names)
        self.target.set(current if current in names else names[0])

    def _drain(self) -> None:
        """Apply messages from background threads; Tk widgets may only be touched here."""
        while True:
            try:
                message = self._inbox.get_nowait()
            except queue.Empty:
                break
            kind = message[0]
            if kind == "log":
                self.log(message[1])
            elif kind == "progress":
                _, done, total, name = message
                self.progress.configure(maximum=max(total, 1), value=done)
                self.progress_label.configure(text=f"{done} of {total}  ·  {name}")
            elif kind == "imported":
                self._importing = False
                self.import_button.configure(state="normal" if self._runner else "disabled")
                self.import_button.configure(text="Import folder…")
                self.progress_label.configure(text=message[1])
                self.log(f"Import finished: {message[1]}.")
                for line in message[2][:5]:
                    self.log(line, error=True)
                self._refresh_people()
        self.root.after(POLL_MS, self._drain)


def main(library: Optional[Path] = None, startup: bool = False) -> int:
    """Open the window; returns when it is closed. ``startup``: launched at Windows sign-in."""
    try:
        import tkinter as tk
    except ImportError:
        print(HarborError("the Harbor window needs tkinter", "this Python was installed without it",
                          "reinstall Python from python.org with 'tcl/tk' ticked, or use "
                          "`python -m photo_harbor serve`").as_text(), file=sys.stderr)
        return 1
    root = tk.Tk()
    ControlPanel(root, PREFS_PATH, library or DEFAULT_LIBRARY, startup=startup)
    root.mainloop()
    return 0
