FROM python:3.11-slim

WORKDIR /app

# Optional: allow forcing a fresh dependency install by bumping this arg
ARG CACHE_BUST=1
RUN echo "CACHE_BUST=$CACHE_BUST"

COPY requirements.txt .
# Upgrade pip to ensure latest wheel support, then install deps
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Create static directory if it doesn't exist
RUN mkdir -p static

# Expose the port that the application will run on
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
