from django.test import TestCase
from django.utils import timezone
from api.models import Task, Profile, Message, Friendship, Notification, Group, GroupMessage, PomodoroTimer, EducationalContent, ConsumedCalories
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


class MessageModelTest(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username="sender", password="password")
        self.recipient = User.objects.create_user(username="recipient", password="password")
        self.message_content = "This is a test message"


    def test_message_creation(self):
        message = Message.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            content=self.message_content
        )

        self.assertEqual(message.sender, self.sender)
        self.assertEqual(message.recipient, self.recipient)
        self.assertEqual(message.content, self.message_content)
        self.assertFalse(message.is_read)
        self.assertIsNotNone(message.timestamp)


    def test_str_method(self):
        message = Message.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            content=self.message_content
        )
        expected_str = f"Message from {self.sender} to {self.recipient} at {message.timestamp}"
        self.assertEqual(str(message), expected_str)


    def test_mark_message_as_read(self):
        message = Message.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            content=self.message_content
        )
        self.assertFalse(message.is_read)
        message.is_read = True
        message.save()

        self.assertTrue(message.is_read)


class FriendshipModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='password')
        self.user2 = User.objects.create_user(username='user2', password='password')

    def test_friendship_creation(self):
        friendship = Friendship.objects.create(
            user=self.user1,
            friend=self.user2,
            status="PENDING"
        )
        self.assertEqual(friendship.user, self.user1)
        self.assertEqual(friendship.friend, self.user2)
        self.assertEqual(friendship.status, "PENDING")
        self.assertIsNotNone(friendship.created_at)

    def test_str_method(self):
        friendship = Friendship.objects.create(
            user=self.user1,
            friend=self.user2,
            status='PENDING'
        )
        expected_str = f"{self.user1} - {self.user2} (PENDING)"
        self.assertEqual(str(friendship), expected_str)

    
    def test_friendship_status_choices(self):
        friendship_pending = Friendship.objects.create(
            user=self.user1,
            friend=self.user2,
            status='PENDING'
        )
        self.assertEqual(friendship_pending.status, "PENDING")

        friendship_accepted = Friendship.objects.create(
            user=self.user1,
            friend=self.user2,
            status='ACCEPTED'
        )
        self.assertEqual(friendship_accepted.status, "ACCEPTED")

        friendship_rejected = Friendship.objects.create(
            user=self.user1,
            friend=self.user2,
            status='REJECTED'
        )
        self.assertEqual(friendship_rejected.status, "REJECTED")

        friendship_friend = Friendship.objects.create(
            user=self.user1,
            friend=self.user2,
            status='FRIEND'
        )
        self.assertEqual(friendship_friend.status, "FRIEND")

    def test_default_status(self):
        friendship = Friendship.objects.create(
            user=self.user1,
            friend=self.user2
        )
        self.assertEqual(friendship.status, "PENDING")


class NotificationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

    def test_notification_creation(self):
        notification = Notification.objects.create(
            user=self.user,
            notification_type='friend_request',
            message='You have a friend request.',
            is_read=False
        )

        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.notification_type, 'friend_request')
        self.assertEqual(notification.message, 'You have a friend request')
        self.assertFalse(notification.is_read)
        self.assertIsNotNone(notification.created_at)

    def test_str_method(self):
        notification = Notification.objects.create(
            user=self.user,
            notification_type='message',
            message='You have a new message.',
            is_read=False
        )
        expected_str = f"Notification for {self.user.username}"
        self.assertEqual(str(notification), expected_str)

    def test_notification_types(self):
        notification_friend_request = Notification.objects.create(
            user=self.user,
            notification_type='friend_request',
            message='You have a new friend request.',
            is_read=False
        )
        self.assertEqual(notification_friend_request.notification_type, 'friend_request')

        notification_message = Notification.objects.create(
            user=self.user,
            notification_type='message',
            message='You have a new message.',
            is_read=False
        )
        self.assertEqual(notification_message.notification_type, 'message')

        notification_task_deadline = Notification.objects.create(
            user=self.user,
            notification_type='task_deadline',
            message='A task deadline is approaching.',
            is_read=False
        )
        self.assertEqual(notification_task_deadline.notification_type, 'task_deadline')

        notification_friend_request_accepted = Notification.objects.create(
            user=self.user,
            notification_type='friend_request_accepted',
            message='Your friend request was accepted.',
            is_read=False
        )
        self.assertEqual(notification_friend_request_accepted.notification_type, 'friend_request_accepted')

        notification_friend_request_rejected = Notification.objects.create(
            user=self.user,
            notification_type='friend_request_rejected',
            message='Your friend request was rejected.',
            is_read=False
        )
        self.assertEqual(notification_friend_request_rejected.notification_type, 'friend_request_rejected')

