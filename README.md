# GradeSync

### About

GradeSync is a backend microservice that integrates with assessment platforms to fetch student grades and facilitate management of post-semester submissions. GradeSync enables students to submit coursework after the term ends and view their updated grades on the GradeView dashboard. GradeSync automates gradebook updates, eliminating the need for manual instructor intervention.


### Setting up Integrations
Navigate inside of each of the integrations' sub-folders in order to launch and deploy that particular integration. The current integrations supported with the google sheets as output include:
1. GradeScope - Containerized Cloud Deployment
2. PrairieLearn - Containerized Cloud Deployment
3. iClicker - Local Script



## Deployment Process for GradeScope and PrairieLearn

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



