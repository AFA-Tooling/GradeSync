# GradeSync

### About

GradeSync is a backend microservice that integrates with assessment platforms to fetch student grades and facilitate management of post-semester submissions. GradeSync enables students to submit coursework after the term ends and view their updated grades on the GradeView dashboard. GradeSync automates gradebook updates, eliminating the need for manual instructor intervention.

### Pre-setup 
1. Download the Docker Desktop application
2. In the terminal, run `docker --version` to ensure Docker is correctly installed.
3. In `/api`, create a `.env` file with the `GRADESCOPE_EMAIL`, `GRADESCOPE_PASSWORD` fields you use to log into the CS10 Fall 2024 test GradeScope. Additionally, include the `PL_API_TOKEN` field you use to log into PraireLearn and include `SERVICE_ACCOUNT_CREDENTIALS` with the JSON content for a Google Service Account obtained through GCP. This is how the application is authenticated automatically.
4. Set the following constants
- **CS_10_GS_COURSE_ID**: The GS course ID is the final component of the URL on the GradeScope course homepage: `https://www.gradescope.com/courses/[COURSE_ID]`
- **CS_10_PL_COURSE_ID** The GS course ID is the final component of the URL on the GradeScope course homepage: `https://us.prairielearn.com/pl/course_instance/[COURSE_ID]`
### How to Launch the App

1. Open the Docker desktop application.
2. In the terminal, navigate to the `/gradesync` directory of this project, which is the root directory.
3. Build the Docker image using `docker-compose build`.
4. Start the application with `docker-compose up`.
5. Confirm the application is running by opening [http://localhost:8000/](http://localhost:8000/) on a browser.
6. Test endpoints with a tool like ThunderClient or Postman.
- Go to VSCode extensions, and add "ThunderClient" to your extensions.
- Click "New Request" to test the API endpoints.
- Also, create test cases in `api/tests/test_app.py`.
7. When you are finished, run `docker-compose down` or press CTRL+C to stop the server.
