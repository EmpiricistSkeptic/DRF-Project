import pytest
from django.urls import reverse
from rest_framework import status
from .factories import UserFactory, HabitFactory
from api.models import UserHabit
from django.utils import timezone

pytestmark = pytest.mark.django_db

class TestHabitViewSet:
    def test_list_habits_unauthenticated(self, client):
        url = reverse('habit-list')
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


    def test_retrieve_habit_unauthenticated(self, client, active_habit):
        url = reverse('habit-detail', kwargs={'pk': active_habit.pk})
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    
    def test_track_habit_unauthenticated(self, client, active_habit):
        url = reverse('habit-track', kwargs={'pk': active_habit.pk})
        response = client.post(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    
    def test_list_habits_authenticated_returns_only_own(self, auth_client, user, active_habit, other_user_habit):
        url = reverse('habit-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        ids = {q['id'] for q in response.data['results']}
        assert active_habit.id in ids
        assert other_user_habit.id not in ids

    
    def test_list_habits_authenticated_empty(self, auth_client, user):
        url = reverse('habit-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == []

    
    def test_retrieve_own_habit(self, auth_client, user, active_habit):
        url = reverse('habit-detail', kwargs={'pk': active_habit.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == active_habit.id

    
    def test_retrieve_other_user_habit_raises_404(self, auth_client, user, other_user_habit):
        url = reverse('habit-detail', kwargs={'pk': other_user_habit.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


    def test_retrieve_non_existent_habit_raises_404(self, auth_client, user):
        non_pk = (UserHabit.objects.last().pk if UserHabit.objects.exists() else 0) + 999
        url = reverse('habit-detail', kwargs={'pk': non_pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


    def test_create_habit_unauthenticated(self, client):
        payload = {
            'title': 'TestName',
            'description': 'TestDesc',
            'frequency': 'Daily',
        }
        url = reverse('habit-list')
        response = client.post(url, data=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


    def test_create_habit_authenticated_success(self, auth_client, user):
        payload = {
            'title': 'TestName',
            'description': 'TestDesc',
            'frequency': 'Daily',
        }
        url = reverse('habit-list')
        response = auth_client.post(url, data=payload)
        assert response.status_code == status.HTTP_201_CREATED
        obj =  UserHabit.objects.get(id=response.data['id'])
        assert obj.user == user
        assert UserHabit.objects.get(id=response.data['id'])

    def test_create_habit_authenticated_invalid_data(self, auth_client, user):
        payload = {
            'description': 'TestDesc',
            'frequency': 'Daily'
        }
        url = reverse('habit-list')
        response = auth_client.post(url, data=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_habit_unauthenticated(self, client, user, active_habit):
        url = reverse('habit-detail', kwargs={'pk': active_habit.pk})
        response = client.patch(url, data={'title': 'Changed title'})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    
    def test_update_own_habit_authenticated_success(self, auth_client, user, active_habit):
        url = reverse('habit-detail', kwargs={'pk': active_habit.pk})
        new_title = 'Fresh title'
        response = auth_client.patch(url, data={'title': new_title})
        assert response.status_code == status.HTTP_200_OK
    
        active_habit.refresh_from_db()
        assert active_habit.title == new_title

    
    def test_update_own_habit_authenticated_invalid_data(self, auth_client, user, active_habit):
        url = reverse('habit-detail', kwargs={'pk': active_habit.pk})
        response = auth_client.patch(url, data={'title': ''})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
    
    def test_update_other_user_habit_raises_404(self, auth_client, user, other_user_habit):
        url = reverse('habit-detail', kwargs={'pk': other_user_habit.pk})
        response = auth_client.patch(url, data={'title': 'No SM'})
        assert response.status_code == status.HTTP_404_NOT_FOUND


    def test_update_non_existent_habit_raises_404(self, auth_client, user):
        non_pk = (UserHabit.objects.last().pk if UserHabit.objects.exists() else 0) + 999
        url = reverse('habit-detail', kwargs={'pk': non_pk})
        response = auth_client.patch(url, data={'title': 'Attempt to update non-existent'})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    
    def test_delete_habit_unauthenticated(self, client, active_habit):
        url = reverse('habit-detail', kwargs={'pk': active_habit.pk})
        response = client.delete(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    
    def test_delete_own_habit_authenticated_success(self, auth_client, user, active_habit):
        url = reverse('habit-detail', kwargs={'pk': active_habit.pk})
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not UserHabit.objects.filter(pk=active_habit.pk).exists()

    
    def test_delete_non_existent_habit_raises_404(self, auth_client, user):
        non_pk = (UserHabit.objects.last().pk if UserHabit.objects.exists() else 0) + 999
        url = reverse('habit-detail', kwargs={'pk': non_pk})
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    
    def test_list_habits_shows_only_active_habits(self, auth_client, user, active_habit, inactive_habit):
        url = reverse('habit-list')
        response = auth_client.get(url)
        ids = (q['id'] for q in response.data['results'])
        assert active_habit.id in ids
        assert inactive_habit.id not in ids

    
    def test_list_habits_pagination_works(self, auth_client, user, active_habit):
        url = reverse('habit-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict), "Ответ пагинации должен быть словарем"
        expected_keys = ['count', 'next', 'previous', 'results']
        for key in expected_keys:
            assert key in response.data, f"Ключ '{key}' отсутствует в ответе пагинации"
        
        assert isinstance(response.data['results'], list), "Ключ 'results' должен содержать список"
        
        if active_habit:
            response.data['count'] >= 1
            assert len(response.data['results']) > 0


    def test_track_non_existent_habit_not_found(self, auth_client, user):
        non_pk = 9999
        url = reverse('habit-track', kwargs={'pk': non_pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
    
    def test_track_habit_unauthenticated_user_forbidden(self, client, active_habit):
        url = reverse('habit-track', kwargs={'pk': active_habit.pk})
        response = client.post(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    
    def test_track_others_habit_forbidden(self, auth_client, user, other_user_habit):
        url = reverse('habit-track', kwargs={'pk': other_user_habit.pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


    def test_track_own_habit_successfully(self, auth_client, user, habit_untracked):
        initial_streak = habit_untracked.streak
        url = reverse('habit-track', kwargs={'pk': habit_untracked.pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        habit_untracked.refresh_from_db()
        assert response.data['detail'] == "Habit tracked successfully!"
        assert response.data['streak'] == initial_streak + 1
        assert habit_untracked.streak == initial_streak + 1
        assert habit_untracked.last_tracked == timezone.now().date()
        

    def test_track_own_habit_already_tracked_today(self, auth_client, user, habit_untracked):
        url = reverse('habit-track', kwargs={'pk': habit_untracked.pk})
        auth_client.post(url)
        habit_untracked.refresh_from_db()
        streak_after_first_track = habit_untracked.streak
        last_tracked_after_first_track = habit_untracked.last_tracked

        response = auth_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        habit_untracked.refresh_from_db()
        assert response.data['detail'] == "Habit has already been tracked today!"
        assert response.data['streak'] == streak_after_first_track
        assert response.data['last_tracked'] == last_tracked_after_first_track


    def test_track_habit_resets_streak_if_day_missed(self, auth_client, user, active_habit):
        active_habit.last_tracked = timezone.now().date() - timezone.timedelta(days=2)
        active_habit.save()
        
        url = reverse('habit-track', kwargs={'pk': active_habit.pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        active_habit.refresh_from_db()

        assert response.data['streak'] == 1
        assert active_habit.streak == 1
        assert active_habit.last_tracked == timezone.now().date()

    



    

        
        
    
        

    


    
    