def test_default_is_read(self):
    notification = Notification.objects.create(
        user=self.user,
        notification_type='friend_request',
        message='You have a new friend request',
    )
    self.assertFalse(notification.is_read)


def test_mark_notification_as_read(self):
    notification = Notification.objects.create(
            user=self.user,
            notification_type='message',
            message='You have a new message.',
            is_read=False
        )
    self.assertFalse(notification.is_read)

    notification.is_read = True
    notification.save()

    self.assertTrue(notification.is_read)


class GroupModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='password')
        self.user2 = User.objects.create_user(username='user2', password='password')
        self.user3 = User.objects.create_user(username='user3', password='password')

    def test_group_creation(self):
        group = Group.objects.create(
            name='Test group',
            description='This is a test group',
            created_by=self.user1
        )

        self.assertEqual(group.name, 'Test group')
        self.assertEqual(group.description, 'This is a test group')
        self.assertEqual(group.created, self.user1)
        self.assertIsNotNone(group.created_at)
        self.assertEqual(group.members.count(), 0)

    def test_str_method(self):
        group = Group.objects.create(
            name='Test Group',
            description='This is a test group.',
            created_by=self.user1
        )
        self.assertEqual(str(group), 'Test group')

    def test_add_members(self):
        group = Group.objects.create(
            name='Test Group',
            description='This is a test group.',
            created_by=self.user1
        )  
        self.assertEqual(group.members.count(), 0)
        group.members.add(self.user2, self.user3)
        self.assertEqual(group.members.count(), 2)
        self.assertTrue(self.user2 in group.members.all())
        self.assertTrue(self.user3 in group.members.all())

    def test_remove_members(self):
        group = Group.objects.create(
            name='Test Group',
            description='This is a test group.',
            created_by=self.user1
        )
        group.members.add(self.user2, self.user3)
        group.members.remove(self.user2)

        self.assertEqual(group.members.count(), 1)
        self.assertFalse(self.user2 in group.members.all())
        self.assertTrue(self.user3 in group.members.all())

    def test_group_has_creator(self):
        group = Group.objects.create(
            name='Test Group',
            description='This is a test group.',
            created_by=self.user1
        )
        self.assertEqual(group.created_by, self.user1)

    def test_group_default_member_count(self):
        group = Group.objects.create(
            name='Test Group',
            description='This is a test group.',
            created_by=self.user1
        )
        self.assertEqual(group.members.count(), 1)


class GroupMessageModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='password')
        self.user2 = User.objects.create_user(username='user2', password='password')
        self.user3 = User.objects.create_user(username='user3', password='password')

        self.group = Group.objects.create(
            name='Test Group',
            description='This is a test group.',
            created_by=self.user1
        )
        self.group.members.add(self.user1, self.user2)

    def test_group_message_creation(self):
        message = GroupMessage.objects.create(
            group=self.group,
            sender=self.user1,
            content='This is a test message.'
        )
        self.assertEqual(message.group, self.group)
        self.assertEqual(message.sender, self.user1)
        self.assertEqual(message.content, 'This is a test message')
        self.assertIsNotNone(message.created_at)

    def test_str_method(self):
        message = GroupMessage.objects.create(
            group=self.group,
            sender=self.user1,
            content='This is a test message.'
        )
        expected_str = f"Message in {self.group.name} by {self.user1.username}"
        self.assertEqual(str(message), expected_str)

    def test_message_association_with_group_and_sender(self):
        message = GroupMessage.objects.create(
            group=self.group,
            sender=self.user2,
            content='Another test message.'
        )
        self.assertEqual(message.group, self.group)
        self.assertEqual(message.sender, self.user2)

    def test_message_is_stored_in_group(self):
        message = GroupMessage.objects.create(
            group=self.group,
            sender=self.user1,
            content='This is a test message.'
        )
        self.assertIn(message, self.group.messages.all())

    def test_created_at_automatic(self):
        message = GroupMessage.objects.create(
            group=self.group,
            sender=self.user1,
            content='This is a test message.'
        )
        self.assertIsNotNone(message.created_at)

    def test_multiple_messages_in_group(self):
        message1 = GroupMessage.objects.create(
            group=self.group,
            sender=self.user1,
            content='First test message.'
        )
        message2 = GroupMessage.objects.create(
            group=self.group,
            sender=self.user2,
            content='Second test message.'
        )
        self.assertEqual(self.group.messages.count(), 2)
        self.assertIn(message1, self.group.messages.all())
        self.assertIn(message2, self.group.messages.all())


