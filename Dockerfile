FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \
    libgdk-pixbuf-2.0-0 libgdk-pixbuf2.0-common \
    libglib2.0-0 libpangocairo-1.0-0 libharfbuzz0b libfribidi0 \
    fonts-noto-cjk fontconfig wget unzip ca-certificates \
    libffi-dev libxml2 libxslt1.1 shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# ── Pretendard font (PDF v3 디자인 의도, OFL 라이센스) ────────────────────
# Source: github.com/orioncactus/pretendard (Kil Hyung-jin, OFL 1.1).
# Required for v3 templates (Vantablack + Bronze + Playfair).
# Install BOTH static OTF + variable TTF — variable font carries richer
# language coverage metadata so fontconfig's `:lang=ko` filter picks it
# up (the static OTFs alone failed this filter on 2026-04-30).
# Plus an explicit fontconfig snippet that asserts Korean lang coverage.
RUN set -eux \
    && mkdir -p /tmp/pretendard-extract \
                /usr/share/fonts/opentype/pretendard \
                /usr/share/fonts/truetype/pretendard \
                /etc/fonts/conf.d \
    && cd /tmp \
    && wget --tries=3 --timeout=30 \
       -O pretendard.zip \
       https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip \
    && unzip pretendard.zip -d /tmp/pretendard-extract/ \
    && find /tmp/pretendard-extract/public/static -maxdepth 1 -name '*.otf' \
       -exec cp {} /usr/share/fonts/opentype/pretendard/ \; \
    && cp /tmp/pretendard-extract/public/variable/PretendardVariable.ttf \
          /usr/share/fonts/truetype/pretendard/ \
    && ls -la /usr/share/fonts/opentype/pretendard/ \
                /usr/share/fonts/truetype/pretendard/ \
    && rm -rf /tmp/pretendard.zip /tmp/pretendard-extract \
    && printf '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n<fontconfig>\n  <match target="scan">\n    <test name="family"><string>Pretendard</string></test>\n    <edit name="lang" mode="append"><string>ko</string></edit>\n  </match>\n  <match target="scan">\n    <test name="family"><string>Pretendard Variable</string></test>\n    <edit name="lang" mode="append"><string>ko</string></edit>\n  </match>\n</fontconfig>\n' > /etc/fonts/conf.d/99-pretendard-ko.conf \
    && fc-cache -f -v 2>&1 | tail -3 \
    && (fc-list | grep -i pretendard | head -5 \
        || (echo "FATAL: Pretendard not in fc-list after fc-cache" && exit 1))

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's bundled Chromium for Brag Card PNG rendering
# (services/artifacts/brag_card_service.py). Failure is tolerated — the
# service degrades gracefully to HTML-only preview, so a broken install
# must not block the whole image build.
RUN playwright install chromium --with-deps \
    || echo "WARNING: playwright install failed; Brag Card PNG will be skipped"

# ── Re-register Pretendard AFTER playwright (which can overwrite fc cache) ──
# playwright --with-deps apt-installs fonts that trigger fontconfig
# rebuild. Re-running fc-cache here ensures Pretendard is in the final
# system-wide fontconfig index. Fail-fast if Pretendard not found.
RUN set -eux \
    && fc-cache -f -v 2>&1 | tail -3 \
    && (fc-list | grep -i pretendard | head -3 \
        || (echo "FATAL: Pretendard missing from fc-list at runtime" \
            && ls -la /usr/share/fonts/opentype/pretendard/ \
            && exit 1))

COPY . .

# ── Journal Companion safety default ────────────────────────────────────────
# The Personal Journal Companion (services/agents/) is in Closed Beta and
# MUST NOT reach paying users until legal counsel signs off on
# reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6. This env default keeps
# it OFF even if the code is deployed. To activate in staging:
#   railway variables set AGENT_ENABLED=1
# Production override requires CEO approval + logged kill-switch audit.
ENV AGENT_ENABLED=0

# ── Alpaca kill switch ──────────────────────────────────────────────────────
# Alpaca broker integration is disabled by default to remove the legal risk
# tied to Alpaca's "My Data" license (US broker-dealer regulation). KIS
# (한국투자증권) is the supported broker. Do NOT flip this to 1 in production
# without legal sign-off. Consumed by:
#   - routes/broker_oauth.py (/api/broker/alpaca/* endpoints → 503)
#   - autotrader.py, data_fetcher.py, realtime_service.py, daytrade_service.py
ENV ALPACA_ENABLED=0

EXPOSE 5050

# ── HEALTHCHECK (Railway + Docker probes) ───────────────────────────────────
# Railway already pings railway.toml's healthcheckPath, but a Dockerfile-level
# HEALTHCHECK lets `docker ps` / local compose / any non-Railway runtime see
# container health too. start-period=60s covers the gunicorn boot + Pretendard
# fc-cache rebuild + alembic runtime migrations (services/launch_prep.py).
# Uses `python -c` instead of curl to avoid adding the curl apt package.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request,sys; \
url='http://127.0.0.1:'+os.environ.get('PORT','5050')+'/api/health'; \
r=urllib.request.urlopen(url,timeout=5); sys.exit(0 if r.status==200 else 1)" \
  || exit 1

CMD ["sh", "-c", "gunicorn app:app --worker-class gevent --workers 1 --bind 0.0.0.0:${PORT:-5050} --timeout 120 --keep-alive 5 --log-level info"]
