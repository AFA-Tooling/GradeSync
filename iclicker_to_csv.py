import os
import glob
from dotenv import load_dotenv 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd

load_dotenv()

ICLICKER_USERNAME = os.getenv("ICLICKER_USERNAME")
ICLICKER_PASSWORD = os.getenv("ICLICKER_PASSWORD")

def main():
    # specify download directory (ensure this folder exists)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    download_dir = os.path.join(base_dir, "iclicker_csv_exports")
    
    # create chromeoptions and set download preferences
    chrome_options = Options()
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # create selenium driver to bypass login credentials
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    # navigate to iclicker login page
    driver.get('https://instructor.iclicker.com/#/onboard/login')
    try:
        # click campus portal login
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in through your campus portal")))
        driver.find_element(By.LINK_TEXT, "Sign in through your campus portal").click()
        # choose berkeley from university list dropdown
        WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, "institute")))
        select_institution = Select(driver.find_element(By.ID, "institute"))
        select_institution.select_by_visible_text("University of California Berkeley")
        # click let's go button
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-primary")))
        driver.find_element(By.CSS_SELECTOR, ".btn-primary").click()
        # send calnet username
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'username')))
        driver.find_element(By.ID, 'username').send_keys(ICLICKER_USERNAME)
        # send calnet password
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'password')))
        driver.find_element(By.ID, 'password').send_keys(ICLICKER_PASSWORD)
        # click sign in button
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.NAME, 'submit')))
        driver.find_element(By.NAME, 'submit').click()
        # wait for manual duo authentication
        print("Please complete the Duo Push authentication now.")
        # click cs10 dummy
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[title='CS10 Dummy']"))).click()
        # click attendance
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//span[@class='course-link-title' and contains(text(), 'Attendance')]"))).click()
        #click bypass bottom 
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Export')]"))).click()

        # select all files to export
        time.sleep(2)
        checkbox = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "check-box-header")))
        checkbox.click()
        print("Select all button clicked successfully!")

        # click export button
        time.sleep(2)
        modal_export_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[@type='submit' and contains(text(), 'Export')]")
            )
        )
        modal_export_button.click()
        
        time.sleep(10)

    except Exception as e:
        print(f"An error occurred: {e}")
    
    # path to csv folder
    csv_folder = os.path.join(base_dir, "iclicker_csv_exports")
    csv_files = glob.glob(os.path.join(csv_folder, "*.csv"))
    dataframes = {}
    for file in csv_files:
        df = pd.read_csv(file)
        df["Total Tracked"] = df["Total Absent"] + df["Total Present"] + df["Total Excused"]
        dataframes[os.path.basename(file)] = df
        print(f"Data from {os.path.basename(file)}:")
        print(df)
        print("\n")


if __name__ == '__main__':
    main()