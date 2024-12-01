from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import TaskSerializer, UserRegistrationSerializer, ProfileSerializer, LoginSerializer, FriendshipSerializer, MessageSerializer, NotificationSerializer, GroupMessageSerializer, GroupSerializer, PomodoroTimerSerializer, EducationalContentSerializer
from .models import Task, Profile, Message, Friendship, Notification, Group, GroupMessage, PomodoroTimer, EducationalContent
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from rest_framework.pagination import PageNumberPagination



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
def accept_friend_request(request, user_id):
    friendship = get_object_or_404(Friendship, user=user_id, friend=request.user, status='PENDING')
    friendship.status = 'ACCEPTED'
    friendship.save()

    Notification.objects.create(
        user=friendship.user,
        notification_type='friend_request_accepted',
        message=f"{request.user.username} accepted your friend request",
    )
    Friendship.objects.create(user=friendship.user, friend=friendship.friend, status='FRIEND')
    Friendship.objects.create(user=friendship.friend, friend=friendship.user, status='FRIEND')

    return Response({'detail': 'Friend request accepted'}, status=status.HTTP_200_OK)

@api_view(['POST'])
def reject_friend_request(request, user_id):
    friendship = get_object_or_404(Friendship, user=user_id, friend=request.user, status='PENDING')
    friendship.delete()

    Notification.objects.create(
        user=friendship.user,
        notification_type='friend_request_rejected',
        message=f"{request.user.username} rejected your friend request."
    )
    return Response({'detail': 'Friend request rejected'}, status=status.HTTP_200_OK)


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def createGroup(request):
    data = request.data
    group = Group.objects.create(
        name=data['name'],
        description=data['description', ''],
        created_by=request.user 
    )
    group.members.add(request.user)

    serializer = GroupSerializer(group)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listGroups(request):
    groups = Group.objects.filter(members=request.user)
    serializer = GroupSerializer(groups, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def joinGroup(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    group.members.add(request.user)
    return Response({'message': f'You joined the group {group.name}'}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leaveGroup(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    group.members.remove(request.user)
    return Response({'messgae': f'You left the group {group.name}'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sendGroupMessage(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if request.user not in group.members.all():
        return Response({'error': 'You are not a member of this group'}, status=status.HTTP_403_FORBIDDEN)
    data = request.data
    message = GroupMessage.objects.create(
        group=group,
        sender=request.user,
        content=data['content']
    )
    serializer = GroupMessageSerializer(message)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getGroupMessages(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if request.user not in group.members.all():
        return Response({'error': 'You are not a member of this group'}, status=status.HTTP_403_FORBIDDEN)
    messages = GroupMessage.objects.filter(group=group)
    serializer = GroupMessageSerializer(messages, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def start_pomodoro_session(request):
    serializer = PomodoroTimerSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_pomodoro_sessions(request):
    sessions = PomodoroTimer.objects.filter(user=request.user)
    serializer = PomodoroTimerSerializer(sessions, many=True)
    return Response(serializer.data)

class EducationContentPagination(PageNumberPagination):
    page_size = 10

@api_view(['GET'])
def get_educational_content(request):
    category = request.query_params.get('category', None)
    contents = EducationalContent.objects.all()
    if category:
        contents = EducationalContent.objects.filter(category=category)
    paginator = EducationContentPagination()
    result_page = paginator.paginate_queryset(contents, request)
    seializer = EducationalContentSerializer(result_page, many=True)
    return paginator.get_paginated_response(seializer.data)


@api_view(['GET'])
def view_educational_content(request, content_id):
    try:
        content = EducationalContent.objects.get(id=content_id)
        content.increment_views()
        serializer = EducationalContentSerializer(content)
        return Response(serializer.data)
    except EducationalContent.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)
    

@api_view(['POST'])
def add_educational_content(request):
    serializer = EducationalContentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
def delete_educational_content(request, content_id):
    try:
        content = EducationalContent.objects.get(id=content_id)
        content.delete()
        return Response({'message': 'Content deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)
    except EducationalContent.DoesNotExist:
        return Response({'error': 'Content not found.'}, status=status.HTTP_404_NOT_FOUND)
    

@api_view(['PUT'])
def update_educational_content(request, content_id):
    try:
        content = EducationalContent.objects.get(id=content_id)
        serializer = EducationalContentSerializer(content, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except EducationalContent.DoesNotExist:
        return Response({'error': 'Content not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PATCH'])
def update_pomodoro_session(request, pk):
    session = get_object_or_404(PomodoroTimer, pk=pk, user=request.user)
    serializer = PomodoroTimerSerializer(session, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
def delete_pomodoro_session(request, pk):
    session = get_object_or_404(PomodoroTimer, pk=pk, user=request.user)
    serializer = PomodoroTimerSerializer(session)
    session.delete()
    return Response(serializer.data, status=status.HTTP_200_OK)













