from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
from datetime import timedelta
from django.utils.timezone import now

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
    exp = models.PositiveIntegerField(default=0)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        title_display = self.title[:50] if self.title and self.title.strip() else 'Без названия'
        description_display = self.description[:100] if self.description and self.description.strip() else 'Нет описания'
        return f"{title_display} - {description_display}"

    
    class Meta:
        ordering = ['-updated']


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    exp = models.IntegerField(default=0)
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
    protein = models.FloatField()
    fat = models.FloatField()
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
    protein_goal = models.FloatField(default=50)
    fat_goal = models.FloatField(default=70)
    carbs_goal = models.FloatField(default=260)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Nutrition Goals"


