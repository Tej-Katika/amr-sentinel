FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/agentic/requirements.txt
RUN pip install --no-cache-dir -r /app/agentic/requirements.txt

COPY . /app/agentic/

# /app is the package root; `agentic` is the package.
ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "agentic.main:app", "--host", "0.0.0.0", "--port", "8000"]
