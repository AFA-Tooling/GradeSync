# Base image with Python and cron
FROM python:3.9-slim

# Set up work directory
WORKDIR /app

# Copy the requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the Python script to the Docker container
COPY gradescope_to_spreadsheet.py .

# Install cron
RUN apt-get update && apt-get install -y cron

# Add the cron job
COPY crontab /etc/cron.d/grade_cron

# Grant execution rights to the cron job
RUN chmod 0644 /etc/cron.d/grade_cron

# Create a log file to be able to inspect cron job execution
RUN touch /var/log/cron.log

# Run the command on container startup
CMD cron && tail -f /var/log/cron.log
