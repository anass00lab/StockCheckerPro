"""
Benchmark price checker for Stock Checker Pro.
Finds lowest prices on Amazon, Google Shopping, and eBay (new only).
"""
import requests
import re
import time
from bs4 import BeautifulSoup
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.logger import log

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}


def _extract_price(text: str) -> float | None:
    """Extract a price value from a text string."""
    if not text:
        return None
    matches = re.findall(r'\$?\s*(\d{1,4}(?:\.\d{2})?)', text.replace(",", ""))
    if matches:
        try:
            return float(matches[0])
        except ValueError:
            return None
    return None


def get_amazon_price(part_number: str, part_name: str = "") -> float | None:
    """Get the lowest new price from Amazon for a part."""
    try:
        query = f"{part_number} appliance part"
        if part_name:
            query = f"{part_number} {part_name}"
        url = f"https://www.amazon.com/s?k={requests.utils.quote(query)}&rh=p_n_condition-type%3A1294423011"

        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        prices = []
        # Amazon search result price selectors
        price_elements = soup.select(".a-price .a-offscreen, .a-price-whole")
        for el in price_elements:
            price = _extract_price(el.get_text())
            if price and 0.5 < price < 5000:
                prices.append(price)

        return min(prices) if prices else None

    except Exception as e:
        log(f"Amazon price check error for {part_number}: {e}", "WARNING")
        return None


def get_google_shopping_price(part_number: str, part_name: str = "") -> float | None:
    """
    Get the lowest new price from Google Shopping (excluding eBay).
    Uses SerpAPI-style scraping.
    """
    try:
        query = f"{part_number} appliance part buy new"
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=shop&tbs=new:1"

        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        prices = []
        # Google Shopping price elements
        price_elements = soup.select(".a8Pemb, .kHxwFf, [class*='price']")
        for el in price_elements:
            # Skip eBay listings
            parent_text = el.find_parent().get_text().lower() if el.find_parent() else ""
            if "ebay" in parent_text:
                continue
            price = _extract_price(el.get_text())
            if price and 0.5 < price < 5000:
                prices.append(price)

        return min(prices) if prices else None

    except Exception as e:
        log(f"Google Shopping price check error for {part_number}: {e}", "WARNING")
        return None


def get_ebay_price(part_number: str, part_name: str = "") -> float | None:
    """
    Get the lowest NEW (not used, not open box) price from eBay.
    Strictly filters to new condition only.
    """
    try:
        # eBay search with New condition filter (LH_ItemCondition=1000)
        query = f"{part_number} appliance part"
        url = (f"https://www.ebay.com/sch/i.html?_nkw={requests.utils.quote(query)}"
               f"&LH_ItemCondition=1000&LH_BIN=1&_sop=15")  # New only, Buy It Now, lowest price

        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        prices = []
        items = soup.select(".s-item")
        for item in items:
            # Verify condition is NEW
            condition_el = item.select_one(".SECONDARY_INFO, .s-item__subtitle")
            if condition_el:
                condition_text = condition_el.get_text().lower()
                # Skip used, open box, refurbished, for parts
                skip_conditions = ["used", "open box", "refurbished", "for parts", "pre-owned",
                                   "seller refurbished", "parts only"]
                if any(c in condition_text for c in skip_conditions):
                    continue

            price_el = item.select_one(".s-item__price")
            if price_el:
                price_text = price_el.get_text()
                # Skip price ranges (usually used items)
                if "to" in price_text.lower():
                    continue
                price = _extract_price(price_text)
                if price and 0.5 < price < 5000:
                    prices.append(price)

        return min(prices) if prices else None

    except Exception as e:
        log(f"eBay price check error for {part_number}: {e}", "WARNING")
        return None


