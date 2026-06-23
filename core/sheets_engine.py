"""
Google Sheets integration for Stock Checker Pro.
Handles reading parts list and writing stock results.

NEW 8-COLUMN FORMAT (tab: "New parts tracked"):
  A (1) = Part Number
  B (2) = Description
  C (3) = Anass Marcone Stock   -> NEVER TOUCH (Anass's manual notes)
  D (4) = Manus Stock           -> app appends "M/D/YY: qty" each run
  E (5) = Distribution Price    -> app appends price (Marcone price * 0.79), keeps history
  F (6) = Model Years
  G (7) = Anass Comment         -> NEVER TOUCH
  H (8) = AI Comment            -> only written when AI analysis is requested

Row 1 = header row. Data starts at row 2.
"""
import re
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from pathlib import Path
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.logger import log

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

CONFIG_DIR = Path(os.path.expanduser("~")) / "StockCheckerPro" / "config"

# Column layout (1-based) for the new 8-column format
COL_PART_NUMBER = 1        # A
COL_DESCRIPTION = 2        # B
COL_ANASS_MARCONE = 3      # C  -- NEVER TOUCH
COL_MANUS_STOCK = 4        # D  -- app appends stock movements here
COL_DISTRIBUTION_PRICE = 5 # E  -- app appends price history here
COL_MODEL_YEARS = 6        # F
COL_ANASS_COMMENT = 7      # G  -- NEVER TOUCH
COL_AI_COMMENT = 8         # H  -- AI analysis only

DATA_START_ROW = 2  # Row 1 = headers, Row 2+ = data

DISTRIBUTION_MULTIPLIER = 0.79


def _extract_sheet_id(url: str) -> str:
    """Extract the spreadsheet ID from a Google Sheets URL."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    # Maybe they pasted the raw ID
    if re.fullmatch(r"[a-zA-Z0-9-_]{30,}", url.strip()):
        return url.strip()
    raise ValueError(f"Could not extract sheet ID from URL: {url}")


def _get_client(credentials_path: str = None):
    """Get an authenticated gspread client using a service account JSON."""
    # Priority 1: explicit credentials path from settings
    if credentials_path and Path(credentials_path).exists():
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        return gspread.authorize(creds)

    # Priority 2: service_account.json stored in config dir
    service_account_file = CONFIG_DIR / "service_account.json"
    if service_account_file.exists():
        creds = Credentials.from_service_account_file(str(service_account_file), scopes=SCOPES)
        return gspread.authorize(creds)

    raise Exception(
        "No Google credentials found. Please add your service account JSON file "
        "path in Settings (Credentials Path)."
    )


def _today() -> str:
    """Return today's date as M/D/YY (e.g. 6/2/26)."""
    now = datetime.now()
    return f"{now.month}/{now.day}/{now.strftime('%y')}"


def get_parts_list(sheet_url: str, sheet_name: str = "New parts tracked",
                   credentials_path: str = None) -> list:
    """
    Read the parts list from the Google Sheet.
    Returns list of dicts with part info.
    """
    try:
        log("Connecting to Google Sheets...")
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        all_values = worksheet.get_all_values()
        parts = []

        for row_idx, row in enumerate(all_values[DATA_START_ROW - 1:], start=DATA_START_ROW):
            if not row or not row[0].strip():
                continue
            pn = row[0].strip()
            if pn.lower() in ["part number", "pn", "#", ""]:
                continue
            parts.append({
                "row": row_idx,
                "part_number": pn,
                "description": row[1].strip() if len(row) > 1 else "",
                "anass_marcone": row[2].strip() if len(row) > 2 else "",
                "manus_stock": row[3].strip() if len(row) > 3 else "",
                "distribution_price": row[4].strip() if len(row) > 4 else "",
                "model_years": row[5].strip() if len(row) > 5 else "",
            })

        log(f"Retrieved {len(parts)} parts from Google Sheet")
        return parts

    except Exception as e:
        log(f"Error reading Google Sheet: {e}", "ERROR")
        raise


