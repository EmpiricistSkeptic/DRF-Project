from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
from datetime import timedelta
from django.utils.timezone import now
from django.utils import timezone

DIFFICULTY_CHOICES = [
    ('S', 'S'),
    ('A', 'A'),
    ('B', 'B'),
    ('C', 'C'),
    ('D', 'D'),
    ('E', 'E'),
]

def default_deadline():
    return now() + timedelta(hours=24)

class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.TextField()
    description = models.TextField(null=True, blank=True)
    deadline = models.DateTimeField(default=default_deadline)
    completed = models.BooleanField(default=False)
    difficulty = models.CharField(max_length=1, choices=DIFFICULTY_CHOICES, default='E')
    points = models.IntegerField(default=0)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        title_display = self.title[:50] if self.title and self.title.strip() else 'Без названия'
        description_display = self.description[:100] if self.description and self.description.strip() else 'Нет описания'
        return f"{title_display} - {description_display}"

    
    class Meta:
        ordering = ['-updated']


class Quest(models.Model):
    QUEST_TYPES = (
        ('DAILY', 'Ежедневный'),
        ('URGENT', 'Срочный'),
        ('MAIN', 'Основной'),
        ('CHALLENGE', 'Челлендж'),
    )
    QUEST_STATUS = (
        ('ACTIVE', 'Активен'),    
        ('COMPLETED', 'Выполнен'),   
        ('FAILED', 'Провален'),       
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quests')
    title = models.CharField(max_length=255, verbose_name="Название квеста")
    description = models.TextField(verbose_name="Описание/Цели")
    quest_type = models.CharField(max_length=20, choices=QUEST_TYPES, default='CHALLENGE', verbose_name="Тип квеста")
    status = models.CharField(max_length=20, choices=QUEST_STATUS, default='ACTIVE', verbose_name="Статус")
    reward_points = models.IntegerField(default=0, verbose_name="Награда XP")
    reward_other = models.CharField(max_length=255, blank=True, null=True, verbose_name="Другая награда (текст)")
    penalty_info = models.CharField(max_length=255, blank=True, null=True, verbose_name="Штраф (текст)")
    generated_at = models.DateTimeField(default=timezone.now, verbose_name="Время генерации")
    expires_at = models.DateTimeField(blank=True, null=True, verbose_name="Срок выполнения (для срочных)")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="Время выполнения")

    class Meta:
        verbose_name = "Квест (от ИИ)"
        verbose_name_plural = "Квесты (от ИИ)"
        ordering = ['-generated_at']

    def __str__(self):
        return f"[{self.get_quest_type_display()}] {self.title} ({self.user.username})"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    points = models.IntegerField(default=0)
    level = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_message')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.sender} to {self.recipient} at {self.timestamp}"
    

class Friendship(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendship_sender')
    friend = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendship_receiver')
    status = models.CharField(max_length=10, choices=[('PENDING', 'Pending'), ('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected'), ('FRIEND', 'Friend')], default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.friend} ({self.status})"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('friend_request', 'Friend Request'),
        ('message', 'Message'),
        ('task_deadline', 'Task Deadline'),
        ('friend_request_accepted', 'Friend Request Accepted'),
        ('friend_request_rejected', 'Friend Request Rejected')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    def __str__(self):
        return f"Notification for {self.user.username} - {self.notification_type}"
    

class Group(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    members = models.ManyToManyField(User, related_name='custom_groups_members')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class GroupMessage(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message in {self.group.name} by {self.sender.username}"


class PomodoroTimer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pomodoro_sessions')
    start_timer = models.DateTimeField(auto_now_add=True)
    duration_minutes = models.IntegerField(default=25)
    short_break_minutes = models.IntegerField(default=5)
    long_break_minutes = models.IntegerField(default=15)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Pomodoro for {self.user.username} - {self.duration_minutes} minutes"
    


class EducationalContent(models.Model):
    CATEGORY_CHOICES = [
        ('neuroscience', 'Neuroscience'),
        ('philosophy', 'Philosophy'),
        ('mindset', 'Mindset'),
        ('productivity', 'Productivity'),
    ]
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ConsumedCalories(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)
    weight = models.FloatField()
    calories = models.FloatField()
    proteins = models.FloatField()
    fats = models.FloatField()
    carbs = models.FloatField()
    consumed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.product_name} ({self.calories} kkal)'
    

class Achievement(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50)  

    def __str__(self):
        return self.title
    
class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    unlocked = models.BooleanField(default=False)
    unlocked_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.achievement.title}"

    

class UserNutritionGoal(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='nutrition_goal')
    calories_goal = models.FloatField(default=2000)
    proteins_goal = models.FloatField(default=50)
    fats_goal = models.FloatField(default=70)
    carbs_goal = models.FloatField(default=260)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Nutrition Goals"


class ChatHistory(models.Model):
    """
    Модель для хранения истории общения пользователя с ИИ-ассистентом.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE, 
        related_name='chat_history',
        verbose_name="Пользователь (Игрок)"
    )
    user_message = models.TextField(
        verbose_name="Сообщение пользователя"
    )
    ai_response = models.TextField(
        verbose_name="Ответ ИИ (Системы)"
    )
    prompt_sent = models.TextField(
        verbose_name="Промпт, отправленный ИИ",
        blank=True, 
        null=True
    )
    scenario = models.CharField(
        max_length=50,
        verbose_name="Определенный сценарий",
        blank=True, # Может быть пустым при ошибке определения
        null=True
    )
    timestamp = models.DateTimeField(
        default=timezone.now, # Автоматически устанавливаем время создания записи
        verbose_name="Время обмена"
    )
    error_occurred = models.BooleanField(
        default=False,
        verbose_name="Произошла ошибка"
    )
    error_message = models.TextField(
        verbose_name="Сообщение об ошибке",
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "Запись истории чата"
        verbose_name_plural = "История чата"
        ordering = ['-timestamp'] 

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.user.username}: {self.user_message[:50]}..."


