"""Open the Streamlit app in a headless browser and wake it if it is asleep.

Used by .github/workflows/keep-alive.yml. Reads the app URL from APP_URL.
"""

from __future__ import annotations

import os
import re
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

WAKE_BUTTON = re.compile(r"get this app back up", re.IGNORECASE)
DEMO_BUTTON = re.compile(r"try the demo", re.IGNORECASE)


def main() -> int:
    url = os.environ.get("APP_URL", "").strip()
    if not url:
        print("APP_URL is empty - set the STREAMLIT_APP_URL repository variable.")
        return 1

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        print(f"Opening {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        button = page.get_by_role("button", name=WAKE_BUTTON)
        try:
            button.wait_for(state="visible", timeout=15_000)
        except PlaywrightTimeout:
            print("App is awake - no wake-up button found.")
        else:
            print("App was asleep - clicking the wake-up button.")
            button.click()
            # Give the container time to boot before the browser goes away.
            page.wait_for_timeout(90_000)

        # Click "Try the demo" so the visit also runs real database queries -
        # free Supabase projects pause after about a week without any.
        # Streamlit Cloud renders the app inside an iframe, so search every frame.
        clicked = False
        for _ in range(30):  # poll for up to ~60 seconds while the app loads
            for frame in page.frames:
                demo = frame.get_by_role("button", name=DEMO_BUTTON)
                if demo.count() and demo.first.is_visible():
                    demo.first.click()
                    clicked = True
                    break
            if clicked:
                print("Clicked 'Try the demo' to exercise the database.")
                break
            page.wait_for_timeout(2_000)
        else:
            print("'Try the demo' button not found - page visit only.")

        # Stay connected briefly so the visit registers as real traffic.
        page.wait_for_timeout(20_000)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
