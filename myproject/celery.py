from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

app = Celery('myproject')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')



app = Celery('myproject')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Добавляем настройку для периодической задачи
app.conf.beat_schedule = {
    'update-task-deadline-daily': {
        'task': 'api.tasks.update_task_deadline',  # Путь к вашей задаче
        'schedule': crontab(minute=0, hour=0),  # Выполнение каждый день в 00:00
    },
}

app.autodiscover_tasks()
