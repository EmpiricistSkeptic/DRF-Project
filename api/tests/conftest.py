import pytest
from rest_framework.test import APIClient
from .factories import UserFactory, QuestFactory
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
  profile.points = 100
  profile.level = 1
  profile.save()
  return profile
  


@pytest.fixture
def another_profile(another_user):
  return user.profile

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

