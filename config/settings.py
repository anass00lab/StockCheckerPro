"""
Settings manager for Stock Checker Pro.
Handles loading, saving, and accessing all app configuration.
"""
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet
import base64
import hashlib

# Base directory for config files
CONFIG_DIR = Path(os.path.expanduser("~")) / "StockCheckerPro" / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "settings.json"
KEY_FILE = CONFIG_DIR / ".key"

DEFAULT_SETTINGS = {
    "marcone": {
        "username": "",
        "password": ""
    },
    "google_sheets": {
        "url": "",
        "sheet_name": "New parts tracked",
        "backup_sheet_name": "Back up sheet",
        "backup_enabled": False,
        "credentials_path": ""
    },
    "scheduler": {
        "stock_check": {
            "Monday": {"enabled": False, "time": "09:00"},
            "Tuesday": {"enabled": False, "time": "09:00"},
            "Wednesday": {"enabled": False, "time": "09:00"},
            "Thursday": {"enabled": False, "time": "09:00"},
            "Friday": {"enabled": False, "time": "09:00"},
            "Saturday": {"enabled": False, "time": "09:00"},
            "Sunday": {"enabled": False, "time": "09:00"}
        },
        "benchmark": {
            "enabled": True,
            "day": "Monday",
            "time": "08:00"
        }
    },
    "app": {
        "theme": "dark",
        "version": "1.0.0",
        "first_run": True
    }
}


def _get_or_create_key():
    """Get or create encryption key for passwords."""
    if KEY_FILE.exists():
        with open(KEY_FILE, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key


def encrypt_password(password: str) -> str:
    """Encrypt a password string."""
    if not password:
        return ""
    key = _get_or_create_key()
    f = Fernet(key)
    return f.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """Decrypt an encrypted password string."""
    if not encrypted:
        return ""
    try:
        key = _get_or_create_key()
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        return ""


def load_settings() -> dict:
    """Load settings from file, merging with defaults."""
    if not CONFIG_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
        # Deep merge with defaults
        merged = DEFAULT_SETTINGS.copy()
        _deep_merge(merged, saved)
        return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    """Save settings to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def _deep_merge(base: dict, override: dict):
    """Recursively merge override into base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
