import os
from celery import Celery

# Tell Celery which Django settings file to use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wifiportal.settings')

# Create the Celery application
app = Celery('wifiportal')

# Read Celery configuration from Django settings
# All Celery settings in settings.py must start with CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover tasks.py files in all installed apps
app.autodiscover_tasks()