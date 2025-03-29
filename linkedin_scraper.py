import json
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import time
import csv
import os
from dotenv import load_dotenv
import random
import re
from telegram_sender import TelegramBot, format_job_message

# Telegram credentials
TELEGRAM_BOT_TOKEN = "7547959272:AAEiClyALIZ_lMj9SPONdSxUZcQU_DRNllE"
TELEGRAM_CHAT_ID = ["2102830578", "1678159044"]

class LinkedInJobScraper:
    def __init__(self):
        # Initialize Chrome options with persistent profile settings
        self.options = webdriver.ChromeOptions()
        self.options.add_argument('--disable-notifications')
        self.options.add_argument('--start-maximized')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        
        # Additional preferences
        self.options.add_experimental_option('prefs', {
            'profile.default_content_setting_values.notifications': 2,
            'profile.managed_default_content_settings.images': 1,
            'profile.managed_default_content_settings.javascript': 1
        })
        
        self.driver = webdriver.Chrome(options=self.options)
        self.wait = WebDriverWait(self.driver, 10)
        
        # Ensure company list file exists
        if not os.path.exists('company_list.txt'):
            with open('company_list.txt', 'w', encoding='utf-8') as f:
                pass
        
        # Ensure companies directory exists
        self.ensure_directory_exists()

        # Initialize all lists including block list
        self.load_lists()
        
        # Load previously notified job IDs (if any)
        self.load_notified_job_ids()

        # Initialize Telegram bot
        self.telegram_bot = TelegramBot("your_bot_token_here")

    def load_notified_job_ids(self):
        """Load job IDs from file so that we don't resend notifications for the same jobs."""
        self.notified_job_ids = set()
        if os.path.exists("notified_jobs.txt"):
            with open("notified_jobs.txt", "r", encoding="utf-8") as f:
                self.notified_job_ids = {line.strip() for line in f if line.strip()}
        print(f"Loaded {len(self.notified_job_ids)} notified job IDs.")

    def save_notified_job_id(self, job_id):
        """Append a new job ID to the persistent storage."""
        with open("notified_jobs.txt", "a", encoding="utf-8") as f:
            f.write(job_id + "\n")
        self.notified_job_ids.add(job_id)

    def safe_click(self, element):
        """Attempt to click an element safely using standard click, fallback to JS click."""
        try:
            element.click()
        except ElementClickInterceptedException as e:
            print(f"Click intercepted: {str(e)}. Trying JS click.")
            self.driver.execute_script("arguments[0].click();", element)
        except Exception as e:
            print(f"Error clicking element: {str(e)}. Trying JS click.")
            self.driver.execute_script("arguments[0].click();", element)

    def close_sign_in_modal(self):
        """Attempt to close the sign-in modal if it appears."""
        try:
            modal_button = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.modal__dismiss"))
            )
            modal_button.click()
            print("Closed sign-in modal.")
            time.sleep(1)
        except Exception:
            # Modal did not appear; nothing to close.
            pass

    def scrape_jobs(self, base_url):
        jobs_data = []
        page = 0
        
        while True:
            url = f"{base_url}&start={page * 25}"
            try:
                self.driver.get(url)
                time.sleep(2)
                
                # Close sign-in modal if it appears
                self.close_sign_in_modal()
                
                job_listings = self.wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, ".job-card-container, .base-search-card")
                ))
                
                if not job_listings:
                    break
                
                for job in job_listings:
                    try:
                        job_details = self.get_job_details(job)
                        if job_details:
                            jobs_data.append(job_details)
                            print(f"Scraped job: {job_details.get('title', 'Unknown Title')}")
                    except Exception as e:
                        print(f"Error processing job: {str(e)}")
                        continue
                
                print(f"Scraped page {page + 1}")
                page += 1
                
                # Optionally save progress after each page
                self.save_to_csv(jobs_data)
                
            except TimeoutException:
                print(f"Timeout on page {page + 1}")
                break
            except Exception as e:
                print(f"Error on page {page + 1}: {str(e)}")
                break
        
        return jobs_data

    def save_to_csv(self, jobs_data):
        fieldnames = [
            'job_id', 'title', 'company_name', 'location', 'job_type', 
            'posted_time', 'applicants', 'description', 'apply_url',
            'company_size', 'company_industry', 'company_description'
        ]
        
        with open('linkedin_jobs.csv', 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for job in jobs_data:
                job_row = {
                    **job,
                    'company_size': job.get('company_details', {}).get('size', ''),
                    'company_industry': job.get('company_details', {}).get('industry', ''),
                    'company_description': job.get('company_details', {}).get('description', '')
                }
                job_row.pop('company_details', None)
                writer.writerow(job_row)

    def close(self):
        self.driver.quit()

    def login(self, email, password):
        """Perform login; this script expects that login is needed."""
        self.driver.get("https://www.linkedin.com/login")
        self.wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(email)
        self.wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, "[type=submit]").click()
        time.sleep(20)  # Adjust delay as needed after login
        print("Logged in successfully.")

    def get_job_description(self, job_card):
        """Extract job description using updated selectors."""
        try:
            self.safe_click(job_card)
            self.random_delay()
            description_container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div#job-details"))
            )
            return description_container.text.strip()
        except TimeoutException as e:
            print(f"Timeout waiting for job description: {str(e)}")
            return ""
        except Exception as e:
            print(f"Error getting job description: {str(e)}")
            return ""

    def get_job_details(self, job_card):
        """
        Extract job details including a unique job ID.
        This version first checks for 'data-occludable-job-id', then 'data-job-id',
        and finally falls back to 'data-entity-urn' if necessary.
        """
        try:
            job_id = job_card.get_attribute("data-occludable-job-id")
            if not job_id:
                job_id = job_card.get_attribute("data-job-id")
            if not job_id:
                job_id = job_card.get_attribute("data-entity-urn")
                if job_id:
                    job_id = job_id.split("jobPosting:")[-1]
            if not job_id:
                job_id = "unknown"
                
            print(f"Job ID: {job_id}")

            # Skip if this job was already notified
            if job_id in self.notified_job_ids:
                print(f"Job ID {job_id} already notified; skipping notification.")
                return None

            self.safe_click(job_card)
            self.random_delay()
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.jobs-search__job-details--container"))
            )
            
            company_name = self.safe_get_text("div.job-details-jobs-unified-top-card__company-name a")
            job_title = self.safe_get_text("h1.t-24.t-bold.inline")
            
            # Get company details and save company info
            company_details = self.get_company_details()
            if company_name:
                self.save_company_info(company_name, company_details)
            
            details = {
                'job_id': job_id,
                'title': job_title,
                'company_name': company_name,
            }
            
            desc_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "div.job-details-jobs-unified-top-card__tertiary-description-container span"
            )
            desc_texts = [elem.text.strip() for elem in desc_elements if elem.text.strip() and elem.text.strip() != "·"]
            
            if len(desc_texts) >= 2:
                details['location'] = desc_texts[0]
                details['posted_time'] = desc_texts[1]
            else:
                details['location'] = ""
                details['posted_time'] = ""
            
            details['applicants'] = desc_texts[2] if len(desc_texts) >= 3 else ""
            details['job_type'] = self.get_job_type()
            self.random_delay()
            details['description'] = self.get_job_description(job_card)
            details['company_details'] = company_details
            details['apply_url'] = self.get_apply_url()
            
            # Send notification if job matches criteria
            if self.check_job_match(details['title'], details['company_name']):
                self.send_telegram_message(details)
            
            return details
            
        except TimeoutException as e:
            print(f"Timeout waiting for job details: {str(e)}")
            return None
        except Exception as e:
            print(f"Error getting job details: {str(e)}")
            return None

    def get_apply_url(self):
        """Extract the apply URL from the job posting"""
        try:
            # First try to get the current job URL (for LinkedIn internal jobs)
            current_url = self.driver.current_url
            
            # Try to find the apply button
            apply_button = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    "button.jobs-apply-button"
                ))
            )
            
            # If it's an external URL, get it from the button
            if apply_button.get_attribute('data-job-url'):
                return apply_button.get_attribute('data-job-url')
            
            # If no external URL, return the LinkedIn job URL
            if 'jobs/view' in current_url:
                return current_url
            
            return None
            
        except Exception as e:
            print(f"Error getting apply URL: {str(e)}")
            # If we can't get the apply URL, return the current job URL if it's a job page
            if 'jobs/view' in self.driver.current_url:
                return self.driver.current_url
            return None

    def safe_get_text(self, selector, parent=None):
        try:
            element = (parent if parent else self.driver).find_element(By.CSS_SELECTOR, selector)
            text = element.text.strip()
            if not text:
                print(f"Warning: Empty text for selector '{selector}'")
            return text
        except NoSuchElementException:
            print(f"Warning: No element found for selector '{selector}'")
            return ""
        except Exception as e:
            print(f"Error getting text for selector '{selector}': {str(e)}")
            return ""

    def get_job_type(self):
        try:
            button = self.driver.find_element(By.CSS_SELECTOR, "button.job-details-preferences-and-skills")
            spans = button.find_elements(By.CSS_SELECTOR, "span.ui-label")
            return [span.text.strip() for span in spans if span.text.strip()]
        except Exception:
            return []

    def get_company_details(self):
        try:
            company_section = self.driver.find_element(By.CSS_SELECTOR, "section.jobs-company")
            info_div = company_section.find_element(By.CSS_SELECTOR, "div.t-14.mt5")
            industry_text = info_div.text.strip()
            
            inline_infos = company_section.find_elements(By.CSS_SELECTOR, "span.jobs-company__inline-information")
            company_size = inline_infos[0].text.strip() if len(inline_infos) > 0 else ""
            company_description = self.safe_get_text("p.jobs-company__company-description")
            
            return {
                'industry': industry_text,
                'size': company_size,
                'description': company_description
            }
        except Exception:
            return {}

    def random_delay(self):
        time.sleep(random.uniform(1.5, 3.5))

    def send_telegram_message(self, job):
        """Send a Telegram notification for a matching job if it hasn't been notified before."""
        job_id = job.get("job_id", "unknown")
        if job_id in self.notified_job_ids:
            print(f"Job ID {job_id} already notified. Skipping message.")
            return

        message = (
            f"🚀 *New Job Matched!*\n"
            f"🔹 *Title:* {job['title']}\n"
            f"📍 *Location:* {job['location']}\n"
            f"🗓 *Posted:* {job['posted_time']}\n"
            f"🔗 [Apply Here]({job['apply_url']})"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        for chat_id in TELEGRAM_CHAT_ID:
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                print(f"📢 Sent Telegram notification for: {job['title']}")
                self.save_notified_job_id(job_id)
            else:
                print(f"⚠ Failed to send Telegram message: {response.text}")

    def save_company_info(self, company_name, company_details):
        try:
            companies = set()
            if os.path.exists('company_list.txt'):
                with open('company_list.txt', 'r', encoding='utf-8') as f:
                    companies = {line.strip() for line in f}
            if company_name and company_name not in companies:
                with open('company_list.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{company_name}\n")
                sanitized_name = self.sanitize_filename(company_name)
                details_filename = os.path.join("companies", f"{sanitized_name}_details.txt")
                with open(details_filename, 'w', encoding='utf-8') as f:
                    f.write(f"Company Name: {company_name}\n")
                    f.write(f"Industry: {company_details.get('industry', 'N/A')}\n")
                    f.write(f"Size: {company_details.get('size', 'N/A')}\n")
                    f.write(f"Description: {company_details.get('description', 'N/A')}\n")
                    size_text = company_details.get('size', '')
                    if size_text:
                        if '-' in size_text:
                            f.write(f"Employee Range: {size_text}\n")
                        else:
                            numbers = re.findall(r'\d+,?\d*', size_text)
                            if numbers:
                                f.write(f"Total Employees: {numbers[0]}\n")
                print(f"Saved details for new company: {company_name}")
        except Exception as e:
            print(f"Error saving company info for {company_name}: {str(e)}")

    def sanitize_filename(self, filename):
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()

    def ensure_directory_exists(self):
        try:
            if not os.path.exists('companies'):
                os.makedirs('companies')
        except Exception as e:
            print(f"Error creating directories: {str(e)}")

    def load_interested_lists(self):
        self.interested_companies = set()
        self.interested_roles = set()
        try:
            with open('interested_company.txt', 'r', encoding='utf-8') as f:
                self.interested_companies = {line.strip().lower() for line in f if line.strip()}
        except FileNotFoundError:
            with open('interested_company.txt', 'w', encoding='utf-8') as f:
                f.write("Capgemini Engineering\nIBM\nGoogle\n")
            self.interested_companies = {"capgemini engineering", "ibm", "google"}
        try:
            with open('interested_role.txt', 'r', encoding='utf-8') as f:
                self.interested_roles = {line.strip().lower() for line in f if line.strip()}
        except FileNotFoundError:
            with open('interested_role.txt', 'w', encoding='utf-8') as f:
                f.write("Software Engineer\nData Engineer\nAI Engineer\n")
            self.interested_roles = {"software engineer", "data engineer", "ai engineer"}

    def load_lists(self):
        self.load_interested_lists()
        self.blocked_companies = set()
        try:
            with open('block_list.txt', 'r', encoding='utf-8') as f:
                self.blocked_companies = {line.strip().lower() for line in f if line.strip()}
                print(f"Blocked companies: {self.blocked_companies}")
        except FileNotFoundError:
            with open('block_list.txt', 'w', encoding='utf-8') as f:
                f.write("Spam Company\nFake Corp\nScam Industries\n")
            self.blocked_companies = {"spam company", "fake corp", "scam industries"}

    def is_company_blocked(self, company_name):
        if not company_name:
            return False
        company_name = company_name.lower()
        if company_name in self.blocked_companies:
            print(f"\nSkipping blocked company: {company_name}")
            return True
        for blocked in self.blocked_companies:
            if blocked in company_name or company_name in blocked:
                print(f"\nSkipping blocked company (partial match): {company_name}")
                return True
        return False

    def add_to_block_list(self, company_name):
        if not company_name:
            return
        company_name = company_name.strip()
        self.blocked_companies.add(company_name.lower())
        with open('block_list.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n{company_name}")
        print(f"Added {company_name} to block list")

    def check_job_match(self, job_title, company_name):
        """Check if job matches and send notification if it does"""
        if not job_title or not company_name:
            return False
        
        # Convert to lowercase for comparison
        job_title = job_title.lower()
        company_name = company_name.lower()
        
        # Check if company matches
        company_match = company_name in self.interested_companies
        
        # Check if any role word matches
        role_words = set(job_title.split())
        role_match = any(
            any(role_word in job_word for job_word in role_words)
            for role_word in self.interested_roles
        )
        
        if company_match and role_match:
            # Get apply URL when there's a match
            apply_url = self.get_apply_url()
            
            # Prepare job details
            job_details = {
                'company_name': company_name,
                'title': job_title,
                'apply_url': apply_url or 'Not available'
            }
            
            # Format and send message
            message = format_job_message(job_details)
            self.telegram_bot.broadcast_message(message)
            
            print("\nFOUND MATCH!")
            print(f"Company: {company_name}")
            print(f"Role: {job_title}")
            if apply_url:
                print(f"Apply URL: {apply_url}")
            else:
                print("Apply URL not found")
            print("-" * 50)
            return True
        
        return False

def main():
    load_dotenv()
    base_url = (
        "https://www.linkedin.com/jobs/search/?currentJobId=4174920866"
        "&f_E=4&f_EA=true&f_JT=F&f_T=39%2C25206%2C30128&f_TPR=r3600"
        "&keywords=software%20engineer"
        "&origin=JOB_SEARCH_PAGE_JOB_FILTER&sortBy=R"
    )
    email = os.getenv('LINKEDIN_EMAIL')
    password = os.getenv('LINKEDIN_PASSWORD')
    if not email or not password:
        raise ValueError("LinkedIn credentials not found in environment variables")
    
    scraper = LinkedInJobScraper()
    try:
        print("Logging in to LinkedIn...")
        scraper.login(email, password)
        # Run the scraping process every 15 minutes
        while True:
            print("Starting job scraping cycle...")
            jobs = scraper.scrape_jobs(base_url)
            print(f"Total jobs scraped in this cycle: {len(jobs) if jobs else 0}")
            print("Waiting for 15 minutes before next cycle...")
            time.sleep(15 * 60)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()