# Stock Checker Pro

Automated Marcone stock checking and price benchmarking desktop app for Windows.

---

## Quick Start

1. **Run `install.bat`** — double-click it to install all dependencies and create a desktop shortcut
2. **Open the app** — double-click "Stock Checker Pro" on your desktop
3. **Go to Settings** — enter your Marcone credentials and Google Sheet URL
4. **Set your schedule** — go to Scheduler and choose which days and times to run
5. **Done** — the app runs automatically in the background on your schedule

---

## What the App Does

| Feature | Description |
|---|---|
| Marcone Stock Check | Logs into Marcone and checks stock for every part in your sheet |
| Smart PN Recovery | If a part isn't found, tries variations and substitutions automatically |
| PN Memory | Remembers learned part number substitutions — never fails twice |
| Google Sheet Update | Writes stock history in format `6/2/26: 88 \| 5/26/26: OS` with bold numbers |
| Distribution Price | Calculates Marcone price × 0.79, tracks changes with dates |
| Benchmark Prices | Finds lowest new prices on Amazon, Google Shopping, and eBay weekly |
| Model Compatibility | Finds how many models a part fits and the year range |
| Auto-Fill New Parts | Automatically fills Part Name, Brand, and Appliance Type for new parts |
| Backup Sheet | Always keeps a backup sheet in sync after every run |
| Scheduler | Set different run times for each day of the week |
| Logs | Full history of every run with detailed logs |

---

## Google Sheet Column Layout

| Column | Content |
|---|---|
| A | Part Number |
| B | Part Name (auto-filled for new parts) |
| C | Brand (auto-filled for new parts) |
| D | Appliance Type (auto-filled for new parts) |
| E | Marcone Stock (history with dates, bold numbers) |
| F | Distribution Price (Marcone × 0.79, tracks changes) |
| G | Models Count (e.g. "87 models") |
| H | Year Range (e.g. "2014–2023") |
| I | Amazon Lowest Price (new only, weekly) |
| J | Google Shopping Lowest Price (no eBay, weekly) |
| K | eBay Lowest Price (new only, weekly) |
| L | Anass Comment — **NEVER TOUCHED BY APP** |

---

## Google Sheets Setup

The app uses the Google Sheets API. You need to provide a credentials file:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the Google Sheets API
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download the `client_secret.json` file
5. In the app Settings, browse to this file under "Google Credentials File"
6. The first time you connect, a browser window will open to authorize access

---

## Requirements

- Windows 10 or 11
- Python 3.11+ (installed by `install.bat` if not present)
- Internet connection (for Marcone and Google Sheets)
- Google Chrome (for Marcone automation)

---

## App Data Location

All app data is stored in `C:\Users\YourName\StockCheckerPro\`:
- `config\settings.json` — your settings (credentials stored encrypted)
- `data\pn_memory.json` — learned part number substitutions
- `logs\` — run history and detailed logs

---

## Version

v1.0.0 — Built by Manus AI
