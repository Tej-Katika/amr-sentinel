FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/ingestion/requirements.txt
RUN pip install --no-cache-dir -r /app/ingestion/requirements.txt

COPY . /app/ingestion/

# /app is the package root; `ingestion` is the package, so relative imports
# (`from .models import ...`) inside ingestion/main.py resolve correctly.
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "ingestion.main:app", "--host", "0.0.0.0", "--port", "8000"]
