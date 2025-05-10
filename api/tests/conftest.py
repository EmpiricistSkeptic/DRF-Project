import pytest
from rest_framework.test import APIClient
from .factories import UserFactory, QuestFactory, HabitFactory
from api.models import Profile

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
  return APIClient()


@pytest.fixture
def auth_client(client, user):
  client.force_authenticate(user=user)
  return client


@pytest.fixture
def user():
  return UserFactory()


@pytest.fixture
def another_user():
  return UserFactory()


@pytest.fixture
def test_profile(user):
  profile = user.profile
  username = user.username
  avatar = None
  bio = None
  profile.points = 100
  profile.level = 1
  profile.save()
  return profile
  

@pytest.fixture
def another_profile(another_user):
  profile_obj = another_user.profile
  profile_obj.points = 150
  profile_obj.level = 1
  profile_obj.save()
  return profile_obj

@pytest.fixture
def active_habit(user):
  return HabitFactory(user=user, title='No sugar', is_active=True, streak=5)


@pytest.fixture
def inactive_habit(user):
  return HabitFactory(user=user, title='Inactive', is_active=False)

@pytest.fixture
def habit_untracked(user):
  return HabitFactory(user=user, title='Untracked', is_active=True, streak=0, last_tracked=None)


@pytest.fixture
def other_user_habit(another_user):
  return HabitFactory(user=another_user, title='Yoga nidra 10 minutes', is_active=True, streak=3)

@pytest.fixture
def active_quest(user):
  return QuestFactory(user=user, title='Study Spanish', status='ACTIVE', reward_points=500)

@pytest.fixture
def completed_quest(user):
  return QuestFactory(user=user, title='Study English', reward_points=200, status='COMPLETED')

@pytest.fixture
def other_user_quest(another_user):
  return QuestFactory(user=another_user, title='Go for a run', status='ACTIVE', reward_points=50)

@pytest.fixture
def quest_for_level_up(user, test_profile):
    return QuestFactory(user=user, title='Martial arts session', reward_points=1500)

