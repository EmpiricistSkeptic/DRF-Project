from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Настройка переменной окружения для Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# Создаём экземпляр приложения Celery
app = Celery('myproject')

# Конфигурируем Celery с настройками из Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматическое обнаружение задач
app.autodiscover_tasks()

# Определяем периодическую задачу
app.conf.beat_schedule = {
    'update-task-deadline-daily': {
        'task': 'api.tasks.update_task_deadline',  # Путь к вашей задаче
        'schedule': crontab(minute=0, hour=0),  # Выполнение каждый день в 00:00
    },
}

# Пример отладочной задачи
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


from celery.schedules import crontab
from celery import Celery
import os
from __future__ import absolute_import, unicode_literals


os.environ.setdefault('DJANGO-SETTINGS-MODULE', 'myproject.settings')

app = Celery('myproject')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'update-task-deadline': {
        'task': 'api.tasks.check_task_deadline',
        'schedule': crontab(minute=0, hour=0)
    }
}
