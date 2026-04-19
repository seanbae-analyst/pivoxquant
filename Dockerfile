FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \
    libgdk-pixbuf-2.0-0 libgdk-pixbuf2.0-common \
    libffi-dev libxml2 libxslt1.1 shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's bundled Chromium for Brag Card PNG rendering
# (services/artifacts/brag_card_service.py). Failure is tolerated — the
# service degrades gracefully to HTML-only preview, so a broken install
# must not block the whole image build.
RUN playwright install chromium --with-deps \
    || echo "WARNING: playwright install failed; Brag Card PNG will be skipped"

COPY . .

EXPOSE 5050
CMD ["sh", "-c", "gunicorn app:app --worker-class gevent --workers 1 --bind 0.0.0.0:${PORT:-5050} --timeout 120 --keep-alive 5 --log-level info"]
