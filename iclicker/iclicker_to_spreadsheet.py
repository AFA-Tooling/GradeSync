import os
import glob
import json
import logging
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
import pandas as pd
from google.oauth2.service_account import Credentials

load_dotenv()

ICLICKER_USERNAME = os.getenv("ICLICKER_USERNAME")
ICLICKER_PASSWORD = os.getenv("ICLICKER_PASSWORD")

# load config variables
class_json_name = 'cs10.json'
config_path = os.path.join(os.path.dirname(__file__), 'config/', class_json_name)
logging.info(f"Loading config from {config_path}")
with open(config_path, "r") as config_file:
    config = json.load(config_file)
SCOPES = config["SCOPES"]
SPREADSHEET_ID = config["SPREADSHEET_ID"]
COURSES = config["COURSES"]

credentials_json = os.getenv("SERVICE_ACCOUNT_CREDENTIALS")
credentials_dict = json.loads(credentials_json)
credentials = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
client = gspread.authorize(credentials)

base_dir = os.path.dirname(os.path.abspath(__file__)) # path to folder
download_dir = os.path.join(base_dir, "iclicker_csv_exports") # ensure folder exists


def selenium_bot():
    """
    Bot automates logging into iClicker, looping through all courses, and downloading attendance data
    while explicitly tracking which CSV file belongs to which course (lecture, lab, or discussion).
    """
    logging.info("Starting Selenium bot...")
    
    # chrome options
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    
    # initialize bot
    chrome_options = Options()
    chrome_options.add_experimental_option("prefs", prefs)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # dictionary for exported files per course
    exported_files = {}

    # navigate to iClicker login page
    driver.get('https://instructor.iclicker.com/#/onboard/login')
    logging.info("Navigated to iClicker login page")

    # bot signs in with credentials
    try:
        # check if there is a cookie tab that needs to be closed. 
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.onetrust-close-btn-handler"))
            )
            close_button.click()
            logging.info("Closed cookie banner")
        except Exception as e:
            # If it times out or the button isn't found/clickable, this will be triggered
            logging.info("No cookie banner found or not clickable")

        time.sleep(3)
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in through your campus portal"))).click()
        logging.info("Clicked campus portal login")
        WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, "institute")))
        select_institution = Select(driver.find_element(By.ID, "institute"))
        select_institution.select_by_visible_text("University of California Berkeley")
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-primary"))).click()

        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'username'))).send_keys(ICLICKER_USERNAME)
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'password'))).send_keys(ICLICKER_PASSWORD)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.NAME, 'submit'))).click()
        logging.info("Submitted login credentials")

        logging.info("Waiting for Duo authentication...")

        # allow time for duo authentication
        time.sleep(15)  

        #Click this is my device button 
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "trust-browser-button"))).click()
        time.sleep(5)

        # iterate over courses so bot can access lecture, lab, and discussion data without another duo push
        for course_name in COURSES:
            try:
                logging.info(f"Processing course: {course_name}")
                driver.get("https://instructor.iclicker.com/#/courses")
                time.sleep(5)

                # click course
                WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, f"button[title='{course_name}']"))
                ).click()
                
                # click attendance
                WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Attendance')]"))
                ).click()

                # click export
                WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Export')]"))
                ).click()

                # select all files
                time.sleep(2)
                WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "check-box-header"))).click()

                # click export button
                time.sleep(2)
                WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and contains(text(), 'Export')]"))
                ).click()

                time.sleep(10)

                # track which file belongs to which course
                csv_files = glob.glob(os.path.join(download_dir, "*.csv"))
                exported_files[course_name] = max(csv_files, key=os.path.getmtime)

            except Exception as e:
                logging.error(f"Error processing {course_name}: {e}")
                continue  

    except Exception as e:
        logging.error(f"Login error: {e}")

    finally:
        driver.quit()
        logging.info("Closed browser and quit driver")
    
    return exported_files


def export_to_google_sheets(course_name, file_path):
    """
    Exports a specific CSV file using file_path to the correct Google Sheets spreadsheet.
    """
    
    logging.info(f"Exporting {course_name} CSV to Google Sheets...")
    df = pd.read_csv(file_path)
    df["Total Tracked"] = df["Total Absent"] + df["Total Present"] + df["Total Excused"]

    # convert attendance values to binary (0 = absent, 1 = present/excused)
    status_map = {"ABSENT": 0, "PRESENT": 1, "EXCUSED": 1}
    df.replace(status_map, inplace=True)
    df = df.dropna(subset=['Student Name'])  # remove empty rows

    # convert dataframe to a list format for google sheets
    sheet_data = [df.columns.tolist()] + df.astype(str).values.tolist()

    try:
        sheet = client.open_by_key(SPREADSHEET_ID)

        # use course name as sheet name
        sheet_name = course_name.replace(" ", "_")

        try:
            worksheet = sheet.worksheet(sheet_name)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=sheet_name, rows="100", cols="20")

        worksheet.update(sheet_data)
        logging.info(f"Successfully uploaded {course_name} data to Google Sheets")

        # delete the local csv after uploading
        os.remove(file_path)
        logging.info(f"Deleted local file: {file_path}")

    except Exception as e:
        logging.error(f"Error exporting {course_name} to Google Sheets: {e}")


def main():
    """
    Main function to handle Selenium automation and Google Sheets export.
    """
    
    logging.info("Starting main function")
    exported_files = selenium_bot()

    for course, file_path in exported_files.items():
        export_to_google_sheets(course, file_path)


if __name__ == '__main__':
    main()
    