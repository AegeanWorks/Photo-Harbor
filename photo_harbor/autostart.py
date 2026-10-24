"""Starting Harbor when the user signs in to Windows, through the per-user Run registry key."""

import os
import sys
from pathlib import Path
from typing import Optional

from .errors import HarborError

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Harbor"
LAUNCHER = Path(__file__).resolve().parent.parent / "Harbor.pyw"


def launch_command(python: Optional[Path] = None, launcher: Path = LAUNCHER) -> str:
    """``pythonw.exe`` (no console window) running ``Harbor.pyw --startup``."""
    python = python or Path(sys.executable)
    windowless = python.with_name("pythonw.exe")
    return f'"{windowless if windowless.exists() else python}" "{launcher}" --startup'


class WindowsRunKey:
    """HKEY_CURRENT_USER's Run key: no administrator rights needed, and only this user is affected."""

    def read(self) -> Optional[str]:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                return winreg.QueryValueEx(key, VALUE_NAME)[0]
        except FileNotFoundError:
            return None

    def write(self, command: str) -> None:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)

    def delete(self) -> None:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            return  # already absent: that is the state we wanted


class Autostart:
    def __init__(self, registry=None, command: Optional[str] = None,
                 supported: Optional[bool] = None) -> None:
        self.supported = (os.name == "nt") if supported is None else supported
        self._registry = registry or (WindowsRunKey() if self.supported else None)
        self._command = command or launch_command()

    def enabled(self) -> bool:
        return self.supported and self._registry.read() is not None

    def set(self, enabled: bool) -> bool:
        """Turn starting with Windows on or off; returns the new state."""
        if not self.supported:
            raise HarborError("starting with the computer is only set up on Windows",
                              f"this is {sys.platform}",
                              "add `python -m photo_harbor serve` to your system's startup items")
        try:
            if enabled:
                self._registry.write(self._command)
            else:
                self._registry.delete()
        except OSError as exc:
            raise HarborError("Windows refused the startup setting", str(exc),
                              "try again; if it repeats, check that the account can edit its own"
                              " startup apps (Settings > Apps > Startup)", status=500) from exc
        return self.enabled()
