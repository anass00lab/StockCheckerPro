"""
Logger module for Stock Checker Pro.
Handles run history and detailed timestamped logs.
"""
import json
import os
from pathlib import Path
from datetime import datetime

LOGS_DIR = Path(os.path.expanduser("~")) / "StockCheckerPro" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
RUN_INDEX_FILE = LOGS_DIR / "run_index.json"

_current_run_id = None
_current_run_lines = []
_current_run_meta = {}
_log_callback = None  # UI callback for live log updates


def set_log_callback(callback):
    """Set a callback function to receive live log lines during a run."""
    global _log_callback
    _log_callback = callback


def start_run(run_type: str = "stock_check") -> str:
    """Start a new run and return the run ID."""
    global _current_run_id, _current_run_lines, _current_run_meta
    _current_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    _current_run_lines = []
    _current_run_meta = {
        "run_id": _current_run_id,
        "run_type": run_type,
        "start_time": datetime.now().isoformat(),
        "start_display": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "status": "running",
        "parts_checked": 0,
        "errors": 0,
        "warnings": 0,
        "pn_substitutions": 0,
        "duration_seconds": 0
    }
    log(f"Starting Stock Checker Pro run ({run_type})")
    log("Loading configuration...")
    return _current_run_id


def log(message: str, level: str = "INFO"):
    """Add a log line to the current run."""
    global _current_run_lines
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    _current_run_lines.append(line)
    if _log_callback:
        try:
            _log_callback(line)
        except Exception:
            pass


def finish_run(status: str = "success", parts_checked: int = 0,
               errors: int = 0, warnings: int = 0, pn_substitutions: int = 0):
    """Finish the current run and save to disk."""
    global _current_run_meta, _current_run_lines, _current_run_id
    if not _current_run_id:
        return

    end_time = datetime.now()
    start_time = datetime.fromisoformat(_current_run_meta["start_time"])
    duration = int((end_time - start_time).total_seconds())

    _current_run_meta.update({
        "status": status,
        "end_time": end_time.isoformat(),
        "end_display": end_time.strftime("%b %d, %Y %I:%M %p"),
        "parts_checked": parts_checked,
        "errors": errors,
        "warnings": warnings,
        "pn_substitutions": pn_substitutions,
        "duration_seconds": duration,
        "duration_display": f"{duration // 60}m {duration % 60}s"
    })

    summary = (f"Run completed in {_current_run_meta['duration_display']}. "
               f"{parts_checked} parts checked. {errors} errors. "
               f"{pn_substitutions} PN substitution(s) saved.")
    log(summary)

    # Save detailed log file
    log_file = LOGS_DIR / f"run_{_current_run_id}.json"
    with open(log_file, "w") as f:
        json.dump({
            "meta": _current_run_meta,
            "lines": _current_run_lines
        }, f, indent=2)

    # Update run index
    _update_index(_current_run_meta)
    _current_run_id = None


def _update_index(meta: dict):
    """Update the run index file."""
    index = _load_index()
    index.insert(0, {
        "run_id": meta["run_id"],
        "run_type": meta.get("run_type", "stock_check"),
        "start_display": meta["start_display"],
        "status": meta["status"],
        "parts_checked": meta["parts_checked"],
        "errors": meta["errors"],
        "warnings": meta["warnings"],
        "pn_substitutions": meta["pn_substitutions"],
        "duration_display": meta.get("duration_display", "")
    })
    # Keep last 100 runs
    index = index[:100]
    with open(RUN_INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)


def _load_index() -> list:
    """Load the run index."""
    if not RUN_INDEX_FILE.exists():
        return []
    try:
        with open(RUN_INDEX_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def get_run_list() -> list:
    """Get list of all runs (most recent first)."""
    return _load_index()


def get_run_detail(run_id: str) -> dict | None:
    """Get full detail for a specific run."""
    log_file = LOGS_DIR / f"run_{run_id}.json"
    if not log_file.exists():
        return None
    try:
        with open(log_file, "r") as f:
            return json.load(f)
    except Exception:
        return None
