#!/usr/bin/env python3
"""
Fill email addresses in Summary sheet by matching Legal Names with an assignment sheet
"""

from googleapiclient.discovery import build
from google.oauth2 import service_account
import os
import json
from dotenv import load_dotenv

load_dotenv()
service_account_json = os.getenv('SERVICE_ACCOUNT_CREDENTIALS')
service_account_info = json.loads(service_account_json)

creds = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)

service = build('sheets', 'v4', credentials=creds)
SPREADSHEET_ID = '130Vsasjjy8cc8MWqpyVy32mS9lqhvy0mhJyOhfTAmOo'

print("Step 1: Getting Legal Names from Summary sheet...")
# Get Legal Names from Summary sheet (column A, starting from row 4)
result = service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID,
    range='Summary!A4:A164'  # 161 students
).execute()
summary_names = result.get('values', [])
print(f"  Found {len(summary_names)} students in Summary sheet")

print("\nStep 2: Getting student data from an assignment sheet...")
# Use an assignment sheet that has Name, SID, and Email
# We'll use 'Lab 3: Conditionals, Reporters, u0026 Testing (Code)' as reference
reference_sheet = 'Lab 3: Conditionals, Reporters, u0026 Testing (Code)'
result = service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID,
    range=f"'{reference_sheet}'!A2:C200"  # Get Name, SID, Email (skip header)
).execute()
assignment_data = result.get('values', [])
print(f"  Found {len(assignment_data)} students in {reference_sheet}")

# Create a mapping from name to email
print("\nStep 3: Creating name-to-email mapping...")
name_to_email = {}
for row in assignment_data:
    if len(row) >= 3 and row[0] and row[2]:  # Name and email exist
        name = row[0].strip()
        email = row[2].strip()
        name_to_email[name] = email

print(f"  Created mapping for {len(name_to_email)} students")

# Match and prepare update data
print("\nStep 4: Matching names and preparing email updates...")
email_updates = []
matched_count = 0
unmatched_names = []

for idx, row in enumerate(summary_names):
    if row and row[0]:  # Name exists
        name = row[0].strip()
        email = name_to_email.get(name, '')
        
        if email:
            matched_count += 1
        else:
            unmatched_names.append(name)
        
        email_updates.append([email])

print(f"  Matched: {matched_count}")
print(f"  Unmatched: {len(unmatched_names)}")

if unmatched_names:
    print(f"\n  Unmatched names (first 5):")
    for name in unmatched_names[:5]:
        print(f"    - {name}")

# Update Summary sheet with emails
print("\nStep 5: Updating Summary sheet with emails...")
body = {
    'values': email_updates
}

result = service.spreadsheets().values().update(
    spreadsheetId=SPREADSHEET_ID,
    range='Summary!B4:B164',  # Column B, rows 4-164
    valueInputOption='RAW',
    body=body
).execute()

print(f"  ✓ Updated {result.get('updatedCells', 0)} cells")
print(f"  ✓ Updated {result.get('updatedRows', 0)} rows")

print("\n" + "="*60)
print("✓ Email filling completed!")
print("="*60)
