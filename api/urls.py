from django.urls import path, include
from . import views
from .viewsets import TaskViewSet, QuestViewSet, HabitViewSet, ProfileViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'api/tasks', TaskViewSet, basename='task')
router.register(r'api/quests', QuestViewSet, basename='quest')
router.register(r'api/habits', HabitViewSet, basename='habit')
router.register(r'api/profile', ProfileViewSet, basename='profile')
router.register(r'friendship', FriendshipViewSet, basename='friendship')


urlpatterns = [
    path('', include(router.urls)),

    path('register/', views.registerAccount),
    path('login/', views.loginUser),
    path('logout/', views.logoutUser),
    path('profile/', views.userProfile),
    
    path('tasks/', views.tasksView, name='tasks'),
    path('tasks/create/', views.createTask, name='create_task'),
    path('tasks/complete/<int:pk>/', views.completeTask, name='complete_task'),
    path('tasks/<int:pk>/', views.getTask, name='get_task'),
    path('tasks/<int:pk>/update/', views.updateTask, name='update_task'),
    path('tasks/<int:pk>/delete/', views.deleteTask, name='delete_task'),
    path('tasks/completed/', views.getCompletedTasks, name='completed-tasks'),

    path('quests/', views.quest_list_view, name='quests'),
    path('quests/complete/<int:id>/', views.quest_complete_view, name='quest_complete'),
    path('quests/<int:id>/', views.get_quest_view, name='get_quest'),

   
    path('habits/', views.get_habits_list, name='get_habits_list'),  # GET список привычек
    path('habit/<int:id>/', views.get_habit, name='get_habit'),      # GET одна привычка
    path('habit/', views.create_habit, name='create_habit'),         # POST новая привычка
    path('habit/<int:id>/update/', views.update_habit, name='update_habit'),  # PUT/PATCH обновление
    path('habit/<int:id>/delete/', views.delete_habit, name='delete_habit'),  # PATCH деактивация
    path('habits/<int:id>/track/', views.track_user_habit, name='track-habit'),   # POST обновление стрика

    
    path('send_friend_request/<int:user_id>/', views.send_friend_request, name='send_friend_request'),
    path('accept_friend_request/<int:user_id>/', views.accept_friend_request, name='accept_friend_request'),
    path('reject_friend_request/<int:user_id>/', views.reject_friend_request, name='reject_friend_request'),
    
    path('sendMessage/', views.sendMessage, name='send_message'),
    path('getMessages/', views.getMessages, name='get_messages'),
    path('notifications/', views.getNotifications, name='get_notifications'),
    
    path('groups/', views.listGroups, name='list_groups'),
    path('groups/create/', views.createGroup, name='create_group'),
    path('groups/<int:group_id>/join/', views.joinGroup, name='join_group'),
    path('groups/<int:group_id>/leave/', views.leaveGroup, name='leave_group'),
    path('groups/<int:group_id>/messages/', views.getGroupMessages, name='get_group_messages'),
    path('groups/<int:group_id>/messages/send/', views.sendGroupMessage, name='send_group_message'),
    
    
    path('get-calories/', views.get_calories, name='get_calories'),
    path('calories-by-days/<str:period>/', views.get_calories_by_days, name='get_calories_by_days'),
    path('nutrition-summary/', views.get_nutrition_summary, name='nutrition-summary'),
    path('update-nutrition-goals/', views.update_nutrition_goals, name='update-nutrition-goals'),
    path('consumed-calories/<int:id>/', views.delete_consumed_calories, name='delete_consumed_calories'),
    
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('assistant/', views.AssistantAPIView.as_view(), name='assistant'),
    path('chat/history/', views.get_chat_history, name='chat_history_api'),
]
