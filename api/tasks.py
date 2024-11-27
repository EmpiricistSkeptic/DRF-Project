from celery import shared_task
from django.utils import timezone
from .models import Task
from datetime import timedelta

@shared_task
def check_task_deadline():
    now = timezone.now()
    overdue_tasks = Task.objects.filter(completed=False, deadline__lt=now)
    for task in overdue_tasks:
        user_profile = task.user.profile
        user_profile.points = max(0, user_profile.points - 10)
        user_profile.save()


@shared_task
def update_task_deadline():
    """
    Эта задача обновляет поле `deadline` для всех незавершённых задач,
    устанавливая его на 24 часа с момента обновления.
    """
    tasks = Task.objects.filter(completed=False)  # Получаем все незавершённые задачи
    for task in tasks:
        task.deadline = timezone.now() + timedelta(hours=24)  # Устанавливаем срок на 24 часа с момента обновления
        task.save()

    completed_tasks = Task.objects.filter(completed=True)
    for task in completed_tasks:
        task.deadline = timezone.now() + timedelta(hours=24)  # Устанавливаем новый срок на 24 часа
        task.save()

