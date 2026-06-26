"""
Debug helper for Stock Checker Pro.

Runs a VISIBLE (non-headless) Chrome so you can watch what happens, logs into
Marcone, then searches one part. It saves the page HTML and screenshots into a
folder called 'debug_out' so we can see the real page structure.

Run from:  C:\\Anass App\\StockCheckerPro
    python debug_marcone.py
"""
import sys
import os
import time

sys.path.insert(0, os.getcwd())

from config.settings import load_settings, decrypt_password
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

OUT = os.path.join(os.getcwd(), "debug_out")
os.makedirs(OUT, exist_ok=True)

LOGIN_URL = "https://my.marcone.com/UserLogin"
HOME_URL = "https://beta.marcone.com/Home/Index"
TEST_PN = "W11598152"


def save(name, driver):
    """Save current page HTML + screenshot + URL."""
    try:
        with open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception as e:
        print("  (could not save html:", e, ")")
    try:
        driver.save_screenshot(os.path.join(OUT, name + ".png"))
    except Exception as e:
        print("  (could not save png:", e, ")")
    print(f"  saved {name}  ->  URL now: {driver.current_url}")


def main():
    s = load_settings()
    user = s["marcone"]["username"]
    pwd = decrypt_password(s["marcone"]["password"])
    print(f"Username from settings: {user!r}")
    print(f"Password present: {'yes' if pwd else 'NO - empty!'}")

    options = Options()
    # VISIBLE so the user can watch
    options.add_argument("--window-size=1400,1000")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                              options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        print("\n1) Opening login page...")
        driver.get(LOGIN_URL)
        time.sleep(4)
        save("01_login_page", driver)

        # List all input fields so we can see their names/ids
        print("\n2) Input fields on the login page:")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for el in inputs:
            try:
                print(f"   type={el.get_attribute('type')!r} "
                      f"name={el.get_attribute('name')!r} "
                      f"id={el.get_attribute('id')!r} "
                      f"placeholder={el.get_attribute('placeholder')!r}")
            except Exception:
                pass

        # Fill username (first text/email input) and password
        print("\n3) Filling in credentials...")
        user_field = None
        for el in inputs:
            t = (el.get_attribute("type") or "").lower()
            if t in ("text", "email", ""):
                user_field = el
                break
        pwd_field = None
        for el in inputs:
            if (el.get_attribute("type") or "").lower() == "password":
                pwd_field = el
                break

        if user_field is None or pwd_field is None:
            print("   !! Could not find username or password field. "
                  "Check 01_login_page.html")
        else:
            user_field.clear(); user_field.send_keys(user)
            pwd_field.clear(); pwd_field.send_keys(pwd)
            time.sleep(1)
            pwd_field.send_keys(Keys.RETURN)
            print("   submitted (pressed Enter). Waiting for login...")
            time.sleep(8)
            save("02_after_login", driver)
            print(f"   URL after login: {driver.current_url}")
            page = driver.page_source.lower()
            print("   'hello' on page:", "hello" in page)
            print("   username on page:", str(user).lower() in page)

        # Go to home / try the search box
        print("\n4) Opening beta home & looking for the search box...")
        driver.get(HOME_URL)
        time.sleep(5)
        save("03_home", driver)
        print(f"   home URL: {driver.current_url}")

        search_inputs = driver.find_elements(
            By.CSS_SELECTOR, "input[type='text'], input[type='search']")
        print("   text/search inputs on home:")
        for el in search_inputs:
            try:
                print(f"     name={el.get_attribute('name')!r} "
                      f"id={el.get_attribute('id')!r} "
                      f"placeholder={el.get_attribute('placeholder')!r}")
            except Exception:
                pass

        # Try searching the test PN
        print(f"\n5) Searching for {TEST_PN}...")
        box = None
        for el in search_inputs:
            ph = (el.get_attribute("placeholder") or "").lower()
            if "part" in ph or "model" in ph or "search" in ph:
                box = el
                break
        if box is None and search_inputs:
            box = search_inputs[0]

        if box is not None:
            box.clear(); box.send_keys(TEST_PN)
            time.sleep(0.5)
            box.send_keys(Keys.RETURN)
            time.sleep(7)
            save("04_search_result", driver)
            print(f"   result URL: {driver.current_url}")
        else:
            print("   !! No search box found on home. Trying direct product URL.")

        # Also try the direct product URL with Make=WPL
        print(f"\n6) Trying direct product URL for {TEST_PN} (Make=WPL)...")
        driver.get(f"https://beta.marcone.com/Product/Detail?Part={TEST_PN}&Make=WPL")
        time.sleep(6)
        save("05_product_direct", driver)
        print(f"   product URL: {driver.current_url}")

        print("\nDONE. Look inside the 'debug_out' folder.")
        print("Leave this browser open for a few seconds so screenshots save.")
        time.sleep(3)

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