class PomodoroTimerModelTest(TestCase):
    def setUp(self):
        self.user = self.user = User.objects.create_user(username='testuser', password='password')

    def test_pomodoro_timer_creation(self):
        pomodoro = PomodoroTimer.objects.create(
            user=self.user,
            duration_minutes=25,
            short_break_minutes=5,
            long_break_minutes=15,
            is_completed=False
        )
        self.assertEqual(pomodoro.user, self.user)
        self.assertEqual(pomodoro.duration_minutes, 25)
        self.assertEqual(pomodoro.short_break_minutes, 5)
        self.assertEqual(pomodoro.long_break_minutes, 15)
        self.assertFalse(pomodoro.is_completed)
        self.assertIsNotNone(pomodoro.start_time)

    def test_str_method(self):
        pomodoro = PomodoroTimer.objects.create(
            user=self.user
        )
        self.assertEqual(pomodoro.duration_minutes, 25)
        self.assertEqual(pomodoro.short_break_minutes, 5)
        self.assertEqual(pomodoro.long_break_minutes, 15)

    def test_is_completed_field(self):
        pomodoro = PomodoroTimer.objects.create(
            user=self.user,
            is_completed=False
        )
        self.assertFalse(pomodoro.is_completed)
        pomodoro.is_completed = True
        pomodoro.save()
        self.assertTrue(pomodoro.is_completed)

    def test_pomodoro_session_start_time(self):
        pomodoro = PomodoroTimer.objects.create(
            user=self.user
        )
        self.assertIsNotNone(pomodoro.start_time)

    def test_multiple_pomodoro_sessions(self):

        pomodoro1 = PomodoroTimer.objects.create(
            user=self.user,
            duration_minutes=25
        )
        pomodoro2 = PomodoroTimer.objects.create(
            user=self.user,
            duration_minutes=30
        )
        self.assertEqual(PomodoroTimer.objects.filter(user=self.user).count(), 2)
        self.assertIn(pomodoro1, self.user.pomodoro_sessions.all())
        self.assertIn(pomodoro2, self.user.pomodoro_sessions.all())

class EducationalContentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
    
    def test_educational_content_creation(self):
        content = EducationalContent.objects.create(
            title='Introduction to Neuroscience',
            content='Neuroscience is the study of the brain...',
            category='neuroscience'
        )
        self.assertEqual(content.title, 'Introduction to Neuroscience')
        self.assertEqual(content.content, 'Neuroscience is the study of the brain...')
        self.assertEqual(content.category, 'neuroscience')
        self.assertIsNotNone(content.created_at)

    def test_str_method(self):
        content = EducationalContent.objects.create(
            title='Introduction to Neuroscience',
            content='Neuroscience is the study of the brain...',
            category='neuroscience'
        )
        self.assertEqual(str(content), 'Introduction to Neuroscience')

    def test_category_choices(self):
        content1 = EducationalContent.objects.create(
            title='Neuroscience Basics',
            content='Neuroscience is the study of the brain...',
            category='neuroscience'
        )
        self.assertEqual(content1.category, 'neuroscience')

        content2 = EducationalContent.objects.create(
            title='Philosophy of Mind',
            content='Philosophy is the study of knowledge...',
            category='philosophy'
        )
        self.assertEqual(content2.category, 'philosophy')

        content3 = EducationalContent.objects.create(
            title='Productivity Hacks',
            content='Productivity is about getting more done...',
            category='productivity'
        )
        self.assertEqual(content3.category, 'productivity')

        content4 = EducationalContent.objects.create(
            title='Growth Mindset',
            content='Mindset is about your beliefs...',
            category='mindset'
        )
        self.assertEqual(content4.category, 'mindset')

        with self.assertRaises(ValueError):
            EducationalContent.objects.create(
                title='Invalid Category Content',
                content='This content has an invalid category...',
                category='invalid_category'
            )

    def test_default_created_at(self):
        content = EducationalContent.objects.create(
            title='Introduction to Neuroscience',
            content='Neuroscience is the study of the brain...',
            category='neuroscience'
        )
        self.assertIsNotNone(content.created_at)

    def test_category_invalid_value(self):
        with self.assertRaises(ValueError):
            EducationalContent.objects.create(
                title='Test Content with Invalid Category',
                content='This content has an invalid category.',
                category='invalid_category'  # Категория не входит в CATEGORY_CHOICES
            )


class ConsumedCaloriesModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')


    def test_consumed_calories_creation(self):

        consumed_item = ConsumedCalories.objects.create(
            user=self.user,
            product_name='Cottage Chease',
            weight=150.0,
            calories=95.0,
            protein=0.5,
            fat=0.3,
            carbs=25.0
        )
        self.assertEqual(consumed_item.user, self.user)
        self.assertEqual(consumed_item.product_name, 'Apple')
        self.assertEqual(consumed_item.weight, 150.0)
        self.assertEqual(consumed_item.calories, 95.0)
        self.assertEqual(consumed_item.protein, 0.5)
        self.assertEqual(consumed_item.fat, 0.3)
        self.assertEqual(consumed_item.carbs, 25.0)
        self.assertIsNotNone(consumed_item.consumed_at)   

    def test_str_method(self):

        consumed_item = ConsumedCalories.objects.create(
            user=self.user,
            product_name='Banana',
            calories=105.0
        )
        expected_str = 'Banana (105.0 kkal)'
        self.assertEqual(str(consumed_item), expected_str)

    def test_created_at_field(self):

        consumed_item = ConsumedCalories.objects.create(
            user=self.user,
            product_name='Orange',
            calories=62.0
        )
        self.assertIsNotNone(consumed_item.consumed_at)

    def test_multiple_entries_for_user(self):

        consumed_item1 = ConsumedCalories.objects.create(
            user=self.user,
            product_name='Apple',
            calories=95.0
        )
        consumed_item2 = ConsumedCalories.objects.create(
            user=self.user,
            product_name='Banana',
            calories=105.0
        )

        self.assertEqual(self.user.consumedcalories_set.count(), 2)
        self.assertIn(consumed_item1, self.user.consumedcalories_set.all())
        self.assertIn(consumed_item2, self.user.consumedcalories_set.all())

    def test_invalid_weight_or_calories(self):

        with self.assertRaises(ValueError):
            ConsumedCalories.objects.create(
                user=self.user,
                product_name='Invalid Product',
                weight=-150.0,  # Неверное значение веса
                calories=-100.0,  # Неверное количество калорий
                protein=2.0,
                fat=1.0,
                carbs=25.0
            )

    def test_zero_or_negative_values_for_nutrients(self):

        with self.assertRaises(ValueError):
            ConsumedCalories.objects.create(
                user=self.user,
                product_name='Invalid Product',
                weight=100.0,
                calories=50.0,
                protein=-2.0,  # Неверное значение для белка
                fat=3.0,
                carbs=10.0
            )

        with self.assertRaises(ValueError):
            ConsumedCalories.objects.create(
                user=self.user,
                product_name='Inavlid Product',
                weight=100.0,
                calories=50.0,
                protein=-2.0,  # Неверное значение для белка
                fat=-3.0,
                carbs=10.0
            )

        with self.assertRaises(ValueError):
            ConsumedCalories.objects.create(
                user=self.user,
                product_name='Invalid Product',
                weight=100.0,
                calories=50.0,
                protein=2.0,
                fat=3.0,
                carbs=-10.0  
            )






        
        


