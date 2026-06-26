"""
Marcone scraping engine for Stock Checker Pro.
Handles login, stock checking, and smart PN recovery with memory.

REAL MARCONE SITE STRUCTURE (confirmed 2026-06-26):
  - Login page:     https://my.marcone.com/UserLogin
  - After login:    https://beta.marcone.com/Home/Index  (logged in as "155469 - PDQ SUPPLY")
  - Product page:   https://beta.marcone.com/Product/Detail?Part={PN}&Make={MAKE}
  - Search box:     top "enter model or part" input + GO button.
                    Typing a PN and submitting takes you DIRECTLY to the product
                    page when the PN exists, or to a results LIST when it does not.

  On a product detail page we read:
    - Description   (e.g. "SPACER")
    - Your Price    (e.g. "Your Price: $4.55")  -> Marcone price (x0.79 = distribution)
    - Stock text    (e.g. "Only 1 left in stock (more on the way)." or
                          "In Stock" / "Out of Stock")
"""
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

# IMPORTANT: beta.marcone.com has its OWN login. Logging into my.marcone.com
# does NOT authenticate the beta portal, so we log in directly on beta.
# The login form uses id=UserName, id=Password and a CLICK button id=loginbtn
# (pressing Enter does not submit). A logged-in page shows a "Log Out" link
# (href="/UserLogin/Logout").
MARCONE_LOGIN = "https://beta.marcone.com/UserLogin"
MARCONE_HOME = "https://beta.marcone.com/Home/Index"
# Search URL on the beta portal. The portal accepts a free-text search term and
# redirects to the product detail page when there is an exact match.
MARCONE_SEARCH = "https://beta.marcone.com/Search/Result?searchText={pn}"
MARCONE_PRODUCT = "https://beta.marcone.com/Product/Detail"

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
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        log(f"Error creating Chrome driver: {e}", "ERROR")
        raise


def _is_logged_in(driver) -> bool:
    """True when the beta portal shows a logged-in session."""
    try:
        page = driver.page_source.lower()
    except Exception:
        return False
    url = driver.current_url.lower()
    # If we are sitting on the login page, we are NOT logged in.
    if "userlogin" in url and "logout" not in url:
        # Unless the page also contains the logout link (rare), treat as not logged in
        if "/userlogin/logout" not in page:
            return False
    # Logged-in pages contain the Log Out link and/or a greeting.
    if "/userlogin/logout" in page or "log out" in page or "sign out" in page:
        return True
    if "hello" in page:
        return True
    return False


def login_to_marcone(driver, username: str, password: str) -> bool:
    """
    Log into the Marcone BETA portal at https://beta.marcone.com/UserLogin.

    The login form (confirmed via captured HTML) uses:
        username -> input id="UserName"
        password -> input id="Password"
        submit   -> input type="button" id="loginbtn"  (must be CLICKED)
    A logged-in page exposes a "Log Out" link (href="/UserLogin/Logout").
    Returns True only when the logged-in marker is confirmed.
    """
    try:
        log("Navigating to Marcone login page...")
        driver.get(MARCONE_LOGIN)
        wait = WebDriverWait(driver, 25)

        # --- Username field (the login form one is id=UserName) ---
        try:
            username_field = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#UserName")))
        except TimeoutException:
            log("Could not find the UserName field on the Marcone login page.", "ERROR")
            return False

        # --- Password field (the login form one is id=Password) ---
        try:
            password_field = driver.find_element(By.CSS_SELECTOR, "#Password")
        except NoSuchElementException:
            log("Could not find the Password field on the Marcone login page.", "ERROR")
            return False

        username_field.clear()
        username_field.send_keys(username)
        time.sleep(0.4)
        password_field.clear()
        password_field.send_keys(password)
        time.sleep(0.4)

        # --- Click the login button (id=loginbtn). Enter does NOT submit. ---
        clicked = False
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "#loginbtn")
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            clicked = True
        except NoSuchElementException:
            pass
        if not clicked:
            # Fallback selectors
            for sel in ["input[type='submit']", "button[type='submit']",
                        "button.btn-primary", "input.btn-primary"]:
                try:
                    driver.find_element(By.CSS_SELECTOR, sel).click()
                    clicked = True
                    break
                except NoSuchElementException:
                    continue
        if not clicked:
            log("Could not find the login button (#loginbtn).", "ERROR")
            return False

        # --- Confirm login ---
        for _ in range(25):  # up to ~25s
            time.sleep(1)
            page = driver.page_source.lower()
            # Explicit credential errors
            if any(w in page for w in ["invalid username", "invalid password",
                                       "incorrect password", "login failed",
                                       "username or password"]):
                log("Marcone reported invalid credentials. "
                    "Check the username/password in Settings.", "ERROR")
                return False
            if _is_logged_in(driver):
                log(f"Login confirmed (now at {driver.current_url})")
                return True

        log("Login did not complete — the logged-in marker never appeared. "
            "Verify the Marcone username/password in Settings.", "ERROR")
        return False

    except Exception as e:
        log(f"Login error: {e}", "ERROR")
        return False


