from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

app = Celery('myproject')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'update-task-deadline-daily': {
        'task': 'api.tasks.check_task_deadline', 
        'schedule': crontab(minute=0, hour=0), 
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
