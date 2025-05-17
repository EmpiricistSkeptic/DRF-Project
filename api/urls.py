from django.urls import path, include
from . import views
from api.agent.manager import AssistantAPIView
from .viewsets import TaskViewSet, QuestViewSet, HabitViewSet, ProfileViewSet, FriendshipViewSet, MessageViewSet, GroupViewSet, GroupMessageViewSet, NotificationViewSet, ConsumedCaloriesViewSet, UserNutritionGoalViewSet, AchievementViewSet, UserAchievementViewSet, UnitTypeViewSet, CategoryViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedSimpleRouter


router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'quests', QuestViewSet, basename='quest')
router.register(r'habits', HabitViewSet, basename='habit')
router.register(r'profile', ProfileViewSet, basename='profile')
router.register(r'friendship', FriendshipViewSet, basename='friendship')
router.register(r'messages', MessageViewSet, basename='message')

router.register(r'groups', GroupViewSet, basename='group')
groups_router = NestedSimpleRouter(router, r'groups', lookup='group')
groups_router.register(r'messages', GroupMessageViewSet, basename='group-messages')
router.register(r'notifications', NotificationViewSet, basename='notification')

router.register(r'consumed-calories', ConsumedCaloriesViewSet, basename='consumed-calories')
router.register(r'nutrition-goals', UserNutritionGoalViewSet, basename='nutrition-goals')

router.register(r'achievements', AchievementViewSet)
router.register(r'achievements/me', UserAchievementViewSet, basename='my-achievements')
router.register(r'categories', CategoryViewSet)
router.register(r'unit-types', UnitTypeViewSet)


urlpatterns = [
    path('api/', include(router.urls)),

    path('register/', views.RegistrationAPIView.as_view(), name='register'),
    path('activate/<uidb64>/<token>/', views.ActivateAccountAPIView.as_view(), name='activate-account'),
    path('login/', views.LoginAPIView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', views.LogoutAPIView.as_view(), name='token_logout'),

    path('get-calories/', views.get_calories, name='get_calories'),

    
    path('assistant/', AssistantAPIView.as_view(), name='assistant'),
    path('chat/history/', views.get_chat_history, name='chat_history_api'),
]



