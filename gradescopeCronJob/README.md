# README

### Requirements  

- **Gradescope Access**: Teaching Assistant or Instructor role on a CS10 Gradescope course instance.  
- **Google Cloud Project**: Configured for Google Sheets API access. 


### 1. Environment Setup

- Store Gradescope credentials in environment variables `GRADESCOPE_EMAIL` and `GRADESCOPE_PASSWORD`. Define these in a `.env` file.
- If you do not have a password setup on Gradescope, you will need to create a password.
- There should be three variables total in the `.env` file. Follow step 2 to add the `SERVICE_ACCOUNT_CREDENTIALS` variable.


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

### 3. Define a config file to define constraints

1. **Create a new config file**: Navigate into the folder `gradescopeCronJob/config/`, and create a new config file with the naming scheme `{class}_{semester, year}.json`. For example, the file could be named `cs10_sp25.json`. 

2. **Define the necessary constraints**:
   - **GRADESCOPE_COURSE_ID**: The course ID is the final component of the URL on the Gradescope course homepage: `https://www.gradescope.com/courses/[GRADESCOPE_COURSE_ID]`
   
   - **PL_COURSE_ID**: The course ID is the component of the URL following course_instance. For example: `https://us.prairielearn.com/pl/course_instance/[PL_COURSE_ID]/instructor/instance_admin/access`

   - **SCOPES**: This should not be modified by the user. Use `"https://www.googleapis.com/auth/spreadsheets"` to allow write access.

   - **SPREADSHEET_ID**: The spreadsheet ID is the final component of the spreadsheet’s URL: `https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit?gid=0#gid=0`

   - **NUMBER_OF_STUDENTS**: Please enter a number **greater than** the total number of students, to account for late adds. There is no harm in choosing a NUMBER_OF_STUDENTS greater than the actual number.

---

# 4. Set up the spreadsheet
- Make a copy of the following template sheet: 

https://docs.google.com/spreadsheets/d/1V77ApZbfwLXGGorUaOMyWrSyydz_X1FCJb7MLIgLCSw/edit?gid=0#gid=0

# 5. Docker Container

#### Prerequisites

- Docker installed on your system.

## Build and Run the Docker Container



### Step 1: Build the Docker Image

In this directory, run the following command to build the Docker image:

```bash
docker build -t gradescope-cron-job .
```

This command will create a Docker image with the cron job configuration and necessary dependencies. 


### Step 2: Run the Docker Container

Once the image is built, start the container in detached mode:

```bash
docker run -d --name gradescope-cron-container
```

This command will run the container in the background. 


### Step 3: Monitor the Logs

To view the cron job output, check the container logs. Use the following command to follow the logs in real-time:

```bash
docker logs -f gradescope-cron-container
```

Replace `gradescope-cron-job` with the actual container ID if needed. This command will display live logs, allowing you to monitor the cron job's execution.

### Example Log Command with Container ID

Alternatively, if you know the container ID, you can run:

```bash
docker logs -f e9b989ea03676f2141b1014891f436c7b3061320a479d8fa3231a4426c84d4c1
```
- e9b989ea03676f2141b1014891f436c7b3061320a479d8fa3231a4426c84d4c1 is an example to replace with the containerID.


## Configuration

- The cron job schedule and script configurations are set up within the Dockerfile and accompanying cron job files.
- Logs are stored in `/var/log/cron.log` within the container and are accessible through Docker logs as shown.

## Stopping the Container

To stop the running container:

```bash
docker stop gradescope-cron-container
```

## Removing the Container

If you wish to remove the container after stopping it:

```bash
docker rm gradescope-cron-container
```


## Troubleshooting

- **Container isn't starting**: Check Docker build output for errors during the image creation step.


# 6. Deployment

### **Deployment Pre-Checklist:**

1. **Updated Configuration File with IDs**
   - Ensure the configuration file is up-to-date with the correct IDs for the relevant resources (e.g., Google Sheets ID, GradeScope course ID, etc.).

