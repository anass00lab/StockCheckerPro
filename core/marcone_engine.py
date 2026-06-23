"""
Marcone scraping engine for Stock Checker Pro.
Handles login, stock checking, and smart PN recovery with memory.
"""
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.pn_memory import get_resolved_pn, save_mapping
from data.logger import log

MARCONE_BASE = "https://www.marcone.com"
MARCONE_LOGIN = "https://www.marcone.com/login"
MARCONE_SEARCH = "https://www.marcone.com/search?q={pn}"

# Progress callback for UI
_progress_callback = None
_stop_flag = [False]


def set_progress_callback(callback):
    global _progress_callback
    _progress_callback = callback


def set_stop_flag(flag_list):
    global _stop_flag
    _stop_flag = flag_list


def _notify_progress(current, total, part_number, status):
    if _progress_callback:
        try:
            _progress_callback(current, total, part_number, status)
        except Exception:
            pass


def _create_driver(headless=True):
    """Create a Chrome WebDriver instance."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        log(f"Error creating Chrome driver: {e}", "ERROR")
        raise


def login_to_marcone(driver, username: str, password: str) -> bool:
    """Log into Marcone website. Returns True on success."""
    try:
        log("Navigating to Marcone login page...")
        driver.get(MARCONE_LOGIN)
        wait = WebDriverWait(driver, 15)

        # Wait for login form
        try:
            email_field = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[id*='email'], input[name='username']")
            ))
        except TimeoutException:
            # Try alternative selectors
            email_field = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='text']")
            ))

        email_field.clear()
        email_field.send_keys(username)
        time.sleep(0.5)

        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        password_field.clear()
        password_field.send_keys(password)
        time.sleep(0.5)

        # Submit
        submit_btn = driver.find_element(By.CSS_SELECTOR,
            "button[type='submit'], input[type='submit'], button.login-btn, button.btn-login")
        submit_btn.click()

        # Wait for successful login (URL change or dashboard element)
        time.sleep(3)
        current_url = driver.current_url.lower()
        if "login" not in current_url or "dashboard" in current_url or "account" in current_url:
            log("Login successful")
            return True
        else:
            # Check for error message
            try:
                error = driver.find_element(By.CSS_SELECTOR, ".error, .alert-danger, [class*='error']")
                log(f"Login failed: {error.text}", "ERROR")
            except NoSuchElementException:
                log("Login may have succeeded (URL unchanged)", "WARNING")
            return True  # Optimistic — proceed and fail gracefully per part

    except Exception as e:
        log(f"Login error: {e}", "ERROR")
        return False


def _pn_variations(pn: str) -> list:
    """Generate common variations of a part number to try."""
    pn = pn.upper().strip()
    variations = [pn]

    # Remove common OEM prefixes
    for prefix in ["WP", "PS", "AP", "EAP", "WD", "DA", "DC", "DE", "DD", "DG"]:
        if pn.startswith(prefix) and len(pn) > len(prefix) + 3:
            variations.append(pn[len(prefix):])

    # Add WP prefix if not present
    if not pn.startswith("WP"):
        variations.append("WP" + pn)

    # Remove trailing letters (e.g. W10295370A -> W10295370)
    stripped = re.sub(r'[A-Z]+$', '', pn)
    if stripped != pn and len(stripped) > 4:
        variations.append(stripped)

    # Remove dashes and spaces
    no_dash = pn.replace("-", "").replace(" ", "")
    if no_dash != pn:
        variations.append(no_dash)

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for v in variations:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def _search_part(driver, pn: str) -> dict | None:
    """
    Search for a part on Marcone and return stock info.
    Returns dict with keys: pn, quantity, found, superseded_by
    Returns None if not found.
    """
    try:
        url = MARCONE_SEARCH.format(pn=pn)
        driver.get(url)
        time.sleep(2)

        wait = WebDriverWait(driver, 10)
        page_source = driver.page_source.lower()

        # Check for "no results" indicators
        no_result_phrases = ["no results", "no products found", "0 results", "not found", "no items found"]
        if any(phrase in page_source for phrase in no_result_phrases):
            return None

        # Try to find product/stock info
        # Look for quantity/availability elements
        try:
            # Look for stock quantity
            qty_selectors = [
                "[class*='stock']", "[class*='quantity']", "[class*='availability']",
                "[class*='qty']", "[data-stock]", "[class*='inventory']"
            ]
            for selector in qty_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    text = el.text.strip()
                    if text:
                        # Extract number from text
                        numbers = re.findall(r'\d+', text)
                        if numbers:
                            qty = int(numbers[0])
                            return {"pn": pn, "quantity": qty, "found": True, "superseded_by": None}
                        elif any(word in text.lower() for word in ["in stock", "available"]):
                            return {"pn": pn, "quantity": 1, "found": True, "superseded_by": None}
                        elif any(word in text.lower() for word in ["out of stock", "unavailable", "0"]):
                            return {"pn": pn, "quantity": 0, "found": True, "superseded_by": None}
        except Exception:
            pass

        # Check for superseded/replaced by notice
        supersede_patterns = ["superseded by", "replaced by", "use part", "order instead"]
        for pattern in supersede_patterns:
            if pattern in page_source:
                # Try to extract the new PN
                try:
                    links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/part/'], a[href*='/product/']")
                    for link in links:
                        href = link.get_attribute("href")
                        if href:
                            new_pn = href.split("/")[-1].upper()
                            if new_pn and new_pn != pn:
                                return {"pn": pn, "quantity": 0, "found": True, "superseded_by": new_pn}
                except Exception:
                    pass

        # If page loaded without "no results", assume found but check for add-to-cart
        add_to_cart = driver.find_elements(By.CSS_SELECTOR,
            "button[class*='cart'], button[class*='add'], [class*='add-to-cart']")
        if add_to_cart:
            return {"pn": pn, "quantity": 1, "found": True, "superseded_by": None}

        return None

    except Exception as e:
        log(f"Search error for {pn}: {e}", "WARNING")
        return None


def check_part_stock(driver, original_pn: str) -> dict:
    """
    Check stock for a part with full smart recovery.
    Returns: {pn, original_pn, quantity, found, resolved_via, error}
    """
    original_pn = original_pn.upper().strip()

    # Step 1: Check PN memory first
    resolved = get_resolved_pn(original_pn)
    if resolved:
        log(f"  Using memorized PN: {original_pn} → {resolved}")
        result = _search_part(driver, resolved)
        if result:
            result["original_pn"] = original_pn
            result["resolved_via"] = "memory"
            return result

    # Step 2: Try original PN
    log(f"  Trying original PN: {original_pn}")
    result = _search_part(driver, original_pn)
    if result:
        if result.get("superseded_by"):
            new_pn = result["superseded_by"]
            log(f"  Part superseded: {original_pn} → {new_pn}, saving to PN Memory")
            save_mapping(original_pn, new_pn, "Superseded by newer PN")
            # Search for the new PN
            new_result = _search_part(driver, new_pn)
            if new_result:
                new_result["original_pn"] = original_pn
                new_result["resolved_via"] = "superseded"
                return new_result
        result["original_pn"] = original_pn
        result["resolved_via"] = "original"
        return result

    # Step 3: Try variations
    variations = _pn_variations(original_pn)
    for variation in variations[1:]:  # Skip first (already tried original)
        log(f"  Trying variation: {variation}")
        result = _search_part(driver, variation)
        if result:
            log(f"  Found under variation: {original_pn} → {variation}, saving to PN Memory")
            save_mapping(original_pn, variation, "Prefix/suffix variation")
            result["original_pn"] = original_pn
            result["resolved_via"] = "variation"
            return result

    # Step 4: Not found anywhere
    log(f"  Part not found on Marcone: {original_pn}", "WARNING")
    return {
        "pn": original_pn,
        "original_pn": original_pn,
        "quantity": 0,
        "found": False,
        "resolved_via": None,
        "error": "Not found on Marcone"
    }


def run_stock_check(username: str, password: str, parts: list,
                    progress_callback=None, stop_flag=None) -> list:
    """
    Run a full stock check for all parts.
    parts: list of part number strings
    Returns list of result dicts.
    """
    global _progress_callback, _stop_flag
    if progress_callback:
        _progress_callback = progress_callback
    if stop_flag:
        _stop_flag = stop_flag

    results = []
    driver = None

    try:
        log("Creating browser session...")
        driver = _create_driver(headless=True)

        log("Logging into Marcone...")
        if not login_to_marcone(driver, username, password):
            log("Failed to log into Marcone. Aborting run.", "ERROR")
            return []

        total = len(parts)
        for i, pn in enumerate(parts, 1):
            if _stop_flag and _stop_flag[0]:
                log("Run stopped by user.")
                break

            pn = str(pn).strip()
            if not pn:
                continue

            log(f"Checking part {i}/{total}: {pn}")
            _notify_progress(i, total, pn, "checking")

            result = check_part_stock(driver, pn)
            results.append(result)

            qty = result.get("quantity", 0)
            found = result.get("found", False)
            if found:
                status = str(qty) if qty > 0 else "OS"
                log(f"  Result: {status}")
            else:
                log(f"  Result: Not found on Marcone")

            _notify_progress(i, total, pn, "done")
            time.sleep(1)  # Polite delay between requests

    except Exception as e:
        log(f"Critical error during stock check: {e}", "ERROR")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return results
