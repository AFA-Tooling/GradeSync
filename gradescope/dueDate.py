#!/usr/bin/env python
# coding: utf-8

# In[33]:


import json
import csv
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


# In[34]:


def parse_html(html):
    return BeautifulSoup(html, "html.parser")


# In[41]:


load_dotenv()
GRADESCOPE_EMAIL = os.getenv("GRADESCOPE_EMAIL")
GRADESCOPE_PASSWORD = os.getenv("GRADESCOPE_PASSWORD")
COURSE_ID = os.getenv("COURSE_ID")
CSV_FILE_NAME = f"E:\AdminStuff\Desktop\GradeSync\gradescope\data\Course{COURSE_ID}_Due Dates.csv"


# In[36]:


gradescopeROOT = "https://www.gradescope.com"
session = requests.Session()
login_page_res = session.get(gradescopeROOT)
login_page = BeautifulSoup(login_page_res.text, 'html.parser')


token = None
for form in login_page.find_all('form'):
    if form.get('action') == '/login':
        for input_element in form.find_all('input'):
            if input_element.get('name') == 'authenticity_token':
                token = input_element.get('value')


# In[37]:


login_payload = {
    'utf8': '✓',
    'authenticity_token': token,
    'session[email]': GRADESCOPE_EMAIL,
    'session[password]': GRADESCOPE_PASSWORD,
    'session[remember_me]': 0,
    'commit': 'Log In',
    'session[remember_me_sso]': 0
}
fieldnames = ['title', 'type', 'due_date', 'link']


# In[38]:


login_response = session.post(
    gradescopeROOT + '/login',
    params=login_payload
)
history = login_response.history
if len(history) > 0 and history[0].status_code == 302:
    print("log in successfully")


# In[42]:


dashboard_res = session.get(f"{gradescopeROOT}/courses/{COURSE_ID}")
dashboard = parse_html(dashboard_res.text)
assignments_table = dashboard.find('div', {'data-react-class': 'AssignmentsTable'})
due_dates = []
if assignments_table:
    json_str = assignments_table.get('data-react-props')
    if json_str:
        try:
            data = json.loads(json_str)
            assignments = data.get('table_data', [])
            for assignment in assignments:
                due = {}
                due['title'] = assignment.get('title')
                due['type'] = assignment.get('type')
                due['link'] = assignment.get('url')
                submission_window = assignment.get('submission_window')
                if due['title'] and submission_window:
                    due['due_date'] = submission_window.get('due_date')
                due_dates.append(due)
            print(due_dates)
            with open(CSV_FILE_NAME, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(due_dates)
                print(f"output file:{CSV_FILE_NAME}")
        except json.JSONDecodeError:
                print("Error: Could not parse JSON data from 'data-react-props'.")  
        except Exception as e:
                print(f"\n❌ Writing error: {e}")


# In[39]:




