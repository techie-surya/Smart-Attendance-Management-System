"""Production entrypoint for Smart Attendance API using Waitress or Gunicorn."""
import os
import sys
import logging 



sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src.config as config
from app import app, startup_cleanup

logger = logging.getLogger(__name__)

# Ensure directories exist
os.makedirs(config.DATASET_PATH, exist_ok=True)
os.makedirs(config.ENCODINGS_PATH, exist_ok=True)
os.makedirs(config.DATABASE_PATH, exist_ok=True)
os.makedirs(config.LOGS_PATH, exist_ok=True)
os.makedirs(config.REPORTS_PATH, exist_ok=True)

# Run startup cleanup when module is loaded (for gunicorn/waitress)
logger.info("Running startup cleanup...")
startup_cleanup()
logger.info("Startup cleanup complete")

# Export app for WSGI servers (gunicorn, waitress, etc.)
# Usage: gunicorn web.wsgi:app
# This ensures startup_cleanup runs before serving requests

if __name__ == "__main__":
    # For local development with waitress
    from waitress import serve
    serve(app, host=config.FLASK_HOST, port=config.FLASK_PORT)
