FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for compiling certain Python packages and running MCP servers via npx
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Inside your Dockerfile
RUN pip install google-adk pandas openpyxl excel-mcp-server
# Copy the rest of your application code into the container
COPY . .

# Document the ports your services run on
EXPOSE 8000
EXPOSE 8005