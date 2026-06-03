"""
screenshotter.py
Loads saved TradingView session, navigates to XAUUSD M1,
and takes a screenshot of the chart area every 60 seconds.

Requirements:
    pip install playwright
    playwright install chromium
"""

import json
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# ── Config ─────────────────────────────────────────────────────────────────
COOKIES_FILE   = "cookies.json"
SCREENSHOTS_DIR = "screenshots"
INTERVAL_SEC   = 60          # screenshot every N seconds
TV_CHART_URL   = "https://www.tradingview.com/chart/?symbol=XAUUSD&interval=1"

# CSS selector for TradingView's main chart canvas container.
# If this ever breaks, inspect the page and find the element wrapping the canvas.
CHART_SELECTOR = "#tv-attr-logo"   # fallback anchor — see note in take_screenshot()

# ── Helpers ─────────────────────────────────────────────────────────────────

def load_cookies(context):
    if not os.path.exists(COOKIES_FILE):
        raise FileNotFoundError(
            f"{COOKIES_FILE} not found. Run setup_session.py first."
        )
    with open(COOKIES_FILE) as f:
        cookies = json.load(f)
    context.add_cookies(cookies)
    print(f"Loaded {len(cookies)} cookies from {COOKIES_FILE}")


def take_screenshot(page, save_dir):
    """
    Screenshot strategy (tries in order):
    1. Target the chart layout container (most precise)
    2. Fall back to full page if selector not found
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = os.path.join(save_dir, f"xauusd_m1_{timestamp}.png")

    # TradingView chart area selectors — tries most specific first
    selectors = [
        ".chart-container",                        # main chart wrapper
        ".layout__area--center",                   # center pane
        '[data-name="legend-source-item"]',        # legend (less ideal)
    ]

    screenshotted = False
    for selector in selectors:
        try:
            element = page.query_selector(selector)
            if element:
                element.screenshot(path=filename)
                print(f"[{timestamp}] Saved chart screenshot → {filename}")
                screenshotted = True
                break
        except Exception:
            continue

    if not screenshotted:
        # Fallback: full page screenshot
        page.screenshot(path=filename, full_page=False)
        print(f"[{timestamp}] Fallback full-page screenshot → {filename}")

    return filename


def wait_for_chart(page, timeout_ms=30000):
    """Wait until the chart canvas is visible before starting the loop."""
    print("Waiting for chart to load...")
    try:
        page.wait_for_selector(".chart-container", timeout=timeout_ms)
        print("Chart loaded.")
    except Exception:
        print("Warning: chart selector timeout — proceeding anyway.")
    # Extra buffer for chart data to render
    page.wait_for_timeout(3000)


def dismiss_popups(page):
    """Dismiss common TradingView popups/banners if they appear."""
    popup_selectors = [
        '[data-name="close-button"]',
        '.js-button-close',
        'button[aria-label="Close"]',
    ]
    for sel in popup_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass


# ── Main loop ────────────────────────────────────────────────────────────────

def run():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,   # set False if you want to watch it
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        load_cookies(context)

        page = context.new_page()
        print(f"Navigating to {TV_CHART_URL}")
        page.goto(TV_CHART_URL, wait_until="networkidle")

        wait_for_chart(page)
        dismiss_popups(page)

        print(f"\nStarting screenshot loop — every {INTERVAL_SEC}s")
        print("Press Ctrl+C to stop.\n")

        screenshot_count = 0
        try:
            while True:
                loop_start = time.time()

                dismiss_popups(page)          # clear any banners before shot
                take_screenshot(page, SCREENSHOTS_DIR)
                screenshot_count += 1

                # Sleep for remainder of interval
                elapsed = time.time() - loop_start
                sleep_time = max(0, INTERVAL_SEC - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print(f"\nStopped. {screenshot_count} screenshots saved to ./{SCREENSHOTS_DIR}/")

        finally:
            browser.close()


if __name__ == "__main__":
    run()