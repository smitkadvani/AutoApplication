import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Constants
MICROSOFT_CAREERS_URL = "https://jobs.careers.microsoft.com/global/en/search?q=software%20developer&lc=United%20States&d=Software%20Engineering&et=Full-Time&l=en_us&pg=1&pgSz=20&o=Relevance&flt=true"
OLD_JOBS_FILE = "old_jobs.json"
CHECK_INTERVAL = 30  # Time interval in seconds

def setup_driver():
    """Initialize and return a Selenium WebDriver instance."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Runs browser in background
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
    """Parses job listings from the saved HTML file."""
    with open("debug_page_source.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "html.parser")
    job_elements = soup.find_all("div", class_="ms-List-cell")

    jobs = []
    for job in job_elements:
        title_element = job.find("h2", class_="MZGzlrn8gfgSs8TZHhv2")
        location_element = job.find("span", string=lambda text: "United States" in text if text else False)
        date_element = job.find("span", string=lambda text: "day" in text or "Today" in text if text else False)
        link_element = job.find("button", class_="seeDetailsLink-544")

        if title_element:
            title = title_element.text.strip()
            location = location_element.text.strip() if location_element else "N/A"
            posted_date = date_element.text.strip() if date_element else "N/A"
            url = MICROSOFT_CAREERS_URL  

            jobs.append({
                "title": title,
                "url": url,
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

def check_for_new_jobs():
    """Main function to check for new job postings in a loop."""
    while True:
        print("\nChecking for new job postings...")
        fetch_and_save_html()
        current_jobs = parse_jobs_from_html()

        if not current_jobs:
            print("No job postings found.")
        else:
            old_jobs = load_previous_jobs()
            new_jobs = find_new_jobs(old_jobs, current_jobs)

            if new_jobs:
                print("\n🚀 New job postings found!")
                for job in new_jobs:
                    print(f"🔹 Title: {job['title']}")
                    print(f"📍 Location: {job['location']}")
                    print(f"🗓 Posted: {job['posted_date']}")
                    print(f"🔗 URL: {job['url']}")
                    print("-" * 40)
                save_jobs(current_jobs)
            else:
                print("✅ No new jobs since last check.")ls -l