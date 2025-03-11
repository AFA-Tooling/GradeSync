import os
import glob
import json
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import gspread
import requests
from bs4 import BeautifulSoup
import pandas as pd
from google.oauth2.service_account import Credentials

load_dotenv()

ICLICKER_USERNAME = os.getenv("ICLICKER_USERNAME")
ICLICKER_PASSWORD = os.getenv("ICLICKER_PASSWORD")

# load json variables
class_json_name = 'cs10_dummy'
config_path = os.path.join(os.path.dirname(__file__), 'config/', class_json_name)
with open(config_path, "r") as config_file:
    config = json.load(config_file)
SCOPES = config["SCOPES"]
SPREADSHEET_ID = config["SPREADSHEET_ID"]

credentials_json = os.getenv("SERVICE_ACCOUNT_CREDENTIALS")
credentials_dict = json.loads(credentials_json)
credentials = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
client = gspread.authorize(credentials)

base_dir = os.path.dirname(os.path.abspath(__file__)) # path to folder
download_dir = os.path.join(base_dir, "iclicker_csv_exports") # ensure folder exists


def selenium_bot():
    # create chromeoptions and set download preferences
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    
    # create selenium driver to bypass login credentials
    chrome_options = Options()
    chrome_options.add_experimental_option("prefs", prefs)
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
        
        
def export_to_csv():
    # path to csv folder
    csv_folder = os.path.join(base_dir, "iclicker_csv_exports")
    csv_files = glob.glob(os.path.join(csv_folder, "*.csv"))

    # print data frame based on timestamp
    if not csv_files:
        raise FileNotFoundError("No CSV files found in the directory.")
    most_recent_file = max(csv_files, key=os.path.getmtime)
    
    # return most recently exported file
    df = pd.read_csv(most_recent_file)
    df["Total Tracked"] = df["Total Absent"] + df["Total Present"] + df["Total Excused"]
    df = df.dropna(subset=['Student Name'])
    return df, csv_files

def export_to_google_sheets():
    df, csv_files = export_to_csv()
    sheet_data = [df.columns.tolist()] + df.astype(str).values.tolist()

    try:
        # open google sheet
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # create a new sheet with timestamp
        most_recent_file = max(csv_files, key=os.path.getmtime)
        sheet_name = os.path.basename(most_recent_file).replace(".csv", "")
        try:
            worksheet = sheet.worksheet(sheet_name)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=sheet_name, rows="100", cols="20")
        
        # update the worksheet with new data
        worksheet.update(sheet_data)
        print("Finished exporting to Google Sheets.")
        
        # remove local csv files after export
        for file_path in csv_files:
            os.remove(file_path)
        print("Local CSV files deleted after export.")
  
    except Exception as e:
        print(f"An error occurred: {e}")


def main():
    selenium_bot()
    export_to_google_sheets()

if __name__ == '__main__':
    main()