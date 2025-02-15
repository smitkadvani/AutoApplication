import time
import json
import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Set your Telegram bot token and chat ID
TELEGRAM_BOT_TOKEN = "7547959272:AAEiClyALIZ_lMj9SPONdSxUZcQU_DRNllE"
TELEGRAM_CHAT_ID = "2102830578"  # Replace with your actual Telegram chat ID

MICROSOFT_CAREERS_URL = "https://jobs.careers.microsoft.com/global/en/search?q=software%20developer&lc=United%20States&d=Software%20Engineering&et=Full-Time&l=en_us&pg=1&pgSz=20&o=Recent&flt=true"
OLD_JOBS_FILE = "old_jobs.json"
CHECK_INTERVAL = 30  # Time interval in seconds

def setup_driver():
    """Initialize and return a Selenium WebDriver instance."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920x1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def fetch_and_save_html():
    """Fetch job listings and save HTML source."""
    driver = setup_driver()
    
    try:
        driver.get(MICROSOFT_CAREERS_URL)
        time.sleep(5)  # Wait for page load

        # Scroll dynamically to load all job postings
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Save page source
        with open("debug_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        driver.quit()

def parse_jobs_from_html():
    """Parses job listings from the saved HTML file and extracts job IDs."""
    with open("debug_page_source.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "html.parser")
    job_elements = soup.find_all("div", class_="ms-List-cell")

    jobs = []
    for job in job_elements:
        title_element = job.find("h2", class_="MZGzlrn8gfgSs8TZHhv2")
        location_element = job.find("span", string=lambda text: "United States" in text if text else False)
        date_element = job.find("span", string=lambda text: "day" in text or "Today" in text if text else False)

        # Extract job ID from the 'aria-label' attribute of the <div> tag
        job_div = job.find("div", {"aria-label": lambda x: x and x.startswith("Job item")})
        if job_div:
            job_id = job_div["aria-label"].split()[-1]  # Extract job ID
            job_url = f"https://jobs.careers.microsoft.com/global/en/job/{job_id}"  # Construct full job URL
            if title_element:
                title = title_element.text.strip()
                location = location_element.text.strip() if location_element else "N/A"
                posted_date = date_element.text.strip() if date_element else "N/A"

                jobs.append({
                    "title": title,
                    "url": job_url,
                    "location": location,
                    "posted_date": posted_date
                })

    return jobs

def load_previous_jobs():
    """Loads previously stored job listings from a JSON file."""
    if os.path.exists(OLD_JOBS_FILE):
        with open(OLD_JOBS_FILE, 'r') as file:
            return json.load(file)
    return []

def save_jobs(jobs):
    """Saves the current job listings to a JSON file."""
    with open(OLD_JOBS_FILE, 'w') as file:
        json.dump(jobs, file, indent=4)

def find_new_jobs(old_jobs, current_jobs):
    """Identifies new jobs that were not in the previous listings."""
    old_job_titles = {job['title'] for job in old_jobs}
    new_jobs = [job for job in current_jobs if job['title'] not in old_job_titles]
    return new_jobs

def send_telegram_message(new_jobs):
    """Sends a notification to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠ Telegram bot token or chat ID missing!")
        return

    for job in new_jobs:
        message = f"🚀 *New Microsoft Job Posted!*\n🔹 *Title:* {job['title']}\n📍 *Location:* {job['location']}\n🗓 *Posted:* {job['posted_date']}\n🔗 [View Job]({job['url']})"
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            print(f"📢 Sent Telegram notification for: {job['title']}")
        else:
            print(f"⚠ Failed to send Telegram message: {response.text}")

def check_for_new_jobs():
    """Main function to check for new job postings in a loop."""
    while True:
        print("\n🔍 Checking for new job postings...")
        fetch_and_save_html()
        current_jobs = parse_jobs_from_html()

        old_jobs = load_previous_jobs()
        new_jobs = find_new_jobs(old_jobs, current_jobs)

        if new_jobs:
            send_telegram_message(new_jobs)
            save_jobs(current_jobs)

        print(f"⏳ Waiting {CHECK_INTERVAL} seconds before next check...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    check_for_new_jobs()