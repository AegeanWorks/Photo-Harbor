"""Double-click to open the Harbor window: Start/Stop the server, open the photo browser,
manage people and import folders. A .pyw file runs without a console window on Windows."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from photo_harbor.control_panel import main  # noqa: E402

# Windows passes --startup when it launches Harbor at sign-in (see photo_harbor/autostart.py).
sys.exit(main(startup="--startup" in sys.argv))
