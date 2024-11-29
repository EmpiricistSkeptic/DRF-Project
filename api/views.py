from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import TaskSerializer, UserRegistrationSerializer, ProfileSerializer, LoginSerializer, FriendshipSerializer, MessageSerializer, NotificationSerializer
from .models import Task, Profile, Message, Friendship, Notification
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User



@api_view(['GET'])
def getRoutes(request):
    routes = [
        {
            'Endpoint': '/tasks/',
            'method': 'GET',
            'body': None,
            'description': 'Returns an array of tasks'
        },
        {
            'Endpoint': '/tasks/id',
            'method': 'GET',
            'body': None,
            'description': 'Returns a single task object'
        },
        {
            'Endpoint': '/tasks/create/',
            'method': 'POST',
            'body': {'body': "The content of the task"},
            'description': 'Creates a new task with data sent in POST request'
        },
        {
            'Endpoint': '/tasks/id/update/',
            'method': 'PUT',
            'body': {'body': "Updated content of the task"},
            'description': 'Updates an existing task with data sent in PUT request'
        },
        {
            'Endpoint': '/tasks/id/delete/',
            'method': 'DELETE',
            'body': None,
            'description': 'Deletes an existing task'
        }
    ]
    return Response(routes)


@api_view(['GET'])
def tasksView(request):
    tasks = Task.objects.filter(user=request.user, completed=False)
    serializer = TaskSerializer(tasks, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def getTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)
        serializer = TaskSerializer(task, many=False)
        return Response(serializer.data)
    except Task.DoesNotExist:
        return Response({"detail": "Task not found or not owned by this user"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def createTask(request):
    data = request.data

    task = Task.objects.create(
        title = data['title']
    )
    user = request.user
    serializer = TaskSerializer(task, many=False)
    return Response(serializer.data)

@api_view(['PUT'])
def updateTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)
        serializer = TaskSerializer(task, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not owned by the user"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
def completeTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)  # Получаем задачу по ID и пользователю
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not owned by the user"}, status=status.HTTP_404_NOT_FOUND)
    
    task.completed = True  # Помечаем задачу как завершённую
    task.save()  # Сохраняем изменения
    
    serializer = TaskSerializer(task)
    return Response(serializer.data, status=status.HTTP_200_OK)

    

@api_view(['DELETE'])
def deleteTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)
        task.delete()
        return Response({"detail": "Task has been deleted"}, status=status.HTTP_204_NO_CONTENT)
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not owned by the user"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def registerAccount(request):
    if request.method == 'POST':
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "User created succssefuly"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def loginUser(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "message": "Login successful"}, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def logoutUser(request):
    try:
        token = request.user.auth_token
        if token:
            token.delete()
            return Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        return Response({"error": "No token provided"}, status=status.HTTP_400_BAD_REQUEST)
    except:
        return Response({"error": "An error occured during logout"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET', 'PUT'])
def userProfile(request):
    if request.method == 'GET':
        try:
            profile = request.user.profile
            serializer = ProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Profile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
    elif request.method == 'PUT':
        try:
            profile = request.user.profile
            serializer = ProfileSerializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Profile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def send_friend_request(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if Friendship.objects.filter(user=request.user, friend=user).exists():
        return Response({'detail': 'Friend request already sent.'}, status=status.HTTP_400_BAD_REQUEST)
    friendship = Friendship.objects.create(user=request.user, friend=user, status='PENDING')
    Notification.objects.create(user=user, notification_type='friend_request', message=f"{request.user.username} sent you a friend request.")
    serializer = FriendshipSerializer(friendship)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def sendMessage(request):
    sender = request.user
    recipient_id = request.data.get('recipient_id')
    content = request.data.get('content')

    # Проверка на обязательные данные
    if not recipient_id or not content:
        return Response({'detail': 'Recipient and content are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Получаем получателя или выдаем 404, если не найден
    recipient = get_object_or_404(User, id=recipient_id)
    
    # Создаем сообщение
    message = Message.objects.create(
        sender=request.user,
        recipient=recipient,
        content=content
    )
    
    # Создаем уведомление для получателя
    Notification.objects.create(
        user=recipient,
        notification_type='message',
        message=f"You have a new message from {sender.username}."
    )

    # Сериализация сообщения
    serializer = MessageSerializer(message)
    
    # Возвращаем успешный ответ с сериализованными данными
    return Response(serializer.data, status=status.HTTP_201_CREATED)



@api_view(['POST'])
def getMessages(request):
    messages = Message.objects.filter(recipient=request.user)
    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def getNotifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)
        










