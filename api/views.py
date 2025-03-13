from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import TaskSerializer, UserRegistrationSerializer, ProfileSerializer, LoginSerializer, FriendshipSerializer, MessageSerializer, NotificationSerializer, GroupMessageSerializer, GroupSerializer, PomodoroTimerSerializer, EducationalContentSerializer, ConsumedCaloriesSerializer, UserNutritionGoalSerializer
from .models import Task, Profile, Message, Friendship, Notification, Group, GroupMessage, PomodoroTimer, EducationalContent, ConsumedCalories, UserNutritionGoal
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.db.models import Sum, DateField
from django.db.models.functions import TruncDate
import requests
from django.utils.timezone import now
from datetime import timedelta



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
@permission_classes([IsAuthenticated])
def tasksView(request):
    tasks = Task.objects.filter(user=request.user, completed=False)
    serializer = TaskSerializer(tasks, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)
        serializer = TaskSerializer(task)
        return Response(serializer.data)
    except Task.DoesNotExist:
        return Response({"detail": "Task not found or not owned by this user"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def createTask(request):
    serializer = TaskSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def updateTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)
        serializer = TaskSerializer(task, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not owned by the user"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def completeTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)  
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not owned by the user"}, status=status.HTTP_404_NOT_FOUND)
    
    task.completed = True  
    task.save()  
    
    serializer = TaskSerializer(task)
    return Response(serializer.data, status=status.HTTP_200_OK)

    

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deleteTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)
        task.delete()
        return Response({"detail": "Task has been deleted"}, status=status.HTTP_204_NO_CONTENT)
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not owned by the user"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def registerAccount(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({"message": "User created successfully"}, status=status.HTTP_201_CREATED)
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
        token = getattr(request.user, 'auth_token', None)
        if token:
            token.delete()
            return Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        return Response({"error": "No token found"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": f"An error occurred during logout: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def userProfile(request):
    profile = getattr(request.user, 'profile', None)
    if not profile:
        return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = ProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'PUT':
        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_friend_request(request, user_id):
    if request.user.id == user_id:
        return Response({'detail': "You can't send a friend request to yourself."}, status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(User, id=user_id)

    if Friendship.objects.filter(user=request.user, friend=user).exists():
        return Response({'detail': 'Friendship or request already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    friendship = Friendship.objects.create(user=request.user, friend=user, status='PENDING')
    Notification.objects.create(user=user, notification_type='friend_request', message=f"{request.user.username} sent you a friend request.")

    serializer = FriendshipSerializer(friendship)
    return Response(serializer.data, status=status.HTTP_201_CREATED)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_friend_request(request, user_id):
    friendship = get_object_or_404(Friendship, user__id=user_id, friend=request.user, status='PENDING')

    # Удаляем старую заявку
    friendship.delete()

    # Создаём новую дружбу (одна запись автоматически означает взаимную дружбу)
    Friendship.objects.create(user=request.user, friend=friendship.user, status='FRIEND')

    Notification.objects.create(
        user=friendship.user,
        notification_type='friend_request_accepted',
        message=f"{request.user.username} accepted your friend request",
    )

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
@permission_classes([IsAuthenticated])
def sendMessage(request):
    sender = request.user
    recipient_id = request.data.get('recipient_id')
    content = request.data.get('content', '').strip()

    if not recipient_id or not content:
        return Response({'detail': 'Recipient and content are required'}, status=status.HTTP_400_BAD_REQUEST)

    if sender.id == recipient_id:
        return Response({'detail': 'You cannot send a message to yourself.'}, status=status.HTTP_400_BAD_REQUEST)

    recipient = get_object_or_404(User, id=recipient_id)

    message = Message.objects.create(sender=sender, recipient=recipient, content=content)

    Notification.objects.create(
        user=recipient,
        notification_type='message',
        message=f"You have a new message from {sender.username}."
    )

    serializer = MessageSerializer(message)
    return Response(serializer.data, status=status.HTTP_201_CREATED)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def getMessages(request):
    messages = Message.objects.filter(recipient=request.user)
    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
        description=data.get('description', ''),
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
    return Response({'message': f'You left the group {group.name}'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sendGroupMessage(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if request.user not in group.members.all():
        return Response({'error': 'You are not a member of this group'}, status=status.HTTP_403_FORBIDDEN)
    data = request.data
    content = data.get('content', '').strip()
    if not content:
        return Response({'error': 'Content is required'}, status=status.HTTP_400_BAD_REQUEST)
    message = GroupMessage.objects.create(
        group=group,
        sender=request.user,
        content=content
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
@permission_classes([IsAuthenticated])
def start_pomodoro_session(request):
    serializer = PomodoroTimerSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pomodoro_sessions(request):
    sessions = PomodoroTimer.objects.filter(user=request.user)
    serializer = PomodoroTimerSerializer(sessions, many=True)
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_pomodoro_session(request, pk):
    session = get_object_or_404(PomodoroTimer, pk=pk, user=request.user)
    serializer = PomodoroTimerSerializer(session, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_pomodoro_session(request, pk):
    session = get_object_or_404(PomodoroTimer, pk=pk, user=request.user)
    serializer = PomodoroTimerSerializer(session)
    session.delete()
    return Response(serializer.data, status=status.HTTP_200_OK)

class EducationContentPagination(PageNumberPagination):
    page_size = 10


@api_view(['GET'])
def get_educational_content(request):
    category = request.query_params.get('category', None)
    contents = EducationalContent.objects.all()
    if category:
        contents = contents.filter(category=category)
    paginator = EducationContentPagination()
    result_page = paginator.paginate_queryset(contents, request)
    serializer = EducationalContentSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
def view_educational_content(request, content_id):
    try:
        content = EducationalContent.objects.get(id=content_id)
        content.increment_views()  # Предполагается, что этот метод существует
        serializer = EducationalContentSerializer(content)
        return Response(serializer.data)
    except EducationalContent.DoesNotExist:
        return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_educational_content(request):
    serializer = EducationalContentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_educational_content(request, content_id):
    try:
        content = EducationalContent.objects.get(id=content_id)
        content.delete()
        # Если статус 204, по спецификации тело ответа не должно присутствовать,
        # но можно вернуть 200, если требуется сообщение.
        return Response({'message': 'Content deleted successfully.'}, status=status.HTTP_200_OK)
    except EducationalContent.DoesNotExist:
        return Response({'error': 'Content not found.'}, status=status.HTTP_404_NOT_FOUND)
    

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
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


@api_view(['GET'])
def search_educational_content(request):
    query = request.query_params.get('query', None)
    if query:
        contents = EducationalContent.objects.filter(Q(title__icontains=query) | Q(content__icontains=query))
        serializer = EducationalContentSerializer(contents, many=True)
        return Response(serializer.data)
    return Response({'error': 'Query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_calories(request):
    API_KEY = "1a1b7806964c5865d8bcb89cffbd73c8"  # Ваш ключ к API Nutritionix
    APP_ID = "faf1a44a"     # Ваш App ID от Nutritionix
    endpoint = "https://trackapi.nutritionix.com/v2/natural/nutrients"
    
    headers = {
        'x-app-id': APP_ID,
        'x-app-key': API_KEY,
        'Content-Type': 'application/json',
    }

    product_name = request.data.get('product_name')
    weight = request.data.get('weight')
    if not product_name or not weight:
        return Response({'error': 'Product name and weight are required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    body = {
        'query': f'{weight}g {product_name}',
        'timezone': 'Europe/Ukraine'
    }
    # Используем библиотеку requests для внешнего запроса
    response = requests.post(endpoint, headers=headers, json=body)
    
    if response.status_code == 200:
        data = response.json()
        # Проверка наличия данных
        if not data.get('foods'):
            return Response({'error': 'No food data returned.'}, status=status.HTTP_400_BAD_REQUEST)
        nutrients = data['foods'][0]
        result = {
            'product_name': nutrients.get('product_name'),
            'calories': nutrients.get('nf_calories'),
            'proteins': nutrients.get('nf_proteins'),
            'fats': nutrients.get('nf_fats'),
            'carbs': nutrients.get('nf_carbs'),
        }
        
        serializer = ConsumedCaloriesSerializer(data=result)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({'error': 'Failed to fetch data from Nutritionix.'}, status=response.status_code)
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_calories_by_days(request, period):
    today = now().date()
    if period == 'week':
        start_date = today - timedelta(days=7)
    elif period == 'month':
        start_date = today - timedelta(days=30)
    else:
        return Response({'error': 'Invalid period specified.'}, status=status.HTTP_400_BAD_REQUEST)
    
    records = (
        ConsumedCalories.objects.filter(
            user=request.user,
            consumed_at__date__gte=start_date  # Используем корректное имя поля (consumed_at)
        )
        .annotate(date=TruncDate('consumed_at'))
        .values('date') 
        .annotate(
            total_calories=Sum('calories'),
            total_proteins=Sum('proteins'),
            total_fat=Sum('fats'),
            total_carbs=Sum('carbs')
        )
        .order_by('date')
    )
    return Response(list(records), status=status.HTTP_200_OK)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nutrition_summary(request):
    today = now().date()

    daily_totals = ConsumedCalories.objects.filter(
        user=request.user,
        consumed_at__date=today
    ).aggregate(
        total_calories=Sum('calories'),
        total_proteins=Sum('proteins'),
        total_fats=Sum('fats'),
        total_carbs=Sum('carbs')
    )

    # Заменяем None на 0 для всех полей
    for key in daily_totals:
        if daily_totals[key] is None:
            daily_totals[key] = 0
    
    try:
        user_goals = UserNutritionGoal.objects.get(user=request.user)
        goals = {
            'calories_goal': user_goals.calories_goal,
            'proteins_goal': user_goals.proteins_goal,
            'fats_goal': user_goals.fats_goal,
            'carbs_goal': user_goals.carbs_goal
        }
    except UserNutritionGoal.DoesNotExist:
        goals = {
            'calories_goal': 2000,  
            'proteins_goal': 50,
            'fats_goal': 70,
            'carbs_goal': 260
        }
    
    # Get today's meals
    today_meals = ConsumedCalories.objects.filter(
        user=request.user,
        consumed_at__date=today
    ).order_by('-consumed_at')  # Сортировка по времени (сначала новые)
    
    meals_serializer = ConsumedCaloriesSerializer(today_meals, many=True)
    
    # Combine all data
    response_data = {
        **daily_totals,
        **goals,
        'meals': meals_serializer.data,
        'remaining': {
            'calories': goals['calories_goal'] - daily_totals['total_calories'],
            'proteins': goals['proteins_goal'] - daily_totals['total_proteins'],
            'fats': goals['fats_goal'] - daily_totals['total_fats'],
            'carbs': goals['carbs_goal'] - daily_totals['total_carbs']
        }
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_nutrition_goals(request):
    serializer = UserNutritionGoalSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_consumed_calories(request, id):
    try:
        meal = ConsumedCalories.objects.get(id=id, user=request.user)
        meal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except ConsumedCalories.DoesNotExist:
        return Response({'error': 'Meal not found'}, status=status.HTTP_404_NOT_FOUND)









