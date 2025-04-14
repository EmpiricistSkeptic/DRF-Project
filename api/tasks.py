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
        user_profile.points = max(0, user_profile.points - 150)
        user_profile.save()


