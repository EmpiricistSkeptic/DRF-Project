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
    path('tasks/<str:pk>/', views.getTask),
    path('tasks/<str:pk>/update/', views.updateTask),
    path('tasks/<str:pk>/delete/', views.deleteTask),
]