FROM python:3.11-slim

# 2026-09-01 — image reduced to what the deployed app actually needs.
#
# This image used to apt-install the full Pango / Cairo / gdk-pixbuf / HarfBuzz
# stack, download and fontconfig-register the Pretendard font family (twice, to
# survive a cache rebuild), and `playwright install chromium --with-deps`. All
# of that existed for server-side rendering that no longer happens:
#
#   * WeasyPrint (the font/Cairo stack) rendered the 18 artefact PDFs — the
#     artefact tree is deleted. The only remaining importer is
#     scripts/legal/build_agenda_pdf.py, which a human runs from the local
#     venv, never in this container.
#   * Playwright's Chromium rendered the Brag Card PNG — also deleted. Its only
#     remaining importer is scripts/caus_daily_sweep.py, likewise local.
#   * Pretendard was installed as a SYSTEM font for those PDFs. The two places
#     the app still names it (routes/email_preferences.py, services/email_token.py)
#     put it in an email CSS font-family stack, which the recipient's mail
#     client resolves — nothing on this host reads it.
#
# Verified before removal: no module under routes/, services/, models/ or
# app.py imports weasyprint or playwright, at module level or lazily inside a
# function. requirements.txt still lists both so a local venv keeps working for
# those two scripts; neither is imported by anything this container runs.
#
# Net effect: roughly a gigabyte less image and several minutes off every build
# — which is the difference that matters when standing this up on a new host.

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    ca-certificates \
    && rm -r /var/lib/apt/lists

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ── Alpaca data-fallback kill switch ─────────────────────────────────────────
# The user-facing Alpaca broker integration was fully removed 2026-05-27. This
# flag now only gates an internal US-price FALLBACK adapter
# (services/data/alpaca_market_adapter.py); disabled by default so US prices
# come from FMP exclusively. KIS (한국투자증권) is the supported broker. Do NOT
# flip this to 1 in production without legal sign-off (would require an Alpaca
# commercial data license).
ENV ALPACA_ENABLED=0

EXPOSE 5050

# ── HEALTHCHECK (container probes) ──────────────────────────────────────────
# A Dockerfile-level HEALTHCHECK lets `docker ps` / compose / any runtime see
# container health, independent of whatever the host platform probes. The
# start-period covers gunicorn boot plus the runtime migrations in
# services/launch_prep.py. Uses `python -c` rather than curl so the image does
# not need the curl package.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request,sys; \
url='http://127.0.0.1:'+os.environ.get('PORT','5050')+'/api/health'; \
r=urllib.request.urlopen(url,timeout=5); sys.exit(0 if r.status==200 else 1)" \
  || exit 1

CMD ["sh", "-c", "gunicorn app:app --worker-class gevent --workers 1 --bind 0.0.0.0:${PORT:-5050} --timeout 120 --keep-alive 5 --log-level info"]
