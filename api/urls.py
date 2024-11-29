from django.urls import path
from . import views

urlpatterns = [
    path('', views.getRoutes),
    path('register/', views.registerAccount),
    path('login/', views.loginUser),
    path('logout/', views.logoutUser),
    path('profile/', views.userProfile),
    path('tasks/', views.tasksView),
    path('tasks/create/', views.createTask),
    path('tasks/complete/<int:pk>/', views.completeTask, name='complete-task'),
    path('tasks/<str:pk>/', views.getTask),
    path('tasks/<str:pk>/update/', views.updateTask),
    path('tasks/<str:pk>/delete/', views.deleteTask),
    path('send_friend_request/<int:user_id>/', views.send_friend_request, name='send_friend_request'),
    path('sendMessage/', views.sendMessage, name='sendMessage'),
    path('getMessages/', views.getMessages, name='getMessages'),
]