def update_stock_result(sheet_url: str, sheet_name: str, row: int,
                        quantity: int, found: bool,
                        marcone_price: float = None,
                        credentials_path: str = None):
    """
    Update the Manus Stock (col D) and Distribution Price (col E) for one part.

    - Manus Stock: appends "M/D/YY: qty" (or "M/D/YY: OS" if out of stock)
      to the front of the existing history, separated by " | ".
    - Distribution Price: computes marcone_price * 0.79. If the price changed
      from the last recorded value, appends "M/D/YY: $price" to the history.
      The old prices are never deleted.
    """
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        today = _today()
        stock_str = str(quantity) if (found and quantity > 0) else "OS"
        new_entry = f"{today}: {stock_str}"

        # --- Manus Stock (column D) ---
        existing = worksheet.cell(row, COL_MANUS_STOCK).value or ""
        if existing.strip():
            updated = new_entry + " | " + existing
        else:
            updated = new_entry
        worksheet.update_cell(row, COL_MANUS_STOCK, updated)

        # --- Distribution Price (column E) ---
        if marcone_price and marcone_price > 0:
            dist_price = round(marcone_price * DISTRIBUTION_MULTIPLIER, 2)
            dist_str = f"${dist_price:.2f}"
            existing_price = worksheet.cell(row, COL_DISTRIBUTION_PRICE).value or ""

            if existing_price.strip():
                last_price_match = re.findall(r'\$\s*([\d,]+\.?\d*)', existing_price)
                price_changed = True
                if last_price_match:
                    try:
                        last_price = float(last_price_match[0].replace(",", ""))
                        price_changed = abs(last_price - dist_price) > 0.01
                    except ValueError:
                        price_changed = True
                if price_changed:
                    new_price_entry = f"{today}: {dist_str}"
                    updated_price = new_price_entry + " | " + existing_price
                    worksheet.update_cell(row, COL_DISTRIBUTION_PRICE, updated_price)
            else:
                worksheet.update_cell(row, COL_DISTRIBUTION_PRICE, f"{today}: {dist_str}")

        return True

    except Exception as e:
        log(f"Error updating sheet row {row}: {e}", "ERROR")
        return False


def update_description(sheet_url: str, sheet_name: str, row: int,
                       description: str, credentials_path: str = None):
    """Fill the Description (col B) only if it is currently empty."""
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        current = worksheet.cell(row, COL_DESCRIPTION).value or ""
        if not current.strip() and description:
            worksheet.update_cell(row, COL_DESCRIPTION, description)
        return True
    except Exception as e:
        log(f"Error updating description for row {row}: {e}", "ERROR")
        return False


def update_model_years(sheet_url: str, sheet_name: str, row: int,
                       model_years: str, credentials_path: str = None):
    """Update the Model Years column (col F) only if currently empty."""
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        current = worksheet.cell(row, COL_MODEL_YEARS).value or ""
        if not current.strip() and model_years:
            worksheet.update_cell(row, COL_MODEL_YEARS, model_years)
        return True
    except Exception as e:
        log(f"Error updating model years for row {row}: {e}", "ERROR")
        return False


def update_ai_comment(sheet_url: str, sheet_name: str, row: int,
                      comment: str, credentials_path: str = None):
    """Write the AI Comment (col H). Overwrites the previous AI comment."""
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.update_cell(row, COL_AI_COMMENT, comment)
        return True
    except Exception as e:
        log(f"Error updating AI comment for row {row}: {e}", "ERROR")
        return False


def sync_backup_sheet(sheet_url: str, main_sheet: str, backup_sheet: str,
                      credentials_path: str = None):
    """Sync the backup sheet with the main sheet (full copy)."""
    try:
        log(f"Syncing backup sheet '{backup_sheet}'...")
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)

        main_ws = spreadsheet.worksheet(main_sheet)
        try:
            backup_ws = spreadsheet.worksheet(backup_sheet)
        except gspread.exceptions.WorksheetNotFound:
            backup_ws = spreadsheet.add_worksheet(title=backup_sheet, rows=1000, cols=20)

        all_data = main_ws.get_all_values()
        if all_data:
            backup_ws.clear()
            backup_ws.update("A1", all_data)

        log("Backup sheet synced successfully")
        return True

    except Exception as e:
        log(f"Error syncing backup sheet: {e}", "ERROR")
        return False


def test_connection(sheet_url: str, sheet_name: str,
                    credentials_path: str = None):
    """Test the Google Sheets connection. Returns (success, message)."""
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        values = worksheet.get_all_values()
        data_rows = len([r for r in values[1:] if r and r[0].strip()])
        return True, f"Connected to '{spreadsheet.title}' / '{sheet_name}'. Found {data_rows} parts."
    except Exception as e:
        return False, str(e)
