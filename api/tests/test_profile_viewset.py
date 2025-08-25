import pytest
from django.urls import reverse
from rest_framework import status
from .factories import UserFactory
from api.models import Profile

pytestmark = pytest.mark.django_db


class TestProfileViewSet:

    def test_profile_created_for_new_user(self, user, test_profile):
        assert hasattr(user, "profile")

    def test_retrieve_profile_authenticated(self, auth_client, user, test_profile):
        url = reverse("profile-detail", kwargs={"pk": test_profile.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == test_profile.id

    def test_retrieve_profile_unauthenticated(self, client, test_profile):
        url = reverse("profile-detail", kwargs={"pk": test_profile.pk})
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_profile_authenticated(self, auth_client, user, test_profile):
        url = reverse("profile-detail", kwargs={"pk": test_profile.pk})
        new_bio = "Amor Fati"
        response = auth_client.patch(url, data={"bio": new_bio})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["bio"] == new_bio

    def test_cannot_update_another_user_profile(
        self, auth_client, user, another_profile, test_profile
    ):
        url = reverse("profile-detail", kwargs={"pk": another_profile.pk})
        new_bio = "Hello"
        response = auth_client.patch(url, data={"bio": new_bio})
        assert response.status_code == status.HTTP_200_OK
        test_profile.refresh_from_db()
        another_profile.refresh_from_db()
        assert test_profile.bio == new_bio
        assert another_profile.bio == None

    def test_update_profile_unauthenticated(self, client, test_profile):
        url = reverse("profile-detail", kwargs={"pk": test_profile.pk})
        new_bio = "Amor Fati"
        response = client.patch(url, data={"bio": new_bio})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_username(self, auth_client, user, test_profile):
        url = reverse("profile-detail", kwargs={"pk": test_profile.pk})
        new_username = "Jack"
        response = auth_client.patch(url, data={"username": new_username})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == new_username
