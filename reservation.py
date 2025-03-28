from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import time
import random
from faker import Faker

# Initialize Faker for generating random names and emails
fake = Faker()

# Configure Chrome to run in headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920x1080")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Initialize WebDriver
driver = webdriver.Chrome(options=chrome_options)

# Open the website
driver.get("https://amitabulvegan.com/menu/")
time.sleep(3)  # Wait for the page to load

# Loop to make 100 reservations
for i in range(100):
    try:
        # Click on the Reservation button
        reservation_button = driver.find_element(By.XPATH, "//a[.//span[text()='Reservation']]")
        reservation_button.click()
        time.sleep(2)  # Wait for the form to load

        # Generate random data
        name = fake.name()
        email = fake.ascii_free_email()
        phone = fake.random_int(min=1000000000, max=9999999999)  # 10-digit number
        date = "02/{:02d}/2025".format(random.randint(10, 28))  # Random day in Feb
        time_slot = f"{random.randint(5, 10)}:{random.choice(['00', '30'])} PM"  # Between 5:00 PM and 10:30 PM
        seats = str(random.randint(1, 10))  # Random seat selection

        # Fill in the form
        driver.find_element(By.ID, "your_name").send_keys(name)
        driver.find_element(By.ID, "email").send_keys(email)
        driver.find_element(By.ID, "phone").send_keys(str(phone))
        driver.find_element(By.ID, "date").clear()
        driver.find_element(By.ID, "date").send_keys(date)
        driver.find_element(By.ID, "time").send_keys(time_slot)

        # Select number of seats
        seats_dropdown = Select(driver.find_element(By.ID, "seats"))
        seats_dropdown.select_by_value(seats)

        # Special request
        driver.find_element(By.ID, "message").send_keys("Please provide a window seat.")

        # Submit the form
        submit_button = driver.find_element(By.ID, "reservation_submit_btn")
        submit_button.click()

        # Print success message
        print(f"Reservation {i+1}: {name}, {email}, {phone}, {date}, {time_slot}, {seats} seats")

        # Wait for confirmation and navigate back
        time.sleep(3)
        driver.get("https://amitabulvegan.com/menu/")
        time.sleep(2)

    except Exception as e:
        print(f"Error on reservation {i+1}: {e}")

# Close the browser
driver.quit()

print("Completed 100 reservations successfully!")