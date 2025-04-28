#!/usr/local/bin/python
# Author: Naveen Nathan

import json
from fullGSapi.api import client as GradescopeClient
import os.path
import re
import io
import time
import warnings
import functools
from googleapiclient.errors import HttpError
import gspread
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import backoff
import csv
import pandas as pd
import backoff_utils
import requests
from datetime import datetime
import logging
import sys
import BeautifulSoup

logger = logging.getLogger(__name__)
load_dotenv()
GRADESCOPE_EMAIL = os.getenv("GRADESCOPE_EMAIL")
GRADESCOPE_PASSWORD = os.getenv("GRADESCOPE_PASSWORD")
logger.info(f"Gradescope email: {GRADESCOPE_EMAIL}")
logger.info(f"Gradescope password: {GRADESCOPE_PASSWORD}")

# Load JSON variables
# Note: this class JSON name can be made customizable, inputted through a front end user interface for example
# But the default is cs10_fall2024.json
class_json_name = 'cs10_sp25_test.json'
config_path = os.path.join(os.path.dirname(__file__), 'config/', class_json_name)
with open(config_path, "r") as config_file:
    config = json.load(config_file)

# IDs to link files
GRADESCOPE_COURSE_ID = config["GRADESCOPE_COURSE_ID"]
logger.info(f"Gradescope course ID: {GRADESCOPE_COURSE_ID}")

def initialize_gs_client():
    """
    Initializes GradeScope API client.

    Returns:
        (GradescopeClient): GradeScope API client.
    """
    gradescope_client = GradescopeClient.GradescopeClient()
    gradescope_client.log_in(GRADESCOPE_EMAIL, GRADESCOPE_PASSWORD)
    return gradescope_client


def get_assignment_deadlines(gs_client, class_id):
    """
    Extract assignment deadlines from Gradescope for a specific course.
    
    Args:
        gs_client (GradescopeClient): Authenticated Gradescope client
        class_id (str): The Gradescope class ID
        
    Returns:
        dict: Dictionary mapping assignment names to their deadlines and late deadlines
    """
    # Make sure client is logged in
    if not gs_client.logged_in:
        logger.error("You must be logged in to access assignment information")
        return None
    
    # Fetch assignments page
    response = gs_client.session.get(f"https://www.gradescope.com/courses/{class_id}")
    if not response or not response.ok:
        logger.error(f"Failed to get class page: {response}")
        return None
    
    deadlines = {}
    
    # Parse the content
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Parse assignment rows
    assignment_rows = soup.select('tr.js-assignmentTableAssignmentRow')
    
    for row in assignment_rows:
        try:
            # Get assignment name from the link
            name_elem = row.select_one('.assignments--rowTitleContainer a')
            
            # Get regular deadline
            due_date_elem = row.select_one('.submissionTimeChart--dueDate time')
            
            # Get late deadline if available
            late_due_date_elem = row.select_one('.submissionTimeChart--hardDueDate time')
            
            if name_elem and due_date_elem:
                name = name_elem.text.strip()
                due_date = due_date_elem.get('datetime')
                
                deadline_info = {
                    'due_date': due_date,
                    'due_date_formatted': due_date_elem.text.strip()
                }
                
                # Add late due date if available
                if late_due_date_elem:
                    deadline_info['late_due_date'] = late_due_date_elem.get('datetime')
                    deadline_info['late_due_date_formatted'] = late_due_date_elem.text.strip()
                
                deadlines[name] = deadline_info
        except Exception as e:
            logger.warning(f"Error parsing row: {e}")
    
    return deadlines


# Initialize and authenticate Gradescope client
gs_client = initialize_gs_client()

# Get deadlines for a specific course
deadlines = get_assignment_deadlines(gs_client, GRADESCOPE_COURSE_ID)

# Print the deadlines with formatted output
for assignment, info in deadlines.items():
    print(f"Assignment: {assignment}")
    print(f"  Due date: {info['due_date_formatted']} ({info['due_date']})")
    if 'late_due_date' in info:
        print(f"  Late due date: {info['late_due_date_formatted']} ({info['late_due_date']})")
    print()