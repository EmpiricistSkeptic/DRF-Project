import factory
from django.contrib.auth.models import User
from api.models import Task, Profile, Quest, UserHabit
from django.utils import timezone


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda u: f"{u.username}@test.com")
    password = factory.PostGenerationMethodCall("set_password", "password123")
    is_active = True

    class Meta:
        model = User


class HabitFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Habit {n}")
    is_active = True
    streak = 0

    class Meta:
        model = UserHabit


class TaskFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("text")
    completed = False
    points = factory.Iterator([10, 20, 30])

    class Meta:
        model = Task


class ProfileFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    points = 100
    level = 1

    class Meta:
        model = Profile


class QuestFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Quest {n}")
    status = "ACTIVE"
    reward_points = 100
    completed_at = None

    @factory.post_generation
    def mark_completed(self, create, extracted, **kwargs):
        if extracted:
            self.status = "COMPLETED"
            self.completed_at = timezone.now()
            if create:
                self.save()

    class Meta:
        model = Quest