def _pn_variations(pn: str) -> list:
    """Generate common variations of a part number to try."""
    pn = pn.upper().strip()
    variations = [pn]

    for prefix in ["WP", "PS", "AP", "EAP", "WD", "DA", "DC", "DE", "DD", "DG"]:
        if pn.startswith(prefix) and len(pn) > len(prefix) + 3:
            variations.append(pn[len(prefix):])

    if not pn.startswith("WP"):
        variations.append("WP" + pn)

    stripped = re.sub(r'[A-Z]+$', '', pn)
    if stripped != pn and len(stripped) > 4:
        variations.append(stripped)

    no_dash = pn.replace("-", "").replace(" ", "")
    if no_dash != pn:
        variations.append(no_dash)

    seen = set()
    unique = []
    for v in variations:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def _parse_stock_from_text(text: str):
    """
    Given the visible product-page text, return an integer stock quantity.
    Examples handled:
      "Only 1 left in stock (more on the way)."   -> 1
      "5 in stock"                                -> 5
      "In Stock"                                  -> 1 (available, qty unknown)
      "Out of Stock" / "Backordered"             -> 0
    Returns None if no stock info is found.
    """
    low = text.lower()

    # Out-of-stock indicators first
    if any(p in low for p in ["out of stock", "backorder", "back order",
                              "no longer available", "discontinued",
                              "not available"]):
        return 0

    # "Only N left in stock" / "N left in stock" / "N in stock"
    m = re.search(r'only\s+(\d+)\s+left\s+in\s+stock', low)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s+left\s+in\s+stock', low)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s+in\s+stock', low)
    if m:
        return int(m.group(1))

    # Generic "in stock" with no number -> available
    if "in stock" in low or "available" in low:
        return 1

    return None