2. **Updated `class_json_name` in `gradescope_to_spreadsheet.py` Script**
   - Verify that the `class_json_name` is correctly updated in the script at line 48 with the relevant configuration file.


### **Step 1: Test the Script one more time**
Run:
```bash
python3 gradescope_to_spreadsheet.py
```
Navigate to the Google Sheets to confirm that the update was officially made. 
1. Navigate to the google sheets whose ID was specified in the configuration JSON file
2. In Google Sheets, click file → see version history
3. Check the version history to ensure that the google sheet was updated by gradesync-sheets-service@eecs-gradeview.iam.gserviceaccount.com
4. Click through a few of the google sheets tabs in order to confirm that all of the student data was edited and refreshed.
4. Compare with the data source, GradeScope course, through verifying 1 assignment by comparing the grade data from GradeScope and the grade data displayed in google sheets



### **Step 2: Build the Docker Container**
Build the Docker container from the `Dockerfile`:
```bash
docker build -t cs10-sp25-production .
```
For the containers, the naming convention is as following:
1. Onboarding practice: `build -t gradescope-cron-job .`
1. Test deployment: `build -t cs10-sp25-test1 .`
2. Production deployment: `build -t cs10-sp25-production .`

### **Step 3: Check if the Docker Image Exists**
Verify that the image was built successfully:
```bash
docker image ls
```

### **Step 4: Run the Docker Container**
Run the container:
```bash
docker run cs10-sp25-production
```

### !! 🛑 STOP 🛑 !!  Confirm that the Docker container is fully functioning before tagging the container
Make sure the Docker container works as expected before proceeding with tagging or deploying it to the cloud. Verify the logging statements in the terminal are correct. 


### **Step 5: Tag the Docker Container**
Tag the Docker container with the destination in Google Cloud Artifact Registry:
```bash
docker tag cs10-sp25-production us-west1-docker.pkg.dev/eecs-gradeview/gradescope-cron-job-cs10-sp25/cs10-sp25-production:latest
```

### **Step 5: Initialize Google Cloud and Authorize**
Set up Google Cloud CLI and authenticate:
```bash
gcloud init
gcloud auth login
gcloud auth configure-docker us-west1-docker.pkg.dev
```

### **Step 6: Push the Tagged Docker Container**
Push the Docker image to Google Cloud Artifact Registry:
```bash
docker push us-west1-docker.pkg.dev/eecs-gradeview/gradescope-cron-job-cs10-sp25/cs10-sp25-production
```

### Google Cloud Section

### **Step 1: Verify on Google Cloud Artifact Registry**

