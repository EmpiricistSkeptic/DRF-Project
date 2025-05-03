import pytest
from django.urls import reverse
from rest_framework import status
from .factories import TaskFactory, UserFactory
from api.models import Task, Profile

@pytest.mark.django_db
class TestTaskViewSet:

  def test_list_returns_only_uncompleted(self, auth_client):
    incomplete = TaskFactory.create_batch(2, completed=False, user=auth_client.handler._force_user)
    TaskFactory(completed=True, user=auth_client.handler._force_user)

    url = reverse('task-list')
    resp = auth_client.get(url)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data['count'] == 2
    assert len(resp.data['results']) == 2
    for item in resp.data['results']:
      assert item['completed'] is False


  
  def test_cannot_retrieve_other_users_task(self, auth_client):
    other = TaskFactory()
    url = reverse('task-detail', kwargs={'pk': other.pk})
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


  def test_create_sets_current_user(self, auth_client):
    payload = {'title': 'Test Task', 'description': 'Test Description', 'completed': False, 'points': 10}
    url = reverse('task-list')
    resp = auth_client.post(url, payload)

    assert resp.status_code == status.HTTP_201_CREATED
    obj = Task.objects.get(id=resp.data['id'])
    assert obj.user == auth_client.handler._force_user


  @pytest.mark.parametrize('method,payload', [
    ('put', {'title': 'Full', 'description': 'D', 'completed': False}),
    ('patch', {'title': 'Partial'}),
  ])
  def test_update_own_task(self, auth_client, method, payload):
    task = TaskFactory(user=auth_client.handler._force_user, title='Old')
    url = reverse('task-detail', kwargs={'pk': task.pk})
    resp = getattr(auth_client, method)(url, payload)
    assert resp.status_code == status.HTTP_200_OK
    task.refresh_from_db()
    assert task.title == payload['title']

  def test_delete_own_task(self, auth_client):
    task = TaskFactory(user=auth_client.handler._force_user)
    url = reverse('task-detail', kwargs={'pk': task.pk})
    resp = auth_client.delete(url)
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert not Task.objects.filter(id=task.pk).exists()

  def test_complete_task_success(self, auth_client):
    user = auth_client.handler._force_user
    if not hasattr(user, 'profile'):
         user.profile = Profile.objects.create(user=user, points=50, level=1)
         user.save()

    task_points = 10 
    task = TaskFactory(user=user, completed=False, points=task_points)
    profile = user.profile
    initial_points = profile.points
    initial_level = profile.level

    url = reverse('task-complete', kwargs={'pk': task.pk})
    resp = auth_client.put(url) 

    assert resp.status_code == status.HTTP_200_OK

    task.refresh_from_db()
    profile.refresh_from_db()

    assert task.completed is True
    assert profile.points == initial_points + task_points

  def test_complete_already_completed(self, auth_client):
    task = TaskFactory(user=auth_client.handler._force_user, completed=True)
    url = reverse('task-complete', kwargs={'pk': task.pk})
    resp = auth_client.put(url)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Task is already completed" in resp.data['detail']

  def test_completed_list_returns_only_completed(self, auth_client):
    user = auth_client.handler._force_user
    TaskFactory.create_batch(3, completed=True, user=user)

    TaskFactory.create_batch(3, completed=False, user=user) 
    url = reverse('task-completed')
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    
    results = resp.data['results'] if 'results' in resp.data else resp.data
    assert len(results) == 3
    assert all(item['completed'] for item in results)