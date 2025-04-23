import os
import re
import time
from selenium.common.exceptions import WebDriverException

# Import WebDriver initialization function from utils
try:
    from utils import initialize_driver
except ImportError:
    print("Error: Could not import initialize_driver from utils.py.")
    print("Ensure utils.py exists and is correctly configured.")
    exit(1)

# --- Configuration ---
TARGET_URLS = [
    "https://race.netkeiba.com/race/result.html?race_id=202506030811&rf=race_list",
    "https://db.netkeiba.com/horse/2022105081",
    "https://db.netkeiba.com/jockey/result/recent/05509/",
    "https://db.netkeiba.com/trainer/result/recent/01159/",
    "https://db.netkeiba.com/horse/result/2022105081/",
    "https://race.netkeiba.com/odds/index.html?race_id=202506030811" # Added live odds URL
]
OUTPUT_DIR = "html_samples"
WAIT_TIME = 5 # Seconds to wait for page load

# --- Helper Function ---
def generate_filename_from_url(url):
    """Generates a safe filename from a URL."""
    # Remove protocol
    name = re.sub(r'^https?://', '', url)
    # Replace common separators and invalid characters with underscores
    name = re.sub(r'[/:?=&%]', '_', name)
    # Remove potentially problematic trailing characters or multiple underscores
    name = re.sub(r'_+', '_', name).strip('_')
    # Limit length if necessary (optional)
    # max_len = 100
    # name = name[:max_len]
    return f"{name}.html"

# --- Main Execution ---
if __name__ == "__main__":
    print(f"Creating output directory: {OUTPUT_DIR}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    driver = None
    try:
        print("Initializing WebDriver...")
        driver = initialize_driver()
        print("WebDriver initialized.")

        # Ensure driver is not None before proceeding
        if driver:
            for url in TARGET_URLS:
                filename = generate_filename_from_url(url)
                filepath = os.path.join(OUTPUT_DIR, filename)

                # Indent the following block to be inside the loop
                print(f"\nFetching URL: {url}")
                try:
                    driver.get(url)
                    print(f"Waiting {WAIT_TIME} seconds for page to load...")
                    time.sleep(WAIT_TIME) # Move sleep inside try

                    print("Getting page source...")
                    html_content = driver.page_source # Move page_source inside try

                    print(f"Saving HTML to: {filepath}")
                    with open(filepath, "w", encoding="utf-8") as f: # Move file writing inside try
                        f.write(html_content)
                    print("Saved successfully.")

                # Correctly indented except blocks
                except WebDriverException as e:
                        print(f"Error accessing URL {url}: {e}")
                except IOError as e:
                        print(f"Error writing file {filepath}: {e}")
                except Exception as e:
                     print(f"An unexpected error occurred for URL {url}: {e}")
        else:
            print("WebDriver initialization failed. Cannot fetch URLs.")

    except Exception as e:
        print(f"An error occurred during WebDriver initialization or processing: {e}")
    finally:
        if driver:
            print("\nQuitting WebDriver...")
            driver.quit()
            print("WebDriver quit.")

    print("\nHTML sample saving process finished.")