def get_model_compatibility(part_number: str, part_name: str = "") -> tuple[int | None, str | None]:
    """
    Get model compatibility info from RepairClinic and PartSelect.
    Returns (model_count, year_range) e.g. (87, "2014-2023")
    """
    try:
        # Try RepairClinic first
        url = f"https://www.repairclinic.com/PartDetail/{part_number}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")

            # Look for "fits X models" text
            fits_text = soup.find(string=re.compile(r'fits\s+\d+\s+model', re.I))
            model_count = None
            if fits_text:
                count_match = re.search(r'(\d+)\s+model', fits_text, re.I)
                if count_match:
                    model_count = int(count_match.group(1))

            # Look for year range in model list
            years = []
            year_elements = soup.select("[class*='model'] td, [class*='year']")
            for el in year_elements:
                year_matches = re.findall(r'\b(19|20)\d{2}\b', el.get_text())
                years.extend([int(y) for y in year_matches])

            if model_count or years:
                year_range = None
                if years:
                    year_range = f"{min(years)}-{max(years)}"
                return model_count, year_range

        # Try PartSelect as fallback
        url2 = f"https://www.partselect.com/PS{part_number}-Part.htm"
        response2 = requests.get(url2, headers=HEADERS, timeout=15)
        if response2.status_code == 200:
            soup2 = BeautifulSoup(response2.text, "lxml")
            years = []
            for el in soup2.select("[class*='year'], td"):
                year_matches = re.findall(r'\b(19|20)\d{2}\b', el.get_text())
                years.extend([int(y) for y in year_matches])

            model_elements = soup2.find_all(string=re.compile(r'\d+\s+model', re.I))
            model_count = None
            for el in model_elements:
                m = re.search(r'(\d+)\s+model', el, re.I)
                if m:
                    model_count = int(m.group(1))
                    break

            if model_count or years:
                year_range = f"{min(years)}-{max(years)}" if years else None
                return model_count, year_range

        return None, None

    except Exception as e:
        log(f"Model compatibility check error for {part_number}: {e}", "WARNING")
        return None, None


def get_part_info(part_number: str) -> dict:
    """
    Get part name, brand, and appliance type from online sources.
    Used to auto-fill new parts.
    """
    try:
        url = f"https://www.repairclinic.com/PartDetail/{part_number}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")

            # Extract part name
            name_el = soup.select_one("h1, .part-name, [class*='part-title']")
            part_name = name_el.get_text().strip() if name_el else ""

            # Extract brand
            brand_el = soup.select_one("[class*='brand'], [itemprop='brand']")
            brand = brand_el.get_text().strip() if brand_el else ""

            # Extract appliance type
            appliance_el = soup.select_one("[class*='appliance'], [class*='category']")
            appliance = appliance_el.get_text().strip() if appliance_el else ""

            if part_name or brand:
                return {
                    "part_name": part_name[:100] if part_name else "",
                    "brand": brand[:50] if brand else "",
                    "appliance_type": appliance[:50] if appliance else ""
                }

        # Try PartSelect
        url2 = f"https://www.partselect.com/search.aspx?SearchTerm={part_number}"
        response2 = requests.get(url2, headers=HEADERS, timeout=15)
        if response2.status_code == 200:
            soup2 = BeautifulSoup(response2.text, "lxml")
            name_el = soup2.select_one(".part-name, h1, .pd-title")
            if name_el:
                return {
                    "part_name": name_el.get_text().strip()[:100],
                    "brand": "",
                    "appliance_type": ""
                }

        return {}

    except Exception as e:
        log(f"Part info lookup error for {part_number}: {e}", "WARNING")
        return {}


def run_benchmark_check(parts: list, sheet_url: str, sheet_name: str,
                        credentials_path: str = None,
                        progress_callback=None, stop_flag=None) -> int:
    """
    Run a full benchmark price check for all parts.
    Updates the Google Sheet with results.
    Returns number of parts updated.
    """
    from core.sheets_engine import update_benchmark_prices

    updated = 0
    total = len(parts)

    for i, part in enumerate(parts, 1):
        if stop_flag and stop_flag[0]:
            log("Benchmark check stopped by user.")
            break

        pn = part.get("part_number", "")
        name = part.get("part_name", "")
        row = part.get("row", 0)

        if not pn or not row:
            continue

        log(f"Benchmark check {i}/{total}: {pn}")
        if progress_callback:
            progress_callback(i, total, pn, "benchmark")

        amazon = get_amazon_price(pn, name)
        time.sleep(1)
        google = get_google_shopping_price(pn, name)
        time.sleep(1)
        ebay = get_ebay_price(pn, name)
        time.sleep(1)

        log(f"  Amazon: {'$' + str(amazon) if amazon else 'Not found'} | "
            f"Google: {'$' + str(google) if google else 'Not found'} | "
            f"eBay: {'$' + str(ebay) if ebay else 'Not found'}")

        if amazon or google or ebay:
            update_benchmark_prices(
                sheet_url, sheet_name, row,
                amazon_price=amazon,
                google_price=google,
                ebay_price=ebay,
                credentials_path=credentials_path
            )
            updated += 1

        time.sleep(2)

    return updated
