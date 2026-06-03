"""
setup_session.py
Run this ONCE to log in to TradingView and save your session cookies.
After this, screenshotter.py will reuse the saved session automatically.
"""

import json
from playwright.sync_api import sync_playwright

COOKIES_FILE = "cookies.json"
TV_URL = "https://www.tradingview.com/chart/?symbol=XAUUSD&interval=1"


def setup_session():
    with sync_playwright() as p:
        # Launch visible browser so you can log in manually
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        print("Opening TradingView...")
        page.goto("https://www.tradingview.com")

        print("\n" + "="*50)
        print("ACTION REQUIRED:")
        print("1. Log in to your TradingView account in the browser")
        print("2. Make sure you can see a chart")
        print("3. Come back here and press ENTER")
        print("="*50 + "\n")
        input("Press ENTER after you have logged in...")

        # Navigate to the exact chart we want
        print("Navigating to XAUUSD M1 chart...")
        page.goto(TV_URL)
        page.wait_for_timeout(5000)  # Wait for chart to fully load

        # Save cookies and storage state
        cookies = context.cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)

        print(f"\nSession saved to {COOKIES_FILE}")
        print("You can now run screenshotter.py")

        browser.close()


if __name__ == "__main__":
    setup_session()