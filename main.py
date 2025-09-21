# This script uses Playwright to concurrently open web pages from a file
# and click two specific buttons on a potentially laggy site.
# It includes robust error handling, crash recovery, and performance optimizations.

import asyncio
import os
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

# --- IMPORTANT: USER CONFIGURATION ---
# These selectors target buttons that are NOT disabled. This is more efficient.
BUTTON_1_SELECTOR = 'button.btn.friend.inverted:not(.disabled)'  # Targets the "Add Friend" button
BUTTON_2_SELECTOR = 'button.btn.poke.inverted:not(.disabled)'    # Targets the "Poke" button
LOGIN_URL = 'https://remilia.com/'

# This selector should point to an element that reliably appears when the main
# content of the profile page has loaded. A profile header or container is a good choice.
DYNAMIC_WAIT_SELECTOR = '.profile-header'
FALLBACK_SELECTOR = 'body'  # Fallback if profile-header isn't reliable

# --- SCRIPT SETTINGS ---
INPUT_FILE = 'output_urls.txt'
AUTH_FILE = 'playwright_auth_state.json'    # Stores the secure login session
PROCESSED_FILE = 'processed_urls.txt'       # Tracks already completed URLs to allow resuming
MAX_CONCURRENT_PAGES = 3      # Reduced to 3 to prevent overwhelming the site/system
PAGE_LOAD_TIMEOUT = 30000     # 30 seconds to wait for the page structure to load
ACTION_TIMEOUT = 20000        # 20 seconds for individual actions like clicking
MAX_RETRIES = 2               # Number of times to retry a failed URL

async def click_buttons_on_page(context, url):
    """
    Navigates to a URL, clicks buttons with retries, and reports status.
    This function is optimized for speed and reliability.
    """
    page = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            page = await context.new_page()

            # --- OPTIMIZATION: Block non-essential resources ---
            # This dramatically speeds up page loads by not downloading images, stylesheets, etc.
            await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff2}", lambda route: route.abort())

            # Navigate to the URL. 'domcontentloaded' is faster than 'load'.
            print(f"[ATTEMPT {attempt+1}/{MAX_RETRIES+1}] Navigating to {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=PAGE_LOAD_TIMEOUT)

            # --- OPTIMIZATION: Wait for a key element with fallback ---
            # Try profile-header first, fall back to body if needed
            try:
                await page.wait_for_selector(DYNAMIC_WAIT_SELECTOR, state='visible', timeout=ACTION_TIMEOUT)
                print(f"[DEBUG] Found {DYNAMIC_WAIT_SELECTOR} on {url}")
            except PlaywrightTimeoutError:
                print(f"[DEBUG] {DYNAMIC_WAIT_SELECTOR} not found, trying {FALLBACK_SELECTOR} on {url}")
                await page.wait_for_selector(FALLBACK_SELECTOR, state='visible', timeout=ACTION_TIMEOUT)
                print(f"[DEBUG] Found {FALLBACK_SELECTOR} on {url}")

            status_b1 = "Not Found"
            status_b2 = "Not Found"

            # --- Click Button 1 (Add Friend) ---
            try:
                # The selector already filters for enabled buttons. We just try to click.
                await page.click(BUTTON_1_SELECTOR, timeout=ACTION_TIMEOUT)
                status_b1 = "Clicked"
                print(f"[OK 1]   Clicked 'Add Friend' on {url}")
            except PlaywrightTimeoutError:
                # This happens if the button doesn't exist or is disabled (already friends).
                status_b1 = "Skipped (Not found/disabled)"
                print(f"[SKIP 1] 'Add Friend' button not available on {url}")

            # --- Click Button 2 (Poke) ---
            try:
                await page.click(BUTTON_2_SELECTOR, timeout=ACTION_TIMEOUT)
                status_b2 = "Clicked"
                print(f"[OK 2]   Clicked 'Poke' on {url}")
            except PlaywrightTimeoutError:
                status_b2 = "Skipped (Not found/disabled)"
                print(f"[SKIP 2] 'Poke' button not available on {url}")

            # If we reach here, the process for this URL was successful.
            await page.close()
            return (url, f"Success: Friend={status_b1}, Poke={status_b2}")

        except Exception as e:
            error_message = str(e).split('\n')[0]  # Get a concise error message
            print(f"[ERROR]  Attempt {attempt+1} on {url} failed: {error_message}")
            if page:
                await page.close()
            if attempt < MAX_RETRIES:
                delay = 5 * (attempt + 1)  # Wait longer between retries
                print(f"[RETRY]  Waiting {delay}s before retrying {url}...")
                await asyncio.sleep(delay)
            else:
                print(f"[FAIL]   URL {url} failed after all retries.")
                return (url, f"Failed: {error_message}")

async def main():
    """Main function to set up Playwright, handle logins, and run the tasks."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_FILE)
    auth_path = os.path.join(script_dir, AUTH_FILE)
    processed_path = os.path.join(script_dir, PROCESSED_FILE)

    # --- Resume Logic ---
    processed_urls = set()
    if os.path.exists(processed_path):
        with open(processed_path, 'r', encoding='utf-8') as f:
            processed_urls = set(line.strip() for line in f)

    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        urls_to_process = [line.strip() for line in f if line.strip() and line.strip() not in processed_urls]

    if not urls_to_process:
        print("All URLs have already been processed. Nothing to do.")
        return

    print(f"Found {len(urls_to_process)} new URLs to process.")

    async with async_playwright() as p:
        # --- Secure Login Handling ---
        if not os.path.exists(auth_path):
            print("\n--- One-Time Login Required ---")
            print(f"A browser window will open. Please log in to {LOGIN_URL}.")
            print("After you successfully log in, CLOSE THE BROWSER WINDOW to continue.")
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(LOGIN_URL)
            await page.wait_for_event('close', timeout=0)  # Wait until user closes the window
            await context.storage_state(path=auth_path)
            print("Authentication state saved successfully!")
            await browser.close()

        # --- Main Processing Loop ---
        browser = await p.chromium.launch(headless=True)  # Run headless for speed
        context = await browser.new_context(storage_state=auth_path)
        
        # --- Applying stealth using the class-based approach ---
        await Stealth().apply_stealth_async(context)
        print("Browser context configured with stealth settings.")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)
        results = []
        
        async def run_task(url):
            async with semaphore:
                result = await click_buttons_on_page(context, url)
                results.append(result)
                # Save progress immediately after a URL is processed
                with open(processed_path, 'a', encoding='utf-8') as f:
                    f.write(url + '\n')

        tasks = [run_task(url) for url in urls_to_process]
        await asyncio.gather(*tasks)

        await browser.close()

        # --- Final Summary ---
        print("\n--- Processing Complete ---")
        success_count = sum(1 for _, status in results if status and status.startswith("Success"))
        print(f"Summary: {success_count} / {len(urls_to_process)} URLs processed successfully in this run.")
        print(f"See {PROCESSED_FILE} for a complete list of all attempted URLs.")

if __name__ == "__main__":
    print("--- Optimized & Secure Button Clicker ---")
    print("If this is your first time, you may need to install stealth:")
    print("pip install playwright-stealth\n")
    asyncio.run(main())
