"""
Google Sheets integration for Stock Checker Pro.
Handles reading parts list and writing stock results.
"""
import re
import gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
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

# Column layout (1-based)
COL_PART_NUMBER = 1
COL_PART_NAME = 2
COL_BRAND = 3
COL_APPLIANCE_TYPE = 4
COL_MARCONE_STOCK = 5
COL_DISTRIBUTION_PRICE = 6
COL_MODELS_COUNT = 7
COL_YEAR_RANGE = 8
COL_AMAZON_PRICE = 9
COL_GOOGLE_PRICE = 10
COL_EBAY_PRICE = 11
COL_ANASS_COMMENT = 12  # NEVER TOUCH THIS COLUMN

DATA_START_ROW = 3  # Row 1 = section headers, Row 2 = column headers, Row 3+ = data


def _extract_sheet_id(url: str) -> str:
    """Extract the spreadsheet ID from a Google Sheets URL."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract sheet ID from URL: {url}")


def _get_client(credentials_path: str = None):
    """Get an authenticated gspread client."""
    token_file = CONFIG_DIR / "token.json"
    client_secret_file = CONFIG_DIR / "client_secret.json"

    if credentials_path and Path(credentials_path).exists():
        client_secret_file = Path(credentials_path)

    # Try service account first
    service_account_file = CONFIG_DIR / "service_account.json"
    if service_account_file.exists():
        creds = Credentials.from_service_account_file(str(service_account_file), scopes=SCOPES)
        return gspread.authorize(creds)

    # Try OAuth token
    if token_file.exists():
        try:
            import json
            with open(token_file) as f:
                token_data = json.load(f)
            from google.oauth2.credentials import Credentials as OAuthCreds
            creds = OAuthCreds.from_authorized_user_info(token_data, SCOPES)
            if creds and creds.valid:
                return gspread.authorize(creds)
        except Exception:
            pass

    # OAuth flow
    if client_secret_file.exists():
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
        creds = flow.run_local_server(port=0)
        import json
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        return gspread.authorize(creds)

    raise Exception("No Google credentials found. Please add credentials in Settings.")


def get_parts_list(sheet_url: str, sheet_name: str = "Sheet1",
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
                "part_name": row[1].strip() if len(row) > 1 else "",
                "brand": row[2].strip() if len(row) > 2 else "",
                "appliance_type": row[3].strip() if len(row) > 3 else "",
                "current_stock": row[4].strip() if len(row) > 4 else "",
                "distribution_price": row[5].strip() if len(row) > 5 else "",
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
    Update the stock result for a single part in the sheet.
    Appends to existing stock history with date and bold formatting.
    """
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        today = datetime.now().strftime("%-m/%-d/%y")  # e.g. 6/2/26
        stock_str = str(quantity) if found and quantity > 0 else "OS"
        new_entry = f"{today}: {stock_str}"

        # Read existing value
        existing = worksheet.cell(row, COL_MARCONE_STOCK).value or ""
        if existing:
            updated = existing + " | " + new_entry
        else:
            updated = new_entry

        worksheet.update_cell(row, COL_MARCONE_STOCK, updated)

        # Update distribution price if provided
        if marcone_price and marcone_price > 0:
            dist_price = round(marcone_price * 0.79, 2)
            dist_str = f"${dist_price:.2f}"
            existing_price = worksheet.cell(row, COL_DISTRIBUTION_PRICE).value or ""
            if existing_price:
                # Check if price changed
                last_price_match = re.findall(r'\$[\d.]+', existing_price)
                if last_price_match:
                    last_price = float(last_price_match[-1].replace("$", ""))
                    if abs(last_price - dist_price) > 0.01:
                        date_str = datetime.now().strftime("%b %d, %Y")
                        updated_price = existing_price + f" → {dist_str} ({date_str})"
                        worksheet.update_cell(row, COL_DISTRIBUTION_PRICE, updated_price)
            else:
                worksheet.update_cell(row, COL_DISTRIBUTION_PRICE, dist_str)

        return True

    except Exception as e:
        log(f"Error updating sheet row {row}: {e}", "ERROR")
        return False


def update_part_info(sheet_url: str, sheet_name: str, row: int,
                     part_name: str = None, brand: str = None,
                     appliance_type: str = None,
                     credentials_path: str = None):
    """
    Auto-fill part name, brand, and appliance type for new parts.
    Only fills cells that are currently empty.
    """
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        row_data = worksheet.row_values(row)

        updates = []
        if part_name and (len(row_data) < 2 or not row_data[1].strip()):
            updates.append({"range": f"B{row}", "values": [[part_name]]})
        if brand and (len(row_data) < 3 or not row_data[2].strip()):
            updates.append({"range": f"C{row}", "values": [[brand]]})
        if appliance_type and (len(row_data) < 4 or not row_data[3].strip()):
            updates.append({"range": f"D{row}", "values": [[appliance_type]]})

        if updates:
            worksheet.batch_update(updates)
        return True

    except Exception as e:
        log(f"Error updating part info for row {row}: {e}", "ERROR")
        return False


def update_benchmark_prices(sheet_url: str, sheet_name: str, row: int,
                             amazon_price: float = None,
                             google_price: float = None,
                             ebay_price: float = None,
                             credentials_path: str = None):
    """
    Update benchmark prices for a part. Only writes if price changed.
    Keeps price history with dates.
    """
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        date_str = datetime.now().strftime("%b %d, %Y")
        price_updates = [
            (COL_AMAZON_PRICE, amazon_price),
            (COL_GOOGLE_PRICE, google_price),
            (COL_EBAY_PRICE, ebay_price)
        ]

        for col, new_price in price_updates:
            if new_price is None:
                continue
            new_price_str = f"${new_price:.2f}"
            existing = worksheet.cell(row, col).value or ""
            if not existing:
                worksheet.update_cell(row, col, new_price_str)
            else:
                last_prices = re.findall(r'\$[\d.]+', existing)
                if last_prices:
                    last = float(last_prices[-1].replace("$", ""))
                    if abs(last - new_price) > 0.01:
                        updated = existing + f" → {new_price_str} ({date_str})"
                        worksheet.update_cell(row, col, updated)
                else:
                    worksheet.update_cell(row, col, new_price_str)

        return True

    except Exception as e:
        log(f"Error updating benchmark prices for row {row}: {e}", "ERROR")
        return False


def update_model_compatibility(sheet_url: str, sheet_name: str, row: int,
                                models_count: int, year_range: str,
                                credentials_path: str = None):
    """Update model compatibility columns."""
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        if models_count:
            worksheet.update_cell(row, COL_MODELS_COUNT, f"{models_count} models")
        if year_range:
            worksheet.update_cell(row, COL_YEAR_RANGE, year_range)
        return True

    except Exception as e:
        log(f"Error updating model compatibility for row {row}: {e}", "ERROR")
        return False


def sync_backup_sheet(sheet_url: str, main_sheet: str, backup_sheet: str,
                      credentials_path: str = None):
    """Sync the backup sheet with the main sheet."""
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

        # Copy all data from main to backup (excluding Anass Comment column)
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
                    credentials_path: str = None) -> tuple[bool, str]:
    """Test the Google Sheets connection. Returns (success, message)."""
    try:
        client = _get_client(credentials_path)
        sheet_id = _extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        cell_count = worksheet.row_count
        return True, f"Connected successfully. Sheet has {cell_count} rows."
    except Exception as e:
        return False, str(e)
