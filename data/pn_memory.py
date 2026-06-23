"""
Part Number Memory database.
Stores learned PN substitutions so searches never fail twice.
"""
import json
from pathlib import Path
from datetime import datetime
import os

DATA_DIR = Path(os.path.expanduser("~")) / "StockCheckerPro" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PN_MEMORY_FILE = DATA_DIR / "pn_memory.json"


def load_memory() -> dict:
    """Load all PN mappings from file."""
    if not PN_MEMORY_FILE.exists():
        return {}
    try:
        with open(PN_MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_memory(memory: dict):
    """Save PN mappings to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PN_MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def get_resolved_pn(original_pn: str) -> str | None:
    """Get the resolved PN for a given original PN. Returns None if not in memory."""
    memory = load_memory()
    entry = memory.get(original_pn.upper().strip())
    if entry:
        return entry.get("resolved_pn")
    return None


def save_mapping(original_pn: str, resolved_pn: str, reason: str):
    """Save a new PN mapping to memory."""
    memory = load_memory()
    memory[original_pn.upper().strip()] = {
        "original_pn": original_pn.upper().strip(),
        "resolved_pn": resolved_pn.upper().strip(),
        "reason": reason,
        "date_learned": datetime.now().strftime("%b %d, %Y"),
        "date_learned_iso": datetime.now().isoformat()
    }
    save_memory(memory)


def delete_mapping(original_pn: str):
    """Delete a PN mapping from memory."""
    memory = load_memory()
    if original_pn.upper().strip() in memory:
        del memory[original_pn.upper().strip()]
        save_memory(memory)


def update_mapping(original_pn: str, resolved_pn: str, reason: str):
    """Update an existing PN mapping."""
    save_mapping(original_pn, resolved_pn, reason)


def get_all_mappings() -> list:
    """Get all PN mappings as a sorted list."""
    memory = load_memory()
    return sorted(memory.values(), key=lambda x: x.get("date_learned_iso", ""), reverse=True)
