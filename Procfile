release: flask db upgrade 2>&1 | tee /tmp/alembic.log; if [ "${PIPESTATUS[0]}" != "0" ]; then echo "ALEMBIC_UPGRADE_FAILED — boot will fall back to _do_migrations() (runtime ADD COLUMN guards in app.py). Inspect /tmp/alembic.log for root cause."; fi
web: gunicorn app:app --worker-class gevent --workers 1 --bind 0.0.0.0:$PORT --timeout 120 --keep-alive 5 --log-level info