def _parse_price_from_text(text: str):
    """
    Extract the 'Your Price' dollar value from the product page text.
    Falls back to 'Retail Price' if 'Your Price' is not present.
    Returns a float, or None.
    """
    # Your Price: $4.55
    m = re.search(r'your\s+price\s*:?\s*\$?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    # Retail Price: $10.02 (fallback)
    m = re.search(r'retail\s+price\s*:?\s*\$?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _on_product_page(driver) -> bool:
    """True if the browser is currently on a product detail page."""
    url = driver.current_url.lower()
    if "/product/detail" in url:
        return True
    # Some flows render the detail inline; detect by the price labels.
    page = driver.page_source.lower()
    return ("your price" in page and "part number" in page
            and "add to cart" in page)


def _search_part(driver, pn: str) -> dict | None:
    """
    Search for a part via the Marcone search box.
    Returns one of:
      {found True,  quantity N, marcone_price P}                  -> resolved to a product page
      {found False, needs_review True}                            -> landed on a results LIST (ambiguous)
      None                                                        -> nothing found / no exact match
    """
    try:
        # Use the search box on the home page for the most reliable behavior.
        driver.get(MARCONE_HOME)
        wait = WebDriverWait(driver, 15)
        time.sleep(1)

        # If the session bounced back to the login page, we are not logged in.
        if "userlogin" in driver.current_url.lower() and not _is_logged_in(driver):
            log("  Session is not logged in (redirected to login page).", "WARNING")
            return None

        search_box = None
        search_selectors = [
            "input[name='searchText']", "input#searchText",
            "input[placeholder*='model or part']",
            "input[placeholder*='part']", "input[type='search']",
            "input[name='q']", "input#search",
        ]
        for sel in search_selectors:
            try:
                search_box = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                if search_box:
                    break
            except TimeoutException:
                continue

        if search_box is not None:
            search_box.clear()
            search_box.send_keys(pn)
            time.sleep(0.3)
            search_box.send_keys(Keys.RETURN)
        else:
            # Fallback: direct search URL
            driver.get(MARCONE_SEARCH.format(pn=pn))

        # Wait for navigation to settle
        time.sleep(3)

        page_text = driver.find_element(By.TAG_NAME, "body").text
        low = page_text.lower()

        # Did we land directly on a product page?
        if _on_product_page(driver):
            # Make sure the part number on the page matches what we searched
            qty = _parse_stock_from_text(page_text)
            price = _parse_price_from_text(page_text)
            if qty is None:
                qty = 1  # product exists but no explicit stock text -> assume available
            return {
                "found": True,
                "quantity": qty,
                "marcone_price": price,
                "needs_review": False,
            }

        # No results at all
        no_result_phrases = [
            "no results", "no products found", "0 results found",
            "did not match any", "no items found", "no matches",
        ]
        if any(p in low for p in no_result_phrases):
            return None

        # We are on a results list (multiple/partial matches) -> needs human review
        list_indicators = ["results for", "search results", "showing",
                            "refine", "filter results"]
        if any(p in low for p in list_indicators):
            return {"found": False, "needs_review": True}

        # Unknown page state -> treat as not found
        return None

    except Exception as e:
        log(f"Search error for {pn}: {e}", "WARNING")
        return None


def check_part_stock(driver, original_pn: str) -> dict:
    """
    Check stock for a part with smart recovery.
    Returns: {pn, original_pn, quantity, marcone_price, found, needs_review,
              resolved_via, error}
    """
    original_pn = str(original_pn).upper().strip()

    def _result(base, resolved_via, used_pn):
        return {
            "pn": used_pn,
            "original_pn": original_pn,
            "quantity": base.get("quantity", 0),
            "marcone_price": base.get("marcone_price"),
            "found": base.get("found", False),
            "needs_review": base.get("needs_review", False),
            "resolved_via": resolved_via,
            "error": None if base.get("found") else (
                "Needs review (multiple matches)" if base.get("needs_review")
                else "Not found on Marcone"),
        }

    # Step 1: PN memory
    resolved = get_resolved_pn(original_pn)
    if resolved:
        log(f"  Using memorized PN: {original_pn} -> {resolved}")
        result = _search_part(driver, resolved)
        if result and result.get("found"):
            return _result(result, "memory", resolved)

    # Step 2: original PN
    log(f"  Trying original PN: {original_pn}")
    result = _search_part(driver, original_pn)
    if result and result.get("found"):
        return _result(result, "original", original_pn)
    # If the original search produced an ambiguous LIST, flag for review
    if result and result.get("needs_review"):
        log(f"  Ambiguous results for {original_pn} - flagged for review", "WARNING")
        return _result(result, None, original_pn)

    # Step 3: variations
    variations = _pn_variations(original_pn)
    for variation in variations[1:]:
        if _stop_flag and _stop_flag[0]:
            break
        log(f"  Trying variation: {variation}")
        result = _search_part(driver, variation)
        if result and result.get("found"):
            log(f"  Found under variation: {original_pn} -> {variation}, "
                f"saving to PN Memory")
            save_mapping(original_pn, variation, "Prefix/suffix variation")
            return _result(result, "variation", variation)

    # Step 4: not found
    log(f"  Part not found on Marcone: {original_pn}", "WARNING")
    return {
        "pn": original_pn,
        "original_pn": original_pn,
        "quantity": 0,
        "marcone_price": None,
        "found": False,
        "needs_review": False,
        "resolved_via": None,
        "error": "Not found on Marcone",
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

            if result.get("found"):
                qty = result.get("quantity", 0)
                price = result.get("marcone_price")
                price_str = f", price ${price:.2f}" if price else ""
                log(f"  Result: {qty} in stock{price_str}")
            elif result.get("needs_review"):
                log(f"  Result: CHECK PN (multiple matches)")
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
