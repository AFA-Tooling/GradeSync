"""
iClicker Service Client

Modern client for iClicker data access using Selenium WebDriver.
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import glob
import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class IClickerClient:
    """
    Client for iClicker attendance data extraction using Selenium automation.
    
    Features:
    - Automated login via campus portal (UC Berkeley)
    - Multi-course data download
    - Duo 2FA handling
    - Course-specific file tracking
    """
    
    ICLICKER_URL = 'https://instructor.iclicker.com'
    INSTITUTION = 'University of California Berkeley'
    
    def __init__(
        self,
        username: str,
        password: str,
        download_dir: Optional[str] = None,
        headless: bool = False
    ):
        """
        Initialize iClicker client.
        
        Args:
            username: Campus login username
            password: Campus login password
            download_dir: Directory for CSV downloads (default: ./downloads)
            headless: Run browser in headless mode
        """
        self.username = username
        self.password = password
        self.download_dir = download_dir or str(Path.cwd() / 'downloads')
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        
        # Create download directory if needed
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)
        
    def _setup_driver(self) -> webdriver.Chrome:
        """Setup Chrome WebDriver with appropriate options."""
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        }
        
        chrome_options = Options()
        chrome_options.add_experimental_option("prefs", prefs)
        
        if self.headless:
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        logger.info("Chrome WebDriver initialized")
        return driver
    
    def _close_cookie_banner(self):
        """Close cookie consent banner if present."""
        try:
            close_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.onetrust-close-btn-handler")
                )
            )
            close_button.click()
            logger.info("Closed cookie banner")
        except Exception:
            logger.debug("No cookie banner to close")
    
    def login(self, duo_wait_seconds: int = 15) -> bool:
        """
        Login to iClicker via campus portal.
        
        Args:
            duo_wait_seconds: Time to wait for Duo 2FA (default 15)
            
        Returns:
            True if login successful
            
        Raises:
            Exception if login fails
        """
        if self.driver is None:
            self.driver = self._setup_driver()
        
        logger.info("Navigating to iClicker login page")
        self.driver.get(f'{self.ICLICKER_URL}/#/onboard/login')
        
        try:
            self._close_cookie_banner()
            time.sleep(3)
            
            # Click campus portal login
            WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.LINK_TEXT, "Sign in through your campus portal")
                )
            ).click()
            logger.info("Clicked campus portal login")
            
            # Select institution
            WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located((By.ID, "institute"))
            )
            select = Select(self.driver.find_element(By.ID, "institute"))
            select.select_by_visible_text(self.INSTITUTION)
            
            WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-primary"))
            ).click()
            
            # Enter credentials
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.ID, 'username'))
            ).send_keys(self.username)
            
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.ID, 'password'))
            ).send_keys(self.password)
            
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.NAME, 'submit'))
            ).click()
            
            logger.info("Submitted login credentials")
            logger.info(f"Waiting {duo_wait_seconds}s for Duo authentication...")
            time.sleep(duo_wait_seconds)
            
            # Click "Trust this browser" button
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.element_to_be_clickable((By.ID, "trust-browser-button"))
                ).click()
                logger.info("Clicked trust browser button")
                time.sleep(5)
            except Exception:
                logger.warning("Could not find trust browser button")
            
            logger.info("Login successful")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise
    
    def download_course_attendance(self, course_name: str) -> str:
        """
        Download attendance data for a specific course.
        
        Args:
            course_name: Course name as shown in iClicker
                        (e.g., "[CS10 | Fa25] Lab")
        
        Returns:
            Path to downloaded CSV file
            
        Raises:
            Exception if download fails
        """
        if self.driver is None:
            raise RuntimeError("Must call login() before downloading data")
        
        logger.info(f"Downloading attendance for: {course_name}")
        
        try:
            # Navigate to courses page
            self.driver.get(f"{self.ICLICKER_URL}/#/courses")
            time.sleep(5)
            
            # Click course button
            WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, f"button[title='{course_name}']")
                )
            ).click()
            
            # Click Attendance tab
            WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//span[contains(text(), 'Attendance')]")
                )
            ).click()
            
            # Click Export button
            WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Export')]")
                )
            ).click()
            
            # Select all files
            time.sleep(2)
            WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.ID, "check-box-header"))
            ).click()
            
            # Click export submit button
            time.sleep(2)
            WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@type='submit' and contains(text(), 'Export')]")
                )
            ).click()
            
            # Wait for download
            time.sleep(10)
            
            # Find most recent CSV
            csv_files = glob.glob(os.path.join(self.download_dir, "*.csv"))
            if not csv_files:
                raise FileNotFoundError("No CSV files found in download directory")
            
            latest_file = max(csv_files, key=os.path.getmtime)
            logger.info(f"Downloaded: {latest_file}")
            return latest_file
            
        except Exception as e:
            logger.error(f"Failed to download {course_name}: {e}")
            raise
    
    def download_all_courses(self, course_names: List[str]) -> Dict[str, str]:
        """
        Download attendance data for multiple courses.
        
        Args:
            course_names: List of course names
            
        Returns:
            Dict mapping course name to downloaded file path
        """
        results = {}
        
        for course_name in course_names:
            try:
                file_path = self.download_course_attendance(course_name)
                results[course_name] = file_path
            except Exception as e:
                logger.error(f"Skipping {course_name} due to error: {e}")
                continue
        
        logger.info(f"Successfully downloaded {len(results)}/{len(course_names)} courses")
        return results
    
    def read_attendance_csv(self, csv_path: str) -> pd.DataFrame:
        """
        Read iClicker attendance CSV into DataFrame.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            pandas DataFrame
        """
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} records from {csv_path}")
        return df
    
    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("WebDriver closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
