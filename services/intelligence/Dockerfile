FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc librdkafka-dev g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/intelligence/requirements.txt
RUN pip install --no-cache-dir -r /app/intelligence/requirements.txt

COPY . /app/intelligence/

# /app is the package root; `intelligence` is the package, so relative imports
# inside the source tree (`from ..breakpoints.aware import ...`) resolve correctly,
# and consumers/classification_consumer.py's `..` goes up to `intelligence`.
ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "intelligence.main:app", "--host", "0.0.0.0", "--port", "8000"]
