import sys
import winreg
from pathlib import Path


APP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VALUE_NAME = "LocalAssistant"


def _get_startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    script_path = Path(sys.argv[0]).resolve()
    return f'"{sys.executable}" "{script_path}"'


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_startup_enabled(enabled: bool):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_VALUE_NAME, 0, winreg.REG_SZ, _get_startup_command())
        else:
            try:
                winreg.DeleteValue(key, APP_VALUE_NAME)
            except FileNotFoundError:
                pass
            except OSError:
                pass