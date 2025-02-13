from faker import Faker
import csv

fake = Faker()
Faker.seed(42)  # For consistent results

def create_berkeley_email(name):
    # Split name into parts and clean special characters
    name_parts = name.split()
    first = name_parts[0].lower().replace("'", "").replace("-", "")
    last = name_parts[-1].lower().replace("'", "").replace("-", "")
    
    # Create email with first.last format
    return f"{first}.{last}@berkeley.edu"

students = []
used_emails = set()

for _ in range(5):
    name = fake.unique.name()
    email = create_berkeley_email(name)
    
    # Ensure unique emails
    counter = 1
    while email in used_emails:
        email = f"{email.split('@')[0]}{counter}@berkeley.edu"
        counter += 1
    
    students.append({
        "First Name": name.split()[0],
        "Last Name": name.split()[1],
        "Email": email,
        "UID": fake.unique.random_number(10, True)
    })
    used_emails.add(email)

with open("/Users/nawodakw/Desktop/GradeSync/test_env/students.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["First Name", "Last Name", "Email", "UID"])
    writer.writeheader()
    writer.writerows(students)