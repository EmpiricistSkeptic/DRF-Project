from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
from datetime import timedelta
from django.utils.timezone import now
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

DIFFICULTY_CHOICES = [
    ('S', 'S'),
    ('A', 'A'),
    ('B', 'B'),
    ('C', 'C'),
    ('D', 'D'),
    ('E', 'E'),
]


class Category(models.Model):
    name = models.CharFielf(max_length=50)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='categories/', blank=True)
    
    def __str__(self):
        return self.name


class UnitType(models.Model):
    name = models.CharField(max_length=50)  # час., мин., стр., сл., уд.
    symbol = models.CharField(max_length=10)  
    
    def __str__(self):
        return self.name


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
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    unit_type = models.ForeignKey(UnitType, on_delete=models.SET_NULL, null=True)
    unit_amount = models.IntegerField(default=0)

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



class Achievement(models.Model):
    TIER_CHOICES = [
        ('BRONZE', 'Bronze'),
        ('SILVER', 'Silver'),
        ('GOLD', 'Gold'),
        ('PLATINUM', 'Platinium'),
        ('DIAMOND', 'Diamond'),
    ]


    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(upload_to='achievements/')
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    unit_type = models.ForeignKey('UnitType', on_delete=models.CASCADE)

    bronze_requirement = models.IntegerField(default=10)
    silver_requirement = models.IntegerField(default=50)
    gold_requirement = models.IntegerField(default=100)
    platinum_requirement = models.IntegerField(default=500)
    diamond_requirement = models.IntegerField(default=1000)

    def __str__(self):
        return self.title
    
    
class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    current_progress = models.IntegerField(default=0)
    current_tier = models.CharField(max_length=10, choices=Achievement.TIER_CHOICES, default='BRONZE')
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'achievement')


    def __str__(self):
        return f"{self.user.username} - {self.achievement.name}"

    
    def update_progeress(self, value):
        self.current_progress += value

        if self.current_progress >= self.achievement.diamond_requirement:
            self.current_tier = 'DIAMOND'
            if not self.completed:
                self.completed = True
                self.completed_at = timezone.now()
        elif self.current_progress >= self.achievement.platinum_requirement:
            self.current_tier = 'PLATINUM'
        elif self.current_progress >= self.achievement.gold_requirement:
            self.current_tier = 'GOLD'
        elif self.current_progress >= self.achievement.silver_requirement:
            self.current_tier = 'SILVER'
        else:
            self.current_tier = 'BRONZE'
        self.save()


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


    
class UserHabit(models.Model):
    """Модель привычки пользователя."""
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='habits' # Добавлено для удобных обратных запросов user.habits.all()
    )
    title = models.CharField(
        max_length=100, # Немного увеличил длину для гибкости
        verbose_name="Название привычки" # Добавлено для админки и форм
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Описание"
    )
    streak = models.PositiveIntegerField(
        default=0, 
        verbose_name="Текущий стрик (дней)"
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name="Активна",
        help_text="Отметьте, если привычка активна (используется для мягкого удаления)"
    )
    last_tracked = models.DateField(
        null=True, 
        blank=True, # Дата может отсутствовать, если привычка никогда не отмечалась
        verbose_name="Дата последней отметки"
    )
    icon = models.CharField(
        max_length=50, # Установлена адекватная длина
        blank=True, 
        null=True, 
        default='list-ul',
        verbose_name="Иконка"
    )
    frequency = models.CharField( # Добавил поле частоты, т.к. оно есть во фронтенде
        max_length=20, 
        default='Daily', 
        choices=[('Daily', 'Ежедневно'), ('Weekly', 'Еженедельно'), ('Monthly', 'Ежемесячно')], # Пример выбора
        verbose_name="Частота"
    )
    notification_enabled = models.BooleanField( # Добавил поле уведомлений
        default=False, 
        verbose_name="Уведомления включены"
    )
    
    # Метаданные времени
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Привычка пользователя"
        verbose_name_plural = "Привычки пользователей"
        ordering = ['-created_at'] # Сортировка по умолчанию

    def track_habit(self):
        """
        Отмечает привычку как выполненную СЕГОДНЯ.
        Обновляет стрик и дату последней отметки.
        Возвращает True, если отметка прошла успешно (т.е. не была уже отмечена сегодня).
        Возвращает False, если привычка уже была отмечена сегодня.
        """
        today = timezone.now().date()

        # --- Проверка: Не была ли уже отмечена сегодня? ---
        # Эту проверку ЛУЧШЕ делать в View перед вызовом этого метода,
        # но для надежности можно оставить и здесь.
        if self.last_tracked == today:
            logger.warning(f"Habit '{self.title}' (ID: {self.id}) already tracked today ({today}).")
            return False # Сигнализируем, что действие не требуется

        # --- Логика обновления стрика ---
        if self.last_tracked: # Если привычка уже отмечалась ранее
            if today == self.last_tracked + timedelta(days=1):
                # Продолжаем стрик
                self.streak += 1
                logger.info(f"Habit '{self.title}' (ID: {self.id}) streak continued: {self.streak} days.")
            elif today > self.last_tracked + timedelta(days=1):
                # Был пропуск, сбрасываем стрик до 1
                self.streak = 1
                logger.info(f"Habit '{self.title}' (ID: {self.id}) streak reset to 1 after a gap.")
            # else: today < self.last_tracked + timedelta(days=1) - это случай отметки в прошлом или дубль (обработан выше), стрик не меняем
        else:
            # Это самая первая отметка привычки
            self.streak = 1
            logger.info(f"Habit '{self.title}' (ID: {self.id}) tracked for the first time. Streak: 1.")

        # --- Обновление даты последней отметки ---
        self.last_tracked = today
        
        # --- Сохранение ---
        # Сохраняем только измененные поля для эффективности и чтобы не затереть `updated_at` без нужды
        self.save(update_fields=['streak', 'last_tracked', 'updated_at']) 
        
        return True # Успешная отметка

    def __str__(self):
        return f"{self.title} ({self.user.get_username()})"
    

    






    

