# This script uses Playwright to concurrently open web pages from a file
# and click two specific buttons on each page. It's designed for speed
# and includes a secure method for handling logins.

import asyncio
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth  # Use Stealth class for anti-detection

# --- IMPORTANT: USER CONFIGURATION ---
# Verify these selectors manually on a logged-in page (e.g., https://remilia.com/~david)
BUTTON_1_SELECTOR = 'button.btn.friend.inverted:not(.disabled)'  # Targets the "Add Friend" button
BUTTON_2_SELECTOR = 'button.btn.poke.inverted:not(.disabled)'   # Targets the "Poke" button
# Note: If "Poke" button has 'bin' instead of 'btn', change to 'button.bin.poke.inverted:not(.disabled)'
DYNAMIC_WAIT_SELECTOR = 'body, .profile-header'                 # Adjust to a visible element (e.g., .profile-header or .user-actions)

# The base URL of the site you need to log into.
LOGIN_URL = 'https://remilia.com/' 

# --- SCRIPT SETTINGS ---
INPUT_FILE = 'output_urls.txt'
AUTH_FILE = 'playwright_auth_state.json' # File to store the secure login session
MAX_CONCURRENT_PAGES = 15  # Set to 15; reduce to 10 if system lags
PAGE_LOAD_TIMEOUT = 60000  # 60s
BUTTON_CLICK_TIMEOUT = 30000  # 30s
DYNAMIC_WAIT_TIMEOUT = 120000  # Increased to 120s (2 minutes) for dynamic content

async def click_buttons_on_page(semaphore, context, url):
    """Navigates to a URL within a logged-in context, attempts to click buttons, and handles errors."""
    async with semaphore:
        page = None
        try:
            page = await context.new_page()
            # No per-page stealth needed; applied to context
            print(f"[START]  Processing {url}")
            await page.goto(url, wait_until='load', timeout=PAGE_LOAD_TIMEOUT)

            # Wait for dynamic content to fully render
            await page.wait_for_load_state('domcontentloaded', timeout=PAGE_LOAD_TIMEOUT)
            await page.wait_for_load_state('networkidle', timeout=DYNAMIC_WAIT_TIMEOUT)  # Wait for network to settle
            await page.wait_for_selector(DYNAMIC_WAIT_SELECTOR, timeout=DYNAMIC_WAIT_TIMEOUT, state='attached')
            print(f"[READY]  Page content loaded for {url}")

            # Check and attempt to click Button 1
            print(f"[CHECK 1] Checking for button 1 on {url}")
            button1_exists = await page.query_selector(BUTTON_1_SELECTOR) is not None
            print(f"[CHECK 1] Button 1 found: {button1_exists}")
            if button1_exists:
                print(f"[WAIT 1] Waiting for button 1 on {url}")
                await page.wait_for_selector(BUTTON_1_SELECTOR, timeout=BUTTON_CLICK_TIMEOUT)
                print(f"[CLICK 1] Attempting to click button 1 on {url}")
                try:
                    await page.click(BUTTON_1_SELECTOR, timeout=BUTTON_CLICK_TIMEOUT)
                    print(f"[OK 1]   Successfully clicked button 1 on {url}")
                except Exception as click_err:
                    print(f"[FAIL 1] Failed to click button 1 on {url}: {click_err}")
            else:
                print(f"[SKIP 1] Button 1 not found on {url}")

            # Check and attempt to click Button 2
            print(f"[CHECK 2] Checking for button 2 on {url}")
            button2_exists = await page.query_selector(BUTTON_2_SELECTOR) is not None
            print(f"[CHECK 2] Button 2 found: {button2_exists}")
            if button2_exists:
                print(f"[WAIT 2] Waiting for button 2 on {url}")
                await page.wait_for_selector(BUTTON_2_SELECTOR, timeout=BUTTON_CLICK_TIMEOUT)
                print(f"[CLICK 2] Attempting to click button 2 on {url}")
                try:
                    await page.click(BUTTON_2_SELECTOR, timeout=BUTTON_CLICK_TIMEOUT)
                    print(f"[OK 2]   Successfully clicked button 2 on {url}")
                except Exception as click_err:
                    print(f"[FAIL 2] Failed to click button 2 on {url}: {click_err}")
            else:
                print(f"[SKIP 2] Button 2 not found on {url}")

            return (url, "Success" if "[OK 2]" in [x for x in locals().values() if isinstance(x, str)] else "Partial/Failed" if "[OK 1]" in [x for x in locals().values() if isinstance(x, str)] else "Failed")

        except PlaywrightTimeoutError:
            error_message = f"Timeout Error: Could not find elements or page took too long to load on {url}"
            print(f"[ERROR]  {error_message}")
            if page:
                content = await page.content()  # Log page content for debugging
                print(f"[DEBUG CONTENT] {content[:500]}...")
            return (url, error_message)
        except Exception as e:
            error_message = f"An unexpected error occurred on {url}: {e}"
            print(f"[ERROR]  {error_message}")
            return (url, str(e))
        finally:
            if page:
                await page.close()


async def main():
    """Reads URLs and processes them in parallel after ensuring the user is logged in."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_FILE)
    auth_path = os.path.join(script_dir, AUTH_FILE)

    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        return

    async with async_playwright() as p:
        browser = None
        context = None

        if not os.path.exists(auth_path):
            # --- ONE-TIME LOGIN PROCESS ---
            print("\n--- Login Required ---")
            print("Authentication file not found. A browser window will open.")
            print(f"Please log in to {LOGIN_URL} manually.")
            print("After you have successfully logged in, CLOSE THE BROWSER WINDOW to continue.")
            
            browser = await p.chromium.launch(headless=False)  # Non-headless for interactive login
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(LOGIN_URL)
            
            # Wait for manual close after login
            input("Press Enter after closing the browser window...")  # Better than wait_for_event for reliability
            
            # Save the authentication state to the file.
            await context.storage_state(path=auth_path)
            print("Authentication state saved successfully!")
            await browser.close()
            browser = None  # Reset for next launch
        
        # --- RUN THE MAIN TASK ---
        with open(input_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            print("Input file is empty. Nothing to process.")
            return
            
        print(f"\nFound {len(urls)} URLs. Starting processing...")
        
        # Launch a new browser with the saved authentication state
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=auth_path)
        
        # Apply stealth to the context (once, for all pages)
        stealth = Stealth()
        await stealth.apply_stealth_async(context)
        print("[STEALTH] Applied stealth evasions to browser context.")
        
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)  # Limit concurrency
        tasks = [click_buttons_on_page(semaphore, context, url) for url in urls]
        try:
            results = await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("[INFO] Script interrupted by user. Closing gracefully...")
            await browser.close()
            return
        
        await browser.close()

        print("\n--- Processing Complete ---")
        success_count = 0
        for url, status in results:
            if status == "Success":
                success_count += 1
            print(f"- {url}: {status}")
        print(f"\nSummary: {success_count} / {len(urls)} URLs processed successfully.")


if __name__ == "__main__":
    print("--- Secure Web Page Button Clicker ---")
    asyncio.run(main())