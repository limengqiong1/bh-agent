# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# WeChat Mini-Program Cloud Hosting listens on port 8081 (as configured in console)
ENV AGENT_PORT=8081
ENV AGENT_HOST=0.0.0.0
ENV AGENT_RELOAD=0

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8081
EXPOSE 8081

# Run main.py
CMD ["python", "main.py"]
