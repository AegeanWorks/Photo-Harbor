"""Command line: ``python -m photo_harbor serve | panel | key | profiles | import | backup``."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import DEFAULT_LIBRARY
from .errors import HarborError

DEFAULT_PORT = 8642
BACKUP_OFF = "off (add --backup-to E:\\HarborBackup)"
PREVIEWS_OFF = "off: Safari shows HEIC itself; `pip install pillow pillow-heif` adds thumbnails"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m photo_harbor",
                                     description="A photo server an iPhone feeds over home Wi-Fi.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY,
                        help=f"folder that holds the photos (default: {DEFAULT_LIBRARY})")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="run the server and gallery in this console")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"default {DEFAULT_PORT}")
    serve.add_argument("--host", default="0.0.0.0", help="address to listen on (default: all)")
    serve.add_argument("--backup-to", type=Path, help="mirror originals here daily (another drive)")
    commands.add_parser("panel", help="open the Harbor window with a Start/Stop button")
    key = commands.add_parser("key", help="print the library (main profile) key")
    key.add_argument("--new", action="store_true", help="replace it; old Shortcuts stop working")
    people = commands.add_parser("profiles", help="list people and their keys")
    people.add_argument("--add", metavar="NAME", help="add a person, e.g. --add Ayşe")
    importer = commands.add_parser("import", help="copy photos from a folder on this PC in")
    importer.add_argument("folder", type=Path, help="folder to scan, with its subfolders")
    importer.add_argument("--profile", default="main", help="whose photos they are (default: main)")
    backup = commands.add_parser("backup", help="copy originals to another drive once")
    backup.add_argument("--to", type=Path, required=True, help="backup folder")
    backup.add_argument("--check", action="store_true",
                        help="re-hash every copied file instead of copying")
    return parser


def _serve(args, library: Path) -> int:
    from .runner import ServerRunner

    runner = ServerRunner(library, args.port, args.host, args.backup_to)
    running = runner.start()
    print(f"Harbor {__version__} is running. Press Ctrl+C to stop.")
    print(f"  Library:   {running.library}")
    print(f"  This PC:   {running.local_url}")
    print(f"  iPhone:    {running.lan_url}")
    print(f"  Key:       {runner.app.profiles.all()[0].key}  (main profile)")
    print(f"  Backup:    {args.backup_to or BACKUP_OFF}")
    print(f"  Previews:  {'on' if running.previews else PREVIEWS_OFF}", flush=True)
    try:
        runner.wait()
    except KeyboardInterrupt:
        print("Stopping.")
    finally:
        runner.stop()
    return 0


def _with_app(library: Path, action) -> int:
    """Run ``action(app)`` against the library without serving it."""
    from .app import HarborApp
    from .config import load_or_create

    app = HarborApp(load_or_create(library), port=0)
    try:
        app.layout.prepare()
        return action(app)
    finally:
        app.close()


def _profiles(args, app) -> int:
    if args.add:
        added = app.profiles.create(args.add)
        print(f"Added {added.name} ({added.id}). Key for their Shortcut: {added.key}")
        return 0
    for profile in app.profiles.all():
        print(f"{profile.id:<16} {profile.name:<20} {profile.key}")
    return 0


def _import(args, library: Path, app) -> int:
    from .importer import import_folder

    if args.profile not in {profile.id for profile in app.profiles.all()}:
        raise HarborError(f"no profile {args.profile!r}", "photos must belong to someone",
                          "list them with `profiles`, or add one with `profiles --add NAME`")

    def show(done, total, path):
        print(f"\r{done}/{total} {path.name[:50]:<50}", end="", flush=True)

    report = import_folder(app.store, args.folder.expanduser(), library, args.profile, show,
                           ledger=app.imports)
    print(f"\n{report.summary}.")
    for line in report.errors:
        print(f"  {line}")
    return 0


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    from .config import load_or_create, rotate_key

    try:
        library = args.library.expanduser().resolve()
        if args.command == "key":
            settings = rotate_key(library) if args.new else load_or_create(library)
            print(settings.key)
            return 0
        if args.command == "backup":
            from .backup import mirror, verify
            target = args.to.expanduser().resolve()
            if args.check:
                report = verify(library, target)
                print(f"Checked {report.checked} files ({report.bytes_checked} bytes); "
                      f"{report.missing} missing, {report.different} different, "
                      f"{report.extra} extra in the backup.")
                for rel, kind in report.problems:
                    print(f"  {kind}: {rel}")
                return 0 if report.ok else 1
            report = mirror(library, target)
            print(f"Copied {report.copied} ({report.bytes_copied} bytes); "
                  f"{report.unchanged} already backed up.")
            return 0
        if args.command == "profiles":
            return _with_app(library, lambda app: _profiles(args, app))
        if args.command == "import":
            return _with_app(library, lambda app: _import(args, library, app))
        if args.command == "panel":
            from .control_panel import main as panel
            return panel(library)
        return _serve(args, library)
    except HarborError as error:
        print(error.as_text(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
