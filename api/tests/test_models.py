# tests.py
from django.test import TestCase
from django.utils import timezone
from api.models import Task
from django.contrib.auth.models import User
from datetime import timedelta

class TaskModelTest(TestCase):
    
    def setUp(self):
        # Этот метод вызывается перед каждым тестом.
        # Создаем пользователя для связи с задачами
        self.user = User.objects.create(username='testuser', password='password')
        
        # Создаем объект Task, чтобы проверять его работу
        self.task = Task.objects.create(
            user=self.user,
            title="Test Task",
            description="This is a test task.",
            deadline=timezone.now() + timedelta(hours=48),  # Устанавливаем дедлайн через 48 часов
            completed=False
        )
    
    def test_task_creation(self):
        # Проверяем, что задача была создана корректно
        self.assertEqual(self.task.title, "Test Task")  # Проверяем, что title правильный
        self.assertEqual(self.task.description, "This is a test task.")  # Проверяем описание
        self.assertFalse(self.task.completed)  # Проверяем, что задача не завершена
        self.assertTrue(self.task.deadline > timezone.now())  # Дедлайн должен быть в будущем
    
    def test_str_method(self):
        # Проверка __str__ метода модели
        self.assertEqual(str(self.task), "Test Task - This is a test task.")  # Проверяем корректность строкового представления задачи

    def test_default_values(self):
        # Проверяем значения по умолчанию
        task = Task.objects.create(user=self.user, title="Another Task")
        self.assertEqual(task.completed, False)  # Убедимся, что значение completed по умолчанию - False
        self.assertIsNotNone(task.created)  # Проверяем, что поле created не пустое
        self.assertIsNotNone(task.updated)  # Проверяем, что поле updated не пустое
    
    def test_deadline_in_future(self):
        # Проверка, что deadline всегда в будущем
        task = Task.objects.create(user=self.user, title="Future Deadline Task", deadline=timezone.now() + timedelta(days=1))
        self.assertGreater(task.deadline, timezone.now())  # Убедимся, что deadline в будущем

    def test_task_association_with_user(self):
        # Проверка, что задача привязана к пользователю
        self.assertEqual(self.task.user.username, "testuser")  # Проверяем, что задача связана с правильным пользователем

