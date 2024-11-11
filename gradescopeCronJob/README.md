# README

### 1. Environment Setup
- Store GradeScope credentials in environment variables `EMAIL` and `PASSWORD`. Define these in a `.env` file.
- If you do not have a password setup on GradeScope, you will need to create a password.

### 2. Google Authentication Setup

1. **Create a New Project in Google Cloud Console**
   - Go to [Google Cloud Console](https://console.cloud.google.com/).
   - In the top-left corner, create a new project.

2. **Enable Google Sheets API**
   - Select your project and navigate to **APIs & Services**.
   - Go to the **Library** tab and search for "Google Sheets API".
   - Click on **Google Sheets API** and enable it.

3. **Create a Service Account**
   - Go to the **Credentials** tab within **APIs & Services**.
   - Fill out the fields as necessary to create a new service account.
   - No additional roles are required at this stage.

4. **Share Google Sheets Access**
   - Under the **Service Accounts** section on the **Credentials** page, click on the account email.
   - Share the Google Sheet with this email address to give access.
   - If this step is skipped, you will get a 403 Access Forbidden error when writing to Google Sheets.

5. **Generate JSON Key**
   - Navigate to the **Keys** section of the service account.
   - Click **Add Key** and create a JSON key.
   - This will download a key file to your computer.

6. **Set Up Environment Variables**
   - Create a `.env` file in this directory (if it doesn’t already exist).
   - Add the following line to the `.env` file:
     ```plaintext
     SERVICE_ACCOUNT_CREDENTIALS=<contents-of-downloaded-keyfile>
     ```
   - Example:
    ```plaintext
    SERVICE_ACCOUNT_CREDENTIALS={"type":"service_account","project_id":"your-project-id","private_key_id":"your-private-key-id","private_key":"-----BEGIN PRIVATE KEY-----\\nMIIEvAIBADANBgkq...\\n-----END PRIVATE KEY-----\\n","client_email":"your-service-account-email@your-project-id.iam.gserviceaccount.com","client_id":"your-client-id","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/your-service-account-email%40your-project-id.iam.gserviceaccount.com"}
    ```

### 3. Set Constants as Necessary

- **COURSE_ID**: The course ID is the final component of the URL on the GradeScope course homepage: `https://www.gradescope.com/courses/[COURSE_ID]`

- **SCOPES**: This should not be modified by the user. Use `"https://www.googleapis.com/auth/spreadsheets"` to allow write access.

- **SPREADSHEET_ID**: The spreadsheet ID is the final component of the spreadsheet’s URL: `https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit?gid=0#gid=0`

- **NUMBER_OF_STUDENTS**: The number of students enrolled in the course.

- **UNGRADED_LABS**: Some labs are not included in the final grade calculation. `UNGRADED_LABS` is a list of such labs. For example, if labs 5 and 6 are not included, set `UNGRADED_LABS` to `[5, 6]`.

- **TOTAL_LAB_POINTS**: Used only for the final grade calculation; this is the total number of lab points in a semester.

- **NUM_LECTURES**: Used only for the final lecture-quiz grade calculation.

- **SPECIAL_CASE_LABS**: A list of 4-part labs (lab assignments with four dropboxes, instead of the typical one or two).

- **NUM_LECTURE_DROPS**: The number of drops included in the lecture-quiz grade calculation.