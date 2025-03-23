from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path('', views.getRoutes),
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
    
    path('pomodoro/start/', views.start_pomodoro_session, name='start_pomodoro_session'),
    path('pomodoro/<int:pk>/update/', views.update_pomodoro_session, name='update_pomodoro_session'),
    path('pomodoro/<int:pk>/delete/', views.delete_pomodoro_session, name='delete_pomodoro_session'),
    path('pomodoro/', views.get_pomodoro_sessions, name='get_pomodoro_sessions'),
    
    path('educational-content/', views.get_educational_content, name='get_educational_content'),
    path('educational-content/<int:content_id>/', views.view_educational_content, name='view_educational_content'),
    path('educational-content/add/', views.add_educational_content, name='add_educational_content'),
    path('educational-content/<int:content_id>/delete/', views.delete_educational_content, name='delete_educational_content'),
    path('educational-content/<int:content_id>/update/', views.update_educational_content, name='update_educational_content'),
    path('educational-content/search/', views.search_educational_content, name='search_educational_content'),
    
    path('get-calories/', views.get_calories, name='get_calories'),
    path('calories-by-days/<str:period>/', views.get_calories_by_days, name='get_calories_by_days'),
    path('nutrition-summary/', views.get_nutrition_summary, name='nutrition-summary'),
    path('update-nutrition-goals/', views.update_nutrition_goals, name='update-nutrition-goals'),
    path('consumed-calories/<int:id>/', views.delete_consumed_calories, name='delete_consumed_calories'),
    
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
