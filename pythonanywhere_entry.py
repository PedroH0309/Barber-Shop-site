"""PythonAnywhere ASGI entrypoint for Precision Agenda's HTTPS web app.

The actual application and business logic remain in backend.app.
No credentials or customer data are stored in the repository.
"""
import os

# PythonAnywhere's supplied subdomain uses HTTPS. Require secure admin cookies.
os.environ.setdefault("COOKIE_SECURE", "1")
# Scheduled reminders require an independent, configured WhatsApp integration.
os.environ.setdefault("REMINDERS_ENABLED", "0")

from backend.app import app
