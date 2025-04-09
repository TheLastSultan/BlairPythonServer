# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Run the application using Uvicorn. Adjust "main:app" if your FastAPI app is named differently.
CMD ["uvicorn", "agent.recruiter_agent:app", "--host", "0.0.0.0", "--port", "80"]
