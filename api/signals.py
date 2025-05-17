from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, Achievement, UserAchievement, Task
from .services.achievement_service import AchievementService


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()



@receiver(post_save, sender=User)
def create_user_achievements(sender, instance, created, **kwargs):
    """
    Создание начальных достижений для нового пользователя
    """
    if created:
        AchievementService.register_user_achievements(instance)

@receiver(post_save, sender=Task)
def update_achievements_on_task_completion(sender, instance, **kwargs):
    """
    Обновление прогресса достижений при выполнении задачи
    """
    if instance.completed: 
        AchievementService.update_achievements_on_task_completion(instance.user, instance)




        