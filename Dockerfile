# FROM python:3.11-slim
# RUN apt-get update && apt-get install -y curl postgresql-client && rm -rf /var/lib/apt/lists/*
# WORKDIR /app
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt
# COPY backend /app/backend
# CMD ["bash"]

FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl postgresql-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY app /app/app

# Expose port
EXPOSE 8000

# Start the FastAPI application
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]