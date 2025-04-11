# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory to /gradescope
WORKDIR /gradescope

# Set environment variables
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

# Copy the current directory contents into the container at /gradescope
COPY . /gradescope

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Allow the cron to execute the script as an executable
# chmod: Changes to the file permissions
# u: Refers to the "user" (the owner of the file).
# +x: Adds execute permission for the specified group (u here).
RUN chmod u+x gradescope_to_spreadsheet.py

# Set the entrypoint to run the script
ENTRYPOINT ["/gradescope/gradescope_to_spreadsheet.py"]