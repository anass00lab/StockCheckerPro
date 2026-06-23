"""
Auto-Updater Module for Stock Checker Pro
Checks GitHub for updates and applies them automatically.
Repository: https://github.com/anass00lab/StockCheckerPro
"""

import os
import sys
import json
import shutil
import tempfile
import zipfile
import threading
import urllib.request
import urllib.error
from datetime import datetime

GITHUB_USER = "anass00lab"
GITHUB_REPO = "StockCheckerPro"
GITHUB_BRANCH = "master"
VERSION_FILE = "version.json"
GITHUB_VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{VERSION_FILE}"
GITHUB_ZIP_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"

# Files and folders that should NEVER be overwritten during update
PROTECTED_FILES = [
    "data/settings.json",
    "data/pn_memory.db",
    "data/logs",
    "assets/logo.png",
    "assets/logo.ico",
]


def get_app_dir():
    """Return the directory where the app is installed."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_local_version():
    """Read the local version from version.json."""
    version_path = os.path.join(get_app_dir(), VERSION_FILE)
    try:
        with open(version_path, "r") as f:
            data = json.load(f)
            return data.get("version", "0.0.0"), data.get("date", "")
    except Exception:
        return "0.0.0", ""


def get_remote_version():
    """Fetch the latest version info from GitHub."""
    try:
        req = urllib.request.Request(
            GITHUB_VERSION_URL,
            headers={"User-Agent": "StockCheckerPro-Updater"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get("version", "0.0.0"), data.get("date", ""), data.get("changelog", "")
    except Exception:
        return None, None, None


def version_is_newer(remote_ver, local_ver):
    """Compare version strings like '1.2.3'."""
    try:
        remote_parts = [int(x) for x in remote_ver.split(".")]
        local_parts = [int(x) for x in local_ver.split(".")]
        return remote_parts > local_parts
    except Exception:
        return False


def check_for_update():
    """
    Check if a newer version is available.
    Returns: (update_available: bool, remote_version: str, changelog: str)
    """
    local_ver, _ = get_local_version()
    remote_ver, remote_date, changelog = get_remote_version()

    if remote_ver is None:
        return False, local_ver, ""

    if version_is_newer(remote_ver, local_ver):
        return True, remote_ver, changelog or "Bug fixes and improvements."

    return False, local_ver, ""


def download_and_apply_update(progress_callback=None):
    """
    Download the latest version from GitHub and apply it.
    progress_callback(message: str) is called with status updates.
    Returns: (success: bool, message: str)
    """
    app_dir = get_app_dir()

    def progress(msg):
        if progress_callback:
            progress_callback(msg)

    try:
        progress("Downloading update from GitHub...")

        # Download the ZIP archive
        tmp_zip = os.path.join(tempfile.gettempdir(), "StockCheckerPro_update.zip")
        req = urllib.request.Request(
            GITHUB_ZIP_URL,
            headers={"User-Agent": "StockCheckerPro-Updater"}
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(tmp_zip, "wb") as f:
                f.write(response.read())

        progress("Download complete. Applying update...")

        # Extract to a temp directory
        tmp_dir = os.path.join(tempfile.gettempdir(), "StockCheckerPro_update_extracted")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir)

        with zipfile.ZipFile(tmp_zip, "r") as z:
            z.extractall(tmp_dir)

        # The extracted folder is named like "StockCheckerPro-master"
        extracted_root = None
        for item in os.listdir(tmp_dir):
            full_path = os.path.join(tmp_dir, item)
            if os.path.isdir(full_path) and "StockCheckerPro" in item:
                extracted_root = full_path
                break

        if not extracted_root:
            return False, "Could not find extracted files."

        # Build list of protected absolute paths
        protected_abs = set()
        for pf in PROTECTED_FILES:
            protected_abs.add(os.path.normpath(os.path.join(app_dir, pf)))

        # Walk the extracted files and copy them, skipping protected files
        for root, dirs, files in os.walk(extracted_root):
            rel_root = os.path.relpath(root, extracted_root)
            dest_root = os.path.join(app_dir, rel_root) if rel_root != "." else app_dir

            os.makedirs(dest_root, exist_ok=True)

            for filename in files:
                src_file = os.path.join(root, filename)
                dest_file = os.path.normpath(os.path.join(dest_root, filename))

                # Skip protected files
                if dest_file in protected_abs:
                    progress(f"Skipping protected file: {filename}")
                    continue

                shutil.copy2(src_file, dest_file)

        # Clean up temp files
        os.remove(tmp_zip)
        shutil.rmtree(tmp_dir)

        # Log the update
        log_update_applied()

        progress("Update applied successfully! Please restart the app.")
        return True, "Update applied successfully. Please restart Stock Checker Pro."

    except urllib.error.URLError:
        return False, "No internet connection. Please check your network and try again."
    except Exception as e:
        return False, f"Update failed: {str(e)}"


def log_update_applied():
    """Write a log entry when an update is applied."""
    app_dir = get_app_dir()
    log_dir = os.path.join(app_dir, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "updates.log")
    local_ver, _ = get_local_version()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] Update applied — now on version {local_ver}\n")


def check_update_async(callback):
    """
    Run update check in a background thread.
    callback(update_available, remote_version, changelog) is called when done.
    """
    def _run():
        available, version, changelog = check_for_update()
        callback(available, version, changelog)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def apply_update_async(progress_callback, done_callback):
    """
    Run the update download and apply in a background thread.
    progress_callback(message) is called with status updates.
    done_callback(success, message) is called when finished.
    """
    def _run():
        success, message = download_and_apply_update(progress_callback)
        done_callback(success, message)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
