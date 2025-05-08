import pytest
from django.urls import reverse
from rest_framework import status
from .factories import QuestFactory, UserFactory
from api.models import Quest, Profile

pytestmark = pytest.mark.django_db

class TestQuestViewSet:
    def test_list_quests_unaithenticated(self, client, active_quest):
        url = reverse('quest-list')
        resp = client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_quest_unauthenticated(self, client, active_quest):
        url = reverse('quest-detail', kwargs={'pk': active_quest.pk})
        resp = client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_complete_quest_unauthenticated(self, client, active_quest):
        url = reverse('quest-complete', kwargs={'pk': active_quest.pk})
        resp = client.patch(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_quests_authenticated_returns_only_own(self, client, user, test_profile, active_quest, completed_quest, other_user_quest):
        client.force_authenticate(user=user)
        url = reverse('quest-list')
        resp = client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        ids = {q['id'] for q in resp.data['results']}
        assert active_quest.id in ids
        assert completed_quest.id in ids
        assert other_user_quest.id not in ids

    def test_list_quests_authenticated_empty(self, client, user, test_profile):
        client.force_authenticate(user=user)
        url = reverse('quest-list')
        resp = client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['results'] == []


    def test_retrieve_own_quest(self, client, user, test_profile, active_quest):
        client.force_authenticate(user=user)
        url = reverse('quest-detail', kwargs={'pk': active_quest.pk})
        resp = client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['id'] == active_quest.id


    def test_retrieve_other_user_quest_raises_404(self, client, user, test_profile, other_user_quest):
        client.force_authenticate(user=user)
        url = reverse('quest-detail', kwargs={'pk': other_user_quest.pk})
        resp = client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_non_existent_quest_raises_404(self, client, user, test_profile):
        client.force_authenticate(user=user)
        non_pk = (Quest.objects.last().pk if Quest.objects.exists() else 0) + 999
        url = reverse('quest-detail', kwargs={'pk': non_pk})
        resp = client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


    def test_complete_active_quest_success(self, client, user, test_profile, active_quest):
        client.force_authenticate(user=user)
        url = reverse('quest-complete', kwargs={'pk': active_quest.pk})
        init_pts = test_profile.points
        init_lvl = test_profile.level
        resp = client.patch(url)
        assert resp.status_code == status.HTTP_200_OK
        active_quest.refresh_from_db()
        test_profile.refresh_from_db()
        assert active_quest.status == 'COMPLETED'
        assert test_profile.points == init_pts + active_quest.reward_points
        assert test_profile.level == init_lvl


    def test_complete_already_completed_quest_fails(self, client, user, test_profile, completed_quest):
        client.force_authenticate(user=user)
        url = reverse('quest-complete', kwargs={'pk': completed_quest.pk})
        resp = client.patch(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        test_profile.refresh_from_db()
        assert test_profile.points == 100


    def test_complete_other_user_quest_fails(self, client, user, test_profile, other_user_quest):
        client.force_authenticate(user=user)
        url = reverse('quest-complete', kwargs={'pk': other_user_quest.pk})
        resp = client.patch(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


    def test_complete_non_existent_quest_fails(self, client, user, test_profile):
        client.force_authenticate(user=user)
        non_pk = (Quest.objects.last().pk if Quest.objects.exists() else 0) + 999
        url = reverse('quest-complete', kwargs={'pk': non_pk})
        resp = client.patch(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


    def test_complete_quest_no_profile_fails(self, client, user, test_profile, active_quest):
        client.force_authenticate(user=user)
        Profile.objects.filter(user=user).delete()
        url = reverse('quest-complete', kwargs={'pk': active_quest.pk})
        resp = client.patch(url)
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'Профиль пользователя не найден' in resp.data['detail']




