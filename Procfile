release: flask db upgrade || echo "migration skipped (non-fatal)"
web: gunicorn app:app --worker-class gevent --workers 1 --bind 0.0.0.0:$PORT --timeout 120 --keep-alive 5 --log-level info
