"""Command line: ``python -m photo_harbor serve | key | backup``."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .errors import HarborError

DEFAULT_LIBRARY = Path.home() / "Pictures" / "Harbor"
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
    serve = commands.add_parser("serve", help="run the server and gallery")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"default {DEFAULT_PORT}")
    serve.add_argument("--host", default="0.0.0.0", help="address to listen on (default: all)")
    serve.add_argument("--backup-to", type=Path, help="mirror originals here daily (another drive)")
    key = commands.add_parser("key", help="print the key the Shortcut sends")
    key.add_argument("--new", action="store_true", help="replace it; old Shortcuts stop working")
    backup = commands.add_parser("backup", help="copy originals to another drive once")
    backup.add_argument("--to", type=Path, required=True, help="backup folder")
    return parser


def _serve(args, settings) -> int:
    from .app import HarborApp
    from .backup import DailyBackup
    from .http_server import HarborServer
    from .setup_api import lan_address

    app = HarborApp(settings, args.port)
    try:
        server = HarborServer((args.host, args.port), app.router, app.guard)
    except OSError as exc:
        app.close()
        raise HarborError(f"port {args.port} is not available", str(exc),
                          "close the other Harbor window, or pass --port 8643") from exc
    backup = DailyBackup(settings.library / "photos", args.backup_to) if args.backup_to else None
    print(f"Harbor {__version__} is running. Press Ctrl+C to stop.")
    print(f"  Library:   {settings.library}")
    print(f"  This PC:   http://localhost:{args.port}")
    print(f"  iPhone:    http://{lan_address()}:{args.port}")
    print(f"  Key:       {settings.key}")
    print(f"  Backup:    {args.backup_to or BACKUP_OFF}")
    print(f"  Previews:  {'on' if app.previews else PREVIEWS_OFF}", flush=True)
    if backup:
        backup.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping.")
    finally:
        server.server_close()
        if backup:
            backup.stop()
        app.close()
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
            from .backup import mirror
            report = mirror(library / "photos", args.to.expanduser().resolve())
            print(f"Copied {report.copied} ({report.bytes_copied} bytes); "
                  f"{report.unchanged} already backed up.")
            return 0
        return _serve(args, load_or_create(library))
    except HarborError as error:
        print(error.as_text(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
