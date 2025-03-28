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

class LinkedInJobScraper:
    def __init__(self):
        # Initialize Chrome options
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

    def scrape_jobs(self, base_url):
        jobs_data = []
        page = 0
        
        while True:
            url = f"{base_url}&start={page * 25}"
            try:
                self.driver.get(url)
                time.sleep(2)
                
                job_listings = self.wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, ".job-card-container")
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
                
                # Save progress after each page
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
            'title', 'company_name', 'location', 'job_type', 
            'posted_time', 'applicants', 'description',
            'apply_url',
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
        self.driver.get("https://www.linkedin.com/login")
        self.wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(email)
        self.wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, "[type=submit]").click()
        time.sleep(3)

    def get_job_description(self, job_card):
        """Extract job description using updated selectors"""
        try:
            # Use safe_click to load job details
            self.safe_click(job_card)
            self.random_delay()
            # Wait for the description container (using the id from sample HTML)
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
        """Modified get_job_details to check for matching jobs, fetch company details, and capture the job apply URL"""
        try:
            self.safe_click(job_card)
            self.random_delay()
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.jobs-search__job-details--container"))
            )
            
            # Get company name and job title first
            company_name = self.safe_get_text("div.job-details-jobs-unified-top-card__company-name a")
            job_title = self.safe_get_text("h1.t-24.t-bold.inline")
            
            # Check for matching jobs based on interested companies/roles
            self.check_job_match(job_title, company_name)
            
            # Get company details
            company_details = self.get_company_details()
            
            # Save company information
            if company_name:
                self.save_company_info(company_name, company_details)
            
            # Collect job details
            details = {
                'title': job_title,
                'company_name': company_name,
            }
            
            # Extract location, posted time, and applicant count
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
            
            # Attempt to capture the job apply URL
            details['apply_url'] = self.get_apply_url()
            
            return details
            
        except TimeoutException as e:
            print(f"Timeout waiting for job details: {str(e)}")
            return {}
        except Exception as e:
            print(f"Error getting job details: {str(e)}")
            return {}

    def get_apply_url(self):
        """Attempts to fetch the URL for the job apply button by clicking it and capturing navigation.
           It uses window handle switching if a new window opens or checks for URL change."""
        apply_url = ""
        try:
            # Locate the apply button using the data-test attribute (which is present on the button in the reference div)
            apply_button = self.driver.find_element(By.CSS_SELECTOR, "*[data-live-test-job-apply-button]")
            # Store the current window handle and URL
            original_handle = self.driver.current_window_handle
            original_url = self.driver.current_url
            original_handles = self.driver.window_handles

            # Click the apply button
            self.safe_click(apply_button)
            time.sleep(3)  # Wait for navigation or new tab

            new_handles = self.driver.window_handles
            if len(new_handles) > len(original_handles):
                # A new window/tab opened; switch to it
                new_handle = [h for h in new_handles if h not in original_handles][0]
                self.driver.switch_to.window(new_handle)
                time.sleep(2)
                apply_url = self.driver.current_url
                # Close the new window and return to original window
                self.driver.close()
                self.driver.switch_to.window(original_handle)
            else:
                # No new window; check if URL has changed
                apply_url = ""
        except Exception as e:
            print(f"Could not get apply URL: {str(e)}")
            apply_url = ""
        return apply_url

    def safe_get_text(self, selector, parent=None):
        """Safely extract text from an element with debugging"""
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
        """Extract job type information (e.g., On-site, Full-time)"""
        try:
            button = self.driver.find_element(By.CSS_SELECTOR, "button.job-details-preferences-and-skills")
            spans = button.find_elements(By.CSS_SELECTOR, "span.ui-label")
            return [span.text.strip() for span in spans if span.text.strip()]
        except Exception:
            return []

    def get_company_details(self):
        """Extract company information using updated selectors from the 'About the company' section"""
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
        """Add a random delay between actions to mimic human behavior"""
        time.sleep(random.uniform(1.5, 3.5))

    def save_company_info(self, company_name, company_details):
        """Save company information to files"""
        try:
            companies = set()
            if os.path.exists('company_list.txt'):
                with open('company_list.txt', 'r', encoding='utf-8') as f:
                    companies = set(line.strip() for line in f)
            
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
        """Sanitize the filename to be valid across operating systems"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()

    def ensure_directory_exists(self):
        """Ensure the necessary directories exist"""
        try:
            if not os.path.exists('companies'):
                os.makedirs('companies')
        except Exception as e:
            print(f"Error creating directories: {str(e)}")

    def load_interested_lists(self):
        """Load interested companies and roles from files"""
        self.interested_companies = set()
        self.interested_roles = set()
        
        # Load interested companies
        try:
            with open('interested_company.txt', 'r', encoding='utf-8') as f:
                self.interested_companies = {line.strip().lower() for line in f if line.strip()}
        except FileNotFoundError:
            with open('interested_company.txt', 'w', encoding='utf-8') as f:
                f.write("Capgemini Engineering\nIBM\nGoogle\n")
            self.interested_companies = {"capgemini engineering", "ibm", "google"}

        # Load interested roles
        try:
            with open('interested_role.txt', 'r', encoding='utf-8') as f:
                self.interested_roles = {line.strip().lower() for line in f if line.strip()}
        except FileNotFoundError:
            with open('interested_role.txt', 'w', encoding='utf-8') as f:
                f.write("Software Engineer\nData Engineer\nAI Engineer\n")
            self.interested_roles = {"software engineer", "data engineer", "ai engineer"}

    def check_job_match(self, job_title, company_name):
        """Check if job matches interested companies and roles"""
        if not job_title or not company_name:
            return False
        
        job_title = job_title.lower()
        company_name = company_name.lower()
        
        company_match = company_name in self.interested_companies
        
        role_words = set(job_title.split())
        role_match = any(
            any(role_word in job_word for job_word in role_words)
            for role_word in self.interested_roles
        )
        
        if company_match and role_match:
            print(f"\nFOUND MATCH!")
            print(f"Company: {company_name}")
            print(f"Role: {job_title}")
            return True
        
        return False

    def load_lists(self):
        """Load all lists (interested companies, roles, and blocked companies)"""
        # Load interested companies and roles (existing code)
        self.load_interested_lists()
        
        # Load blocked companies
        self.blocked_companies = set()
        try:
            with open('block_list.txt', 'r', encoding='utf-8') as f:
                self.blocked_companies = {line.strip().lower() for line in f if line.strip()}
                print(f"Blocked companies: {self.blocked_companies}")
        except FileNotFoundError:
            # Create file if it doesn't exist
            with open('block_list.txt', 'w', encoding='utf-8') as f:
                # Example blocked companies
                f.write("Spam Company\nFake Corp\nScam Industries\n")
            self.blocked_companies = {"spam company", "fake corp", "scam industries"}

    def is_company_blocked(self, company_name):
        """Check if company is in block list"""
        if not company_name:
            return False
        
        company_name = company_name.lower()
        
        # Check exact match
        if company_name in self.blocked_companies:
            print(f"\nSkipping blocked company: {company_name}")
            return True
        
        # Check partial matches (optional)
        for blocked in self.blocked_companies:
            if blocked in company_name or company_name in blocked:
                print(f"\nSkipping blocked company (partial match): {company_name}")
                return True
                
        return False

    def add_to_block_list(self, company_name):
        """Add a company to the block list"""
        if not company_name:
            return
        
        company_name = company_name.strip()
        
        # Add to memory set
        self.blocked_companies.add(company_name.lower())
        
        # Add to file
        with open('block_list.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n{company_name}")
        
        print(f"Added {company_name} to block list")

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
        time.sleep(5)
        
        print("Starting to scrape jobs...")
        jobs = scraper.scrape_jobs(base_url)
        print(f"Total jobs scraped: {len(jobs)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()