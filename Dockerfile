FROM python:3.11-slim

RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5050
CMD ["sh", "-c", "gunicorn app:app --worker-class gevent --workers 1 --bind 0.0.0.0:${PORT:-5050} --timeout 120 --keep-alive 5 --log-level info"]