1. Navigate to the [Google Cloud Artifact Registry](https://console.cloud.google.com/artifacts).
2. In the left-hand navigation panel, go to **"eecs-gradeview"**.
3. Open the repository named:  
   ```
   gradescope-cron-job-cs10-sp25
   ```
4. Inside the repository, find and click on the deployment name:  
   ```
   cs10-sp25-production
   ```
5. Click on the image tagged:  
   ```
   latest
   ```
   This corresponds to the most recent image deployed (as confirmed in your terminal commands).


### **Step 2: Test Deployment with Google Cloud Run**

1. Navigate to [Google Cloud Run Jobs](https://console.cloud.google.com/run/jobs?invt=Abt-xw&project=eecs-gradeview).
2. Select the **“Jobs”** tab (next to the “Services” tab).
3. Click **`Deploy Container` → Deploy Job**.
4. Fill in the deployment details:
   - **Container Image URL**: Select the container image from the repository → container name → image with the `latest` tag.
   - **Job Name**: This should be automatically populated with the container name.
   - **Region**: Select `us-west1` (to include data from the Oregon Google center).
   - **Number of Tasks**: Leave as `1` (default). Only one run is needed to complete the script.
5. Click **“Create”**.
6. You should now see the container name listed as a **Google Cloud Job**.
7. Test the deployment by clicking **“Execute”** (the play button to the left of the word Execute).
8. Confirm that the deployment **succeeded**.


### **Step 3: Verify Update on Google Sheets After Single Execution of Cloud Job**

1. Navigate to the Google Sheet whose ID was specified in the configuration file used during deployment.
2. In Google Sheets, go to **File → See version history**.
3. Confirm that the sheet was updated by:  
   `gradesync-sheets-service@eecs-gradeview.iam.gserviceaccount.com`
4. Click through several sheet tabs to verify that all student data was updated and refreshed.
5. Cross-check with the data source (GradeScope):
   - Choose one assignment.
   - Compare the grade data displayed in Google Sheets with the corresponding grades in GradeScope to ensure accuracy.


### **Step 4: Begin Configuring the Google Cloud Run Trigger for the Automated Cloud Scheduler**

1. In the Cloud Run job (with the container name), navigate to the **`Triggers`** tab.
2. Click the **“+ Add schedule trigger”** button.

#### Define the Schedule

- **Name**: Use the default provided (e.g. `cs10-sp25-deployment-scheduler-trigger`).
- **Region**: `us-west1` (Oregon). Always keep this as `us-west1` for consistency.
- **Frequency**:  
  ```text
  */2 * * * *
  ```  
  This sets the job to run every 2 minutes—ideal for initial verification. (You will change this later once functionality is confirmed.)
- **Timezone**: `Coordinated Universal Time (UTC)` – this is the default and can remain unchanged.

#### Configure the Execution

- **Compute Service Account**: Use the **default compute service account**.  
  This account handles authentication and runs the Cloud Run scheduler (distinct from the service account that interacts with Google Sheets via the script).

> ✅ _Note:_ Record the name of this default compute service account in a convenient location.

🚫 **Do not confirm the trigger yet.**  
Exit this screen for now—an additional authentication permission still needs to be configured before the trigger can be finalized.


### **Step 5: Grant IAM Role to Google Cloud Scheduler**

To allow Cloud Scheduler to trigger your Cloud Run Job, you must assign the appropriate IAM role to the Cloud Scheduler's service account.

#### Identify the Cloud Scheduler Service Account

1. Use the **default compute service account** identified in **Step 4**.  
   (_You should have noted this earlier._)
2. Alternatively, retrieve the project number by running:
   ```bash
   gcloud projects describe eecs-gradeview --format="value(projectNumber)"
   ```
3. Convert the project number into the service account email in this format:
   ```
   [PROJECT_NUMBER]-compute@developer.gserviceaccount.com
   ```
4. Confirm that this is the **same account** used in Step 4.

#### Grant the Cloud Run Invoker Role

Run the following command, updating it with:
- Your **Cloud Run job name** (e.g. `cs10-sp25-production`)
- The **default compute service account email**

```bash
gcloud run jobs add-iam-policy-binding cs10-sp25-production \
  --member="serviceAccount:900000000000-compute@developer.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --project=eecs-gradeview
```

#### Expected Output (Example)

After executing the command, you should see a confirmation message like:

```yaml
Updated IAM policy for job [cs10-sp25-production].
bindings:
- members:
  - serviceAccount:900000000000-compute@developer.gserviceaccount.com
  role: roles/run.invoker
etag: BwYyEKL1XrA=
version: 1
```

✅ **You’ve successfully granted the necessary permission.**  
You can now proceed to finalize the Cloud Run Scheduler Trigger.

### **Step 6: Actually Configure the Google Cloud Run Trigger**

Now that permissions have been granted, let’s actually configure the scheduler trigger.

#### Navigate to Cloud Run Job

1. Go to your Cloud Run Job with the container name.
2. Open the `Triggers` tab.
3. Click the **“+ Add schedule trigger”** button.

#### Define the Schedule (Initial Setup)

- **Name:** Use the default provided (e.g., `cs10-sp25-deployment-scheduler-trigger`)
- **Region:** `us-west1 (Oregon)` — this must remain consistent
- **Frequency:**  
  ```cron
  */2 * * * *
  ```
  _(Every 2 minutes, for initial testing)_
- **Timezone:** Coordinated Universal Time (UTC)

#### Configure the Execution

- **Service Account:** Use the **default compute service account**  
  (_Used to authenticate and run the Google Cloud Run scheduler — different from the one used for the Sheets API in your script_)

Once created, a visual block will appear representing the deployment trigger.

#### View & Edit Trigger Details
Click **“View details”** to open a new tab with advanced configuration options.

##### Reconfirm the Schedule

- **Description:** Leave blank for now
- **Frequency:**
  ```cron
  */2 * * * *
  ```
- **Timezone:** Coordinated Universal Time (UTC)

##### Configure Execution Settings

- **Target type:** HTTP (default)
- **URL:**  
  ```
  https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/eecs-gradeview/jobs/cs10-sp25-alt-deployment-2:run
  ```
- **HTTP Method:** POST (default)
- **HTTP Header**
   - Name: `User-Agent`
   - Value: `Google-Cloud-Scheduler`
- **Auth Header:** Add OAuth token (default)
- **Service Account:** Default compute service account (default)
- **Scope:** `https://www.googleapis.com/auth/cloud-platform` (default)

##### Optional Settings

- **Max retry attempts:** `1`
- **Max retry duration:** `0s` _(unlimited)_
- **Min backoff duration:** `5s`
- **Max backoff duration:** `1h`
- **Max doublings:** `5`
- **Attempt deadline:** `3m`

Click **“Update”** to finalize.

---

✅ You will now be redirected to the [Google Cloud Scheduler Jobs Interface](https://console.cloud.google.com/cloudscheduler?invt=Abt-xw&project=eecs-gradeview).

- Scroll to the far right of the page to view columns like:
  - **Last run**
  - **Next run**
  - **Last updated**

If the job fails:
- Go to the **“Actions”** section
- Click the **3-dot menu**
- Select **“View Logs”** to investigate the error


### **Step 7: Verify Update on Google Sheets After Cloud Scheduled Execution of Job**

After the scheduled Cloud Run job has executed, confirm that the Google Sheets document has been updated correctly.

#### Steps:

1. Navigate to the Google Sheets file  
   - Use the **Google Sheet ID** specified in the configuration file used during script deployment.

2. Refresh the Google Sheet to load any recent updates.

3. Go to **File → Version history → See version history**

4. Confirm that an edit was made by the following service account:
   ```
   gradesync-sheets-service@eecs-gradeview.iam.gserviceaccount.com
   ```

5. Browse through multiple tabs within the spreadsheet to verify that:
   - All student data has been updated
   - The changes reflect the expected data source updates

6. Wait for the **initial 2-minute scheduled trigger cycle** to complete.

7. After waiting, repeat step 3 to confirm that **another update occurred**, indicating that the Cloud Scheduler has executed successfully.

> ✅ If everything appears correct, the scheduler and job configuration are working as intended.


### **Step 8: Update the Cloud Scheduler Frequency**

Now that the Cloud Scheduler has been verified through Google Sheets, update the Cloud Run frequency according to the desired schedule.

#### Steps:

1. Navigate to the **Google Cloud Scheduler** interface.

2. Locate the **Cloud Scheduler job** created for the Cloud Run deployment.

3. Update the **frequency** based on the desired schedule:
   - For **once per hour**:
     ```
     0 */1 * * *
     ```
   - For **once every 2 hours**:
     ```
     0 */2 * * *
     ```
   - For **once per day at 10 AM UTC** (equivalent to 3 AM PST). This is a great time for updating since typically compute resources are used less during that time:
     ```
     0 10 */1 * *
     ```


4. Click **Update** to save the changes.

> ✅ Ensure that the updated frequency reflects your desired update interval for optimal performance.



### **Step 9: CELEBRATE!**

Congratulations! 🎉

The deployment of the Docker container, hosted on Google Cloud, and scheduled with Google Cloud Run Scheduler is complete! 

Enjoy having an automated integration! 🚀



## Additional Notes

### **Debugging Tips:**

#### **Problem: Permission Denied for Writing to the Output Google Sheet**
- **Solution:** Double check if the output Google Sheet is shared with `gradesync-sheets-service@eecs-gradeview.iam.gserviceaccount.com`.
- **When This Can Be Caught:** After running `python3 gradescope_to_sheets.py` following the update of the JSON configuration and IDs.

#### **Problem: No IAM Access or Permission Denied Related to Google Cloud**
- **Solution:** Contact the current admin of the `eecs-gradeview` project for specific permissions required to execute the entire process end-to-end. 
    - This is most effective during a synchronous meeting, where you can walk through the steps and ensure access is granted in real-time.
    - Alternatively, this can be done asynchronously by sending screenshots or instructions to the admin to grant permissions for each step.
- **When This Can Be Caught:** During the initial setup or when encountering permission-related errors.

#### **Problem: Cloud Run Scheduler Failed or Showed Permission Denied**
- **Solution:** The failure occurs due to the compute account not having invoke access to run the scheduler on the cloud container.
    - Grant the Cloud Run Invoker Permission using the following command:
    
    ```bash
    gcloud run jobs add-iam-policy-binding cs10-sp25-production \
      --member="serviceAccount:900000000000-compute@developer.gserviceaccount.com" \
      --role="roles/run.invoker" \
      --project=eecs-gradeview
    ```
    - After running the command, you should see the following output in the terminal:
    
    ```
    Updated IAM policy for job [cs10-sp25-production].
    bindings:
    - members:
      - serviceAccount:900000000000-compute@developer.gserviceaccount.com
      role: roles/run.invoker
    etag: BwYyEKL1XrA=
    version: 1
    ```
- **When This Can Be Caught:** After setting up the Cloud Run scheduler and analyzing the logs.

#### **Additional Debugging Tips:**

1. **Problem: Cloud Run Deployment Fails or Times Out**
   - **Solution:** Ensure that the cloud job's container image is correctly configured and up-to-date. Re-deploy the container image if needed.
   - **When This Can Be Caught:** During deployment or when attempting to execute the Cloud Run job.

2. **Problem: Cloud Scheduler Trigger Not Executing on Time**
   - **Solution:** Double-check the trigger configuration and ensure the correct time zone and frequency are set. Also, verify that the Cloud Scheduler has the proper permissions to trigger the job.
   - **When This Can Be Caught:** After setting the Cloud Scheduler trigger and waiting for execution.

3. **Problem: Google Sheets Not Updating as Expected**
   - **Solution:** Check the execution logs for any errors related to the Google Sheets API or permissions. Ensure the Google Sheets API service account has the required permissions.
   - **When This Can Be Caught:** After executing the Cloud Run job and verifying the changes in the Google Sheets.

4. **Problem: Incorrect Output Data in Google Sheets**
   - **Solution:** If the data is incorrect, review the mapping between the GradeScope data and the Google Sheets columns. Verify that the JSON configuration file has been correctly updated with the appropriate mappings.
   - **When This Can Be Caught:** After verifying the updated Google Sheets data and comparing it with the expected output.

5. **Problem: Container Image Build Failures**
   - **Solution:** Review the Dockerfile for any issues. Check the build logs for specific error messages and ensure all dependencies are correctly installed.
   - **When This Can Be Caught:** During the container image build process.

6. **Problem: Cloud Scheduler Not Triggering the Job as Expected**
   - **Solution:** Check the Cloud Scheduler logs to ensure that the job trigger is being fired as per the defined schedule. Confirm that the trigger URL and method are correct in the scheduler setup.
   - **When This Can Be Caught:** After setting up the Cloud Scheduler job and verifying that the job isn't being triggered at the expected times.

By following these debugging tips and adding some of the additional checks, you should be able to address common issues and ensure smooth execution of the process.


