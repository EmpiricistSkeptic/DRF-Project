# tests.py
from django.test import TestCase
from django.utils import timezone
from api.models import Task, Profile
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


class ProfileModelTest(TestCase):

    def setUp(self):
        # Create a user instance
        self.user = User.objects.create_user(username="testuser", password="testpassword")

    def test_profile_creation(self):
        """Test that the profile is created when a user is created"""
        profile = Profile.objects.create(user=self.user)

        # Check if the profile is created
        self.assertIsInstance(profile, Profile)
        self.assertEqual(profile.user.username, self.user.username)
        self.assertEqual(profile.points, 0)  # Default value
        self.assertEqual(profile.level, 1)   # Default value

    def test_profile_str_method(self):
        """Test the __str__ method of the Profile model"""
        profile = Profile.objects.create(user=self.user)

        # Check if the string representation of the profile is correct
        self.assertEqual(str(profile), f"{self.user.username}'s Profile")

    def test_bio_field(self):
        """Test that bio field is blank by default"""
        profile = Profile.objects.create(user=self.user)
        self.assertEqual(profile.bio, None)

    def test_avatar_field(self):
        """Test that avatar field is blank by default"""
        profile = Profile.objects.create(user=self.user)
        self.assertEqual(profile.avatar, None)

    def test_points_field(self):
        """Test that points field defaults to 0"""
        profile = Profile.objects.create(user=self.user)
        self.assertEqual(profile.points, 0)

    def test_level_field(self):
        """Test that level field defaults to 1"""
        profile = Profile.objects.create(user=self.user)
        self.assertEqual(profile.level, 1)

    def test_profile_update(self):
        """Test updating profile fields"""
        profile = Profile.objects.create(user=self.user)
        profile.bio = "Updated bio"
        profile.points = 100
        profile.level = 2
        profile.save()

        # Fetch the updated profile
        updated_profile = Profile.objects.get(user=self.user)
        self.assertEqual(updated_profile.bio, "Updated bio")
        self.assertEqual(updated_profile.points, 100)
        self.assertEqual(updated_profile.level, 2)


