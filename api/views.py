# Стандартная библиотека
import logging
from datetime import timedelta
from django.utils.timezone import now
from decimal import Decimal, ROUND_HALF_UP

# Сторонние библиотеки (Django, DRF, requests)
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q, Count, DateField, F, Sum # Объединил импорты из django.db.models
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone # Объединил импорты timezone, now доступно как timezone.now()

import requests
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# Локальные импорты приложения
from .models import ( 
    ChatHistory, ConsumedCalories, EducationalContent, Friendship, Group,
    GroupMessage, Message, Notification, PomodoroTimer, Profile, Quest, Task,
    UserNutritionGoal
)
from .serializers import ( 
    ConsumedCaloriesSerializer, EducationalContentSerializer, FriendshipSerializer,
    GroupMessageSerializer, GroupSerializer, LoginSerializer, MessageSerializer,
    NotificationSerializer, PomodoroTimerSerializer, ProfileSerializer, QuestSerializer,
    TaskSerializer, UserNutritionGoalSerializer, UserRegistrationSerializer
)

logger = logging.getLogger(__name__)



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

    profile = request.user.profile
    profile.points += task.points

    xp_threshhold = 1000 * (1.5 ** (profile.level - 1))
    while profile.points >= xp_threshhold:
        profile.level += 1
        profile.points -= xp_threshhold
        xp_threshhold = int(1000 * (1.5 ** (profile.level - 1)))

    profile.save()
    
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getCompletedTasks(request):
    tasks = Task.objects.filter(user=request.user, completed=True)
    serializer = TaskSerializer(tasks, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET']) 
@permission_classes([IsAuthenticated]) 
def quest_list_view(request):
    user = request.user
    try:
        active_quests = Quest.objects.filter(user=user, status='ACTIVE')
        serializer = QuestSerializer(active_quests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Ошибка получения списка квестов для пользователя {user.id}: {e}", exc_info=True)
        return Response({"detail": "Не удалось получить список квестов."}, status.status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def quest_complete_view(request, id):
    
    user = request.user

    # Ищем активный квест, принадлежащий текущему пользователю
    quest_to_complete = get_object_or_404(Quest, id=id, user=user, status='ACTIVE')

    try:
        # Используем транзакцию: либо все изменения сохранятся, либо ни одно
        with transaction.atomic():
            # 1. Получаем профиль пользователя
            # Используем select_for_update() для блокировки строки профиля на время транзакции,
            # чтобы избежать гонок при одновременном завершении нескольких квестов/задач.
            profile = Profile.objects.select_for_update().get(user=user)

            # 2. Обновляем статус и время завершения квеста
            quest_to_complete.status = 'COMPLETED'
            quest_to_complete.completed_at = timezone.now()
            quest_to_complete.save() # Сохраняем квест внутри транзакции

            # 3. Начисляем очки и обрабатываем уровень, если есть награда
            reward_points = quest_to_complete.reward_points # Используем новое имя поля

            if reward_points > 0:
                profile.points += reward_points
                if hasattr(profile, 'total_points'): # Обновляем total_points, если поле существует
                     profile.total_points += reward_points

                logger.info(f"Игроку {profile.username} начислено {reward_points} Points за квест '{quest_to_complete.title}'. Текущие очки: {profile.points}")

                # --- Логика повышения уровня (скопирована из твоего примера) ---
                xp_threshold = int(1000 * (1.5 ** (profile.level - 1)))
                # Добавим защиту от 0 или отрицательного порога
                if xp_threshold <= 0:
                    xp_threshold = 1000 # Минимальный порог для первого уровня

                leveled_up = False # Флаг, чтобы показать, был ли левел-ап
                while profile.points >= xp_threshold:
                    leveled_up = True
                    profile.points -= xp_threshold # Вычитаем порог текущего уровня
                    profile.level += 1             # Повышаем уровень
                    logger.info(f"Игрок {profile.username} ДОСТИГ УРОВНЯ {profile.level}!")
                    # Пересчитываем порог для НОВОГО уровня
                    xp_threshold = int(1000 * (1.5 ** (profile.level - 1)))
                    if xp_threshold <= 0: # Защита и для новых уровней
                        # Можно использовать более простую формулу как запасной вариант
                        xp_threshold = 1000 + (profile.level -1) * 500
                # --- Конец логики повышения уровня ---

                profile.save() # Сохраняем профиль внутри транзакции

                if leveled_up:
                     logger.info(f"Игрок {profile.username} завершил квест '{quest_to_complete.title}'. Финальный статус: Уровень {profile.level}, Очки {profile.points}.")
                else:
                    logger.info(f"Игрок {profile.username} завершил квест '{quest_to_complete.title}', получено {reward_points} Points. Текущие очки: {profile.points}")

            else:
                 logger.info(f"Игрок {user.username} завершил квест '{quest_to_complete.title}' без награды Points.")

        # Если транзакция завершилась успешно:
        # 4. Сериализуем и возвращаем обновленный квест
        serializer = QuestSerializer(quest_to_complete)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Profile.DoesNotExist:
        # Эта ошибка должна быть обработана внутри транзакции, но если она произойдет
        # при первоначальном получении профиля (хотя get_object_or_404 для Quest сработает раньше),
        # логируем ее. Транзакция откатится.
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: Профиль для пользователя {user.id} не найден при попытке завершить квест {id}.")
        return Response(
            {"detail": "Профиль пользователя не найден."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        # Ловим любые другие ошибки во время транзакции (ошибка БД, расчеты и т.д.)
        # Транзакция автоматически откатится при возникновении исключения.
        logger.error(f"Ошибка при завершении квеста {id} для пользователя {user.id} внутри транзакции: {e}", exc_info=True)
        return Response(
            {"detail": "Не удалось завершить квест из-за внутренней ошибки."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
        serializer = ProfileSerializer(profile, context={'request': request})
        if profile.avatar:
            print(f"Avatar physical path: {profile.avatar.path}")
            print(f"Avatar URL path: {profile.avatar.url}")
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'PUT':
        # Create a copy of the data
        data = request.data.copy()
        
        # Handle username separately
        if 'username' in data:
            request.user.username = data.get('username')
            request.user.save()
        
        # Handle avatar separately
        if data.get('avatar_clear') == 'true':
            if profile.avatar:
                profile.avatar.delete(save=False)
                profile.avatar = None
        elif 'avatar' in request.FILES:
            # If a new avatar is uploaded, replace the old one
            if profile.avatar:
                profile.avatar.delete(save=False)
            profile.avatar = request.FILES['avatar']
        
        # Now handle the rest with the serializer
        serializer = ProfileSerializer(profile, data=data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            # Re-fetch the serializer to get the updated data including the avatar_url
            updated_serializer = ProfileSerializer(profile, context={'request': request})
            return Response(updated_serializer.data, status=status.HTTP_200_OK)
        
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

    print("Request data:", request.data)

    product_name = request.data.get('product_name')
    weight = request.data.get('weight')
    if not product_name or not weight:
        print("Error: Product name or weight is missing")
        return Response({'error': 'Product name and weight are required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    query = f'{product_name} {weight}g'
    print("Query to Nutritionix:", query)

    body = {
        'query': query,
        'timezone': 'Europe/Ukraine'
    }
    
    try:
        print("Sending request to Nutritionix with body:", body)
        response = requests.post(endpoint, headers=headers, json=body)
        print("Response status:", response.status_code)
        print("Response content:", response.content)
    
        if response.status_code == 200:
            data = response.json()
            print("Parsed JSON data:", data)
            
            # Проверка наличия данных
            if not data.get('foods'):
                print("Error: No food data returned in response")
                return Response({'error': 'No food data returned.'}, status=status.HTTP_400_BAD_REQUEST)
            
            nutrients = data['foods'][0]
            print("Extracted nutrients:", nutrients)
            
            result = {
                'product_name': nutrients.get('food_name'),  # Изменил с product_name на food_name
                'calories': nutrients.get('nf_calories'),
                'proteins': nutrients.get('nf_protein'),  # Изменил с nf_proteins на nf_protein
                'fats': nutrients.get('nf_total_fat'),  # Изменил с nf_fats на nf_total_fat
                'carbs': nutrients.get('nf_total_carbohydrate'),  # Изменил с nf_carbs на nf_total_carbohydrate
                'weight': weight
            }
            print("Result to be serialized:", result)
            
            serializer = ConsumedCaloriesSerializer(data=result)
            if serializer.is_valid():
                print("Serializer is valid")
                serializer.save(user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                print("Serializer errors:", serializer.errors)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            print("Error response from API:", response.text)
            return Response({'error': f'Failed to fetch data from Nutritionix. Status code: {response.status_code}'}, 
                          status=response.status_code)
    except Exception as e:
        print("Exception during API request:", str(e))
        return Response({'error': f'API request failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


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



# --- Конфигурация (Лучше вынести в settings.py или .env) ---
# Замените на реальный URL вашего ИИ-сервиса (OpenAI, Claude, etc.)
AI_API_ENDPOINT = 'https://api.deepseek.com/v1'
# Замените на ваш реальный API-ключ (НИКОГДА не храните его прямо в коде)
AI_API_KEY = ''
# -------------------------------------------------------------

# Улучшенные шаблоны с персоной "Системы" и тематикой Solo Leveling
SYSTEM_PERSONA = (
    "Ты - 'Система', ИИ-помощник для пользователя ('Игрока'), вдохновленный системой из Solo Leveling. "
    "Твоя задача - помогать Игроку развиваться, отслеживать его прогресс, давать задания (квесты) и мотивацию. "
    "Общайся кратко, четко, используя игровую терминологию (Уровень, Опыт (Points), Навыки, Квесты, Награды, Статус). "
    "Обращайся к пользователю как к 'Игроку'."
    "Никогда не упоминай, что ты языковая модель или ИИ."
    "Всегда начинай ответ с '[Система]'."
)



PROMPT_TEMPLATES = {
    "status": (
        f"{SYSTEM_PERSONA}\n"
        "Игрок запросил свой текущий статус.\n\n"
        "--- КОНТЕКСТ ИГРОКА ---\n"
        "Сводка: {user_data_summary}\n"
        "Активные задачи:\n{active_tasks_summary}\n"
        "Недавно выполненные задачи:\n{completed_tasks_summary}\n" # Добавлено для полноты статуса
        "Активные квесты:\n{active_quests_summary}\n"
        "Питание сегодня: {nutrition_today_summary}\n" # Добавлено для полноты статуса
        "--- КОНЕЦ КОНТЕКСТА ---\n\n"
        "Предоставь краткий, но информативный отчет о статусе Игрока, основываясь на предоставленном контексте."
    ),
    "books": (
        f"{SYSTEM_PERSONA}\n"
        "Игрок интересуется книгами или чтением.\n\n"
        "--- КОНТЕКСТ ИГРОКА ---\n"
        "Сводка: {user_data_summary}\n"
        # Можно добавить задачи, если они связаны с чтением/обучением
        "Активные задачи:\n{active_tasks_summary}\n"
        "Недавно выполненные задачи:\n{completed_tasks_summary}\n"
        "--- КОНЕЦ КОНТЕКСТА ---\n\n"
        "Сообщение Игрока: {user_message}\n\n"
        "Дай краткую рекомендацию по книге, связанную с развитием навыков или знаний, или предложи мини-квест, связанный с чтением (например, 'Прочесть главу книги для +10 Points'). Учитывай уровень Игрока при сложности рекомендации/квеста."
    ),
    "tasks": (
        f"{SYSTEM_PERSONA}\n"
        "Игрок сообщает о задачах (Tasks). Возможно, он завершил их.\n\n"
        "--- КОНТЕКСТ ИГРОКА ---\n"
        "Сводка: {user_data_summary}\n"
        # Предоставляем инфо о выполненных задачах, на основе которых можно генерить квест
        "Недавно выполненные задачи:\n{completed_tasks_summary}\n"
        "Текущий Уровень: {user_level}\n" # Уровень для сложности квеста
        "--- КОНЕЦ КОНТЕКСТА ---\n\n"
        "Сообщение Игрока: {user_message}\n\n"
        "Подтверди получение информации о задачах. Если Игрок сообщает о выполнении, упомяни возможную награду (фактическое начисление происходит на бэкенде).\n"
        # Инструкция ссылается на {completed_tasks_summary} (неявно через 'выполненные задачи')
        "Проанализируй выполненные задачи и текущий Уровень ({user_level}) Игрока. ЕСЛИ СЧИТАЕШЬ УМЕСТНЫМ, СГЕНЕРИРУЙ НОВЫЙ КВЕСТ (Quest), основанный на его активности.\n"
        "Если генерируешь квест, используй ТОТ ЖЕ СТРУКТУРИРОВАННЫЙ ФОРМАТ, что и в сценарии 'quests', внутри тегов [QUEST_DATA_START] и [QUEST_DATA_END].\n"
        "Пример:\n"
        "[Система] Задача 'Ежедневная пробежка' отмечена как выполненная. +20 Points.\n"
        "Анализ активности показывает стремление к развитию выносливости. Выдан новый квест:\n"
        "[QUEST_DATA_START]\n"
        "Type: CHALLENGE\n"
        "Title: Марафонский рывок\n"
        "Description: Пробежать 10 км без остановок.\n"
        "Reward points: 100\n"
        "Reward Other: +1 Выносливость\n"
        "Penalty Info: Нет\n"
        "[QUEST_DATA_END]\n"
        "Если квест не генерируешь, просто дай обычный ответ с подтверждением."
    ),
    "nutrition": (
        f"{SYSTEM_PERSONA}\n"
        "Игрок интересуется питанием.\n\n"
        "--- КОНТЕКСТ ИГРОКА ---\n"
        "Сводка: {user_data_summary}\n" # Общий контекст уровня/очков
        "Цели питания: {nutrition_goal_info}\n"
        "Питание сегодня: {nutrition_today_summary}\n"
        "Недавняя история питания:\n{nutrition_recent_history}\n" # История для анализа паттернов, если нужно
        "--- КОНЕЦ КОНТЕКСТА ---\n\n"
        "Сообщение Игрока: {user_message}\n\n"
        "Проанализируй данные о питании, сравнивая сегодняшнее потребление ({nutrition_today_summary}) с целями ({nutrition_goal_info}). Выдай краткое уведомление: подтверди соответствие норме, предупреди о недостатке/избытке или предложи мини-квест ('Потребление X грамм белка для +15 Points')."
    ),
    "quests": (
        f"{SYSTEM_PERSONA}\n"
        "Игрок запросил новый квест или говорит о квестах.\n\n"
        "--- КОНТЕКСТ ИГРОКА ---\n"
        "Сводка: {user_data_summary}\n"
        "Активные задачи:\n{active_tasks_summary}\n" # Контекст текущей занятости
        "Недавно выполненные задачи:\n{completed_tasks_summary}\n" # Контекст недавних успехов/направлений
        "Активные квесты:\n{active_quests_summary}\n" # Чтобы не выдавать похожие или слишком много
        "Текущий Уровень Игрока: {user_level}\n" # Для сложности квеста
        "--- КОНЕЦ КОНТЕКСТА ---\n\n"
        "Сообщение Игрока: {user_message}\n\n"
        "СГЕНЕРИРУЙ НОВЫЙ КВЕСТ, подходящий для Уровня {user_level} Игрока и учитывающий его текущую активность и недавние достижения.\n"
        "ВАЖНО: Представь параметры квеста ЧЕТКО И СТРУКТУРИРОВАННО внутри специальных тегов [QUEST_DATA_START] и [QUEST_DATA_END].\n"
        "Формат внутри тегов должен быть следующим (каждый параметр на новой строке):\n"
        "Type: [УКАЖИ ОДИН ТИП: DAILY, URGENT, CHALLENGE или MAIN]\n"
        "Title: [Придумай название квеста]\n"
        "Description: [Напиши цели или описание квеста]\n"
        "Reward points: [Укажи числовое значение опыта]\n"
        "Reward Other: [Напиши текстовое описание другой награды или 'Нет']\n"
        "Penalty Info: [Напиши текстовое описание штрафа (особенно для URGENT) или 'Нет']\n"
        "Пример:\n"
        "[QUEST_DATA_START]\n"
        "Type: CHALLENGE\n"
        "Title: Испытание Скорости Мысли\n"
        "Description: Решить 5 логических задач среднего уровня сложности за 30 минут.\n"
        "Reward points: 75\n"
        "Reward Other: +1 Интеллект (очко стата)\n"
        "Penalty Info: Нет\n"
        "[QUEST_DATA_END]\n"
        "Перед тегом [QUEST_DATA_START] можешь добавить короткое вводное сообщение для Игрока."
    ),
    "motivations": (
        f"{SYSTEM_PERSONA}\n"
        "Игрок нуждается в мотивации.\n\n"
        "--- КОНТЕКСТ ИГРОКА ---\n"
        "Сводка: {user_data_summary}\n"
        "Активные задачи:\n{active_tasks_summary}\n" # Чтобы ссылаться на текущие усилия
        "Активные квесты:\n{active_quests_summary}\n" # Чтобы ссылаться на текущие вызовы
        "--- КОНЕЦ КОНТЕКСТА ---\n\n"
        "Сообщение Игрока: {user_message}\n\n"
        "Предоставь краткое, но сильное мотивирующее сообщение. Свяжи его текущие усилия (задачи, квесты) с повышением Уровня или получением новых Навыков. Напомни о его потенциале роста."
    ),
    "default": (
        f"{SYSTEM_PERSONA}\n"
        "Игрок отправил сообщение общего характера. Проанализируй его в контексте текущего состояния Игрока.\n\n"
        "--- КОНТЕКСТ ИГРОКА ---\n"
        "Сводка: {user_data_summary}\n"
        "Активные задачи:\n{active_tasks_summary}\n"
        "Недавно выполненные задачи:\n{completed_tasks_summary}\n"
        "Активные квесты:\n{active_quests_summary}\n"
        "Цели питания: {nutrition_goal_info}\n"
        "Питание сегодня: {nutrition_today_summary}\n"
        "Недавняя история питания:\n{nutrition_recent_history}\n"
        "--- КОНЕЦ КОНТЕКСТА ---\n\n"
        "Сообщение Игрока: {user_message}\n\n"
        "Ответь кратко и по делу. Если возможно, свяжи ответ с его прогрессом, предложи небольшой совет для развития или задай уточняющий вопрос для выдачи квеста/рекомендации, основываясь на предоставленном контексте."
    ),
    "skill_progress": (
        f"{SYSTEM_PERSONA}\n"
        "Игрок сообщает о прогрессе в освоении или тренировке навыка.\n\n"
        "--- КОНТЕКСТ ИГРОКА ---\n"
        "Сводка: {user_data_summary}\n"
        "Активные задачи:\n{active_tasks_summary}\n"
        "Активные квесты:\n{active_quests_summary}\n"
        "--- КОНЕЦ КОНТЕКСТА ---\n\n"
        "Сообщение Игрока: {user_message}\n\n"
        "Проанализируй сообщение Игрока, чтобы определить навык и достигнутый прогресс (если указан)."
        "Подтверди получение информации о прогрессе. "
        "Выдай краткое поощрение и, возможно, небольшую награду Points за усилие (например, '+5 Points за тренировку Навыка: [Название навыка]'). "
        "Если прогресс значителен, предложи связанный мини-квест или следующий шаг для развития этого навыка, учитывая текущий уровень игрока ({user_level})." # Добавил user_level для контекста
    )
}

QUEST_START_TAG = "[QUEST_DATA_START]"
QUEST_END_TAG = "[QUEST_DATA_END]"
QUEST_EXPECTED_KEYS = ['type', 'title', 'description', 'reward points', 'reward other', 'penalty info']



class AssistantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    RECENT_TASKS_LIMIT = 15
    RECENT_FOOD_LIMIT = 20
    # Сколько активных задач показать?
    ACTIVE_TASKS_LIMIT = 10
    # --------------------------------

    def _get_user_context(self, user):
        """
        Собирает расширенный контекст пользователя для ИИ, включая:
        - Профиль (уровень, очки, порог)
        - Статистику по задачам (всего выполнено, активные, недавние выполненные)
        - Цели по питанию
        - Сводку по питанию за сегодня
        - Недавние приемы пищи
        - Статистику по квестам (всего выполнено, активные)
        """
        context = {
            "user_data_summary": "Статус: Ошибка загрузки данных",
            "active_tasks_summary": "Активные задачи: Нет данных",
            "completed_tasks_summary": "Выполненные задачи: Нет данных",
            "nutrition_goal_info": "Цели питания: Нет данных",
            "nutrition_today_summary": "Питание сегодня: Нет данных",
            "nutrition_recent_history": "Недавние приемы пищи: Нет данных",
            "active_quests_summary": "Активные квесты: Нет данных",
            "user_level": 1, # Значение по умолчанию
        }
        try:
            profile = Profile.objects.select_related('user').get(user=user) # select_related для оптимизации
            user_name = profile.user.username
            user_level = profile.level
            user_points = profile.points

            # Рассчитываем порог XP для следующего уровня по твоей формуле
            # Используем Decimal для большей точности при возведении в степень
            level_decimal = Decimal(profile.level - 1)
            xp_threshold_decimal = Decimal(1000) * (Decimal(1.5) ** level_decimal)
            xp_threshold = int(xp_threshold_decimal.to_integral_value(rounding=ROUND_HALF_UP))
            if xp_threshold <= 0: # Порог для первого уровня
                xp_threshold = 1000

            # --- Задачи (Tasks) ---
            all_tasks = Task.objects.filter(user=user)
            completed_task_count = all_tasks.filter(completed=True).count()

            # Активные задачи (с ограничением)
            active_tasks = all_tasks.filter(completed=False).order_by('-created')[:self.ACTIVE_TASKS_LIMIT]
            active_tasks_list = [f"- {t.title} (до {t.deadline.strftime('%Y-%m-%d %H:%M') if t.deadline else 'N/A'})" for t in active_tasks]
            context["active_tasks_summary"] = f"Активные задачи ({len(active_tasks_list)} из {all_tasks.filter(completed=False).count()}):\n" + ('\n'.join(active_tasks_list) if active_tasks_list else "Нет")

            # Недавно выполненные задачи (с ограничением)
            recent_completed_tasks = all_tasks.filter(completed=True).order_by('-updated')[:self.RECENT_TASKS_LIMIT] # Используем 'updated' или 'completed_at', если добавишь
            recent_completed_list = [f"- {t.title} (+{t.points} Points)" for t in recent_completed_tasks]
            context["completed_tasks_summary"] = (
                f"Всего выполнено задач: {completed_task_count}\n"
                f"Недавние выполненные ({len(recent_completed_list)}):\n" +
                ('\n'.join(recent_completed_list) if recent_completed_list else "Нет")
            )

            # --- Квесты (Quests) ---
            all_quests = Quest.objects.filter(user=user)
            completed_quest_count = all_quests.filter(status='COMPLETED').count()
            active_quests = all_quests.filter(status='ACTIVE').order_by('-generated_at')
            active_quests_list = [f"- {q.title} ({q.get_quest_type_display()})" for q in active_quests]
            context["active_quests_summary"] = f"Активные квесты ({len(active_quests_list)}):\n" + ('\n'.join(active_quests_list) if active_quests_list else "Нет")

            # --- Базовая информация об игроке ---
            context["user_data_summary"] = (
                f"Имя: {user_name}, Уровень: {user_level}, Опыт: {user_points}/{xp_threshold} Points, "
                f"Выполнено Задач: {completed_task_count}, Выполнено Квестов: {completed_quest_count}"
            )
            context["user_level"] = user_level # Передаем отдельно для удобства в шаблонах

            # --- Питание ---
            today = timezone.now().date()
            all_consumed = ConsumedCalories.objects.filter(user=user)

            # Цель по питанию
            try:
                goal = UserNutritionGoal.objects.get(user=user)
                context["nutrition_goal_info"] = (
                    f"Цели БЖУК: {goal.calories_goal:.0f} ккал, "
                    f"{goal.proteins_goal:.0f}г Б, {goal.fats_goal:.0f}г Ж, {goal.carbs_goal:.0f}г У"
                )
            except UserNutritionGoal.DoesNotExist:
                context["nutrition_goal_info"] = "Цели питания: Не установлены"

            # Питание за сегодня (агрегация)
            today_consumed_agg = all_consumed.filter(consumed_at__date=today).aggregate(
                total_calories=Sum('calories', default=0),
                total_proteins=Sum('proteins', default=0),
                total_fats=Sum('fats', default=0),
                total_carbs=Sum('carbs', default=0)
            )
            # Убедимся, что значения не None
            calories_today = today_consumed_agg.get('total_calories') or 0
            proteins_today = today_consumed_agg.get('total_proteins') or 0
            fats_today = today_consumed_agg.get('total_fats') or 0
            carbs_today = today_consumed_agg.get('total_carbs') or 0

            if calories_today > 0 or proteins_today > 0 or fats_today > 0 or carbs_today > 0:
                 context["nutrition_today_summary"] = (
                     f"Питание сегодня: {calories_today:.0f} ккал, "
                     f"{proteins_today:.1f}г Б, {fats_today:.1f}г Ж, {carbs_today:.1f}г У"
                )
            else:
                 context["nutrition_today_summary"] = "Питание сегодня: Нет данных"

            # Недавняя история питания (с ограничением)
            # Выбираем только нужные поля и сортируем
            recent_food_items = all_consumed.order_by('-consumed_at').values(
                'product_name', 'weight', 'calories', 'proteins', 'fats', 'carbs', 'consumed_at'
            )[:self.RECENT_FOOD_LIMIT]

            if recent_food_items:
                food_history_list = []
                for item in recent_food_items:
                     # Форматируем дату/время и значения
                     time_str = item['consumed_at'].strftime('%Y-%m-%d %H:%M')
                     food_history_list.append(
                         f"- [{time_str}] {item['product_name']} ({item['weight']:.0f}г): "
                         f"{item['calories']:.0f} ккал "
                         f"(Б:{item['proteins']:.1f} Ж:{item['fats']:.1f} У:{item['carbs']:.1f})"
                     )
                context["nutrition_recent_history"] = f"Недавние приемы пищи ({len(food_history_list)}):\n" + '\n'.join(food_history_list)
            else:
                context["nutrition_recent_history"] = "Недавние приемы пищи: Нет записей"

            return context

        except Profile.DoesNotExist:
            logger.error(f"Профиль для пользователя {user.id} не найден.")
            # Возвращаем дефолтные значения с сообщением об ошибке
            context["user_data_summary"] = "Статус: Профиль не найден"
            return context
        except Exception as e:
            logger.error(f"Ошибка получения контекста для пользователя {user.id}: {e}", exc_info=True)
            # Возвращаем дефолтные значения с сообщением об общей ошибке
            context["user_data_summary"] = "Статус: Ошибка загрузки данных"
            # Остальные поля останутся со значениями по умолчанию
            return context

    def _determine_scenario(self, message):
        """Определяет сценарий на основе сообщения пользователя."""
        message_lower = message.lower()
        if any(word in message_lower for word in ["навык", "умение", "изучил", "тренировал", "прокачал", "практиковал"]):
             return "skill_progress"
        if any(word in message_lower for word in ["статус", "уровень", "опыт", "прогресс"]):
            return "status"
        if any(word in message_lower for word in ["квест", "задание", "миссия"]):
            return "quests"
        if any(word in message_lower for word in ["мотивация", "устал", "сложно", "поддержка"]):
            return "motivations"
        if any(word in message_lower for word in ["книга", "чтение", "прочитал", "литература"]):
            return "books"
        if any(word in message_lower for word in ["задача", "сделал", "выполнил", "тренировка", "челлендж"]):
            return "tasks"
        if any(word in message_lower for word in ["питание", "еда", "калории", "белки", "бжу", "диета"]):
            return "nutrition"
        # Можно добавить больше ключевых слов и сценариев
        return "default"

    def _call_ai_service(self, prompt):
        """Выполняет вызов внешнего ИИ API."""
        headers = {
            'Authorization': f'Bearer {AI_API_KEY}',
            'Content-Type': 'application/json'
        }
        # Параметры могут отличаться в зависимости от API (например, для OpenAI Completion/ChatCompletion)
        payload = {
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': SYSTEM_PERSONA},
                {'role': 'user', 'content': prompt} 
            ],
            'max_tokens': 400, 
            'temperature': 1.0,
        }

        try:
            response = requests.post(
                AI_API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=15 
            )
            response.raise_for_status() # Проверка на HTTP ошибки (4xx, 5xx)
            response_data = response.json()

            ai_text = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

            if not ai_text:
                logger.warning(f"ИИ вернул пустой ответ. Payload (частично): {payload.get('messages')}")
                return "[Система] Не могу обработать запрос в данный момент."

            # Добавляем префикс, если ИИ его не добавил
            if not ai_text.startswith("[Система]"):
                ai_text = f"[Система] {ai_text}"

            return ai_text

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка вызова ИИ API ({AI_API_ENDPOINT}): {e}")
            return "[Система] Ошибка связи с сервером ИИ. Попробуйте позже."
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обработке ответа ИИ: {e}")
            return "[Система] Внутренняя ошибка при обработке вашего запроса."

    def _parse_and_create_quest(self, text_block, user):
        """
        Парсит блок текста с данными квеста и создает объект Quest.
        Возвращает созданный объект Quest или None в случае ошибки.
        (Версия из предыдущего ответа)
        """
        quest_data = {}
        lines = text_block.strip().splitlines()

        for line in lines:
            if ':' not in line: continue
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            if key in QUEST_EXPECTED_KEYS:
                quest_data[key] = value

        if not all(k in quest_data for k in ['type', 'title', 'description', 'reward points']):
             logger.warning(f"Парсинг квеста: отсутствуют обязательные поля в: {text_block}")
             return None

        try:
            valid_quest_types = [choice[0] for choice in Quest.QUEST_TYPES]
            parsed_type = quest_data.get('type', '').upper()
            if parsed_type not in valid_quest_types:
                 logger.warning(f"Парсинг квеста: недопустимый тип '{parsed_type}', используется CHALLENGE.")
                 parsed_type = 'CHALLENGE'

            model_data = {
                'user': user,
                'title': quest_data.get('title', 'Квест без названия'),
                'description': quest_data.get('description', ''),
                'quest_type': parsed_type,
                'reward_points': int(quest_data.get('reward points', 0)),
                'reward_other': quest_data.get('reward other', None),
                'penalty_info': quest_data.get('penalty info', None),
            }
            if not model_data['reward_other'] or model_data['reward_other'].lower() == 'нет':
                model_data['reward_other'] = None
            if not model_data['penalty_info'] or model_data['penalty_info'].lower() == 'нет':
                model_data['penalty_info'] = None

        except ValueError:
             logger.error(f"Парсинг квеста: ошибка преобразования reward points в число: {quest_data.get('reward points')}")
             return None
        except Exception as e:
            logger.error(f"Парсинг квеста: неожиданная ошибка подготовки данных: {e}", exc_info=True)
            return None

        try:
            # Используем transaction.atomic для гарантии целостности
            with transaction.atomic():
                 new_quest = Quest.objects.create(**model_data)
            logger.info(f"Создан квест ID {new_quest.id} '{new_quest.title}' для {user.username}")
            return new_quest
        except Exception as e:
            logger.error(f"Ошибка создания квеста в БД для {user.id}: {e}", exc_info=True)
            return None


    def post(self, request, *args, **kwargs):
        """
        Обрабатывает POST-запрос с сообщением пользователя к ИИ и сохраняет историю.
        """
        user = request.user
        user_message = request.data.get('message', '').strip()

        # --- Инициализация переменных для сохранения ---
        prompt_to_save = None
        scenario = None
        ai_response_raw = "[Система] Ответ не был сгенерирован." # Дефолт, если ИИ не вызван
        final_response_to_user = "[Система] Ошибка обработки запроса." # Дефолт для пользователя
        error_occurred_flag = False
        error_message_text = None
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR # Дефолтный статус ошибки

        if not user_message:
            final_response_to_user = '[Система] Получено пустое сообщение.'
            error_occurred_flag = True
            error_message_text = "Получено пустое сообщение от пользователя."
            status_code = status.HTTP_400_BAD_REQUEST
            # Сохраняем запись об ошибке и выходим
            self._save_chat_history(
                user=user,
                user_msg="<ПУСТОЕ СООБЩЕНИЕ>", # Или сам user_message, если нужно
                ai_resp=final_response_to_user,
                error_flag=error_occurred_flag,
                err_msg=error_message_text
            )
            return Response({'response': final_response_to_user}, status=status_code)

        try:
            # 1. Получаем контекст пользователя
            user_context = self._get_user_context(user)
            # Не будем прерывать из-за ошибки контекста, но можем залогировать в error_message позже, если нужно

            # 2. Определяем сценарий
            scenario = self._determine_scenario(user_message) # Сохраняем сценарий
            template = PROMPT_TEMPLATES.get(scenario, PROMPT_TEMPLATES["default"])

            # 3. Формируем промпт
            try:
                prompt = template.format(
                    user_message=user_message,
                    **user_context
                )
                prompt_to_save = prompt # Сохраняем промпт
            except KeyError as e:
                 logger.error(f"Ошибка форматирования промпта для сценария '{scenario}': ключ {e}.")
                 final_response_to_user = '[Система] Внутренняя ошибка: не удалось подготовить данные.'
                 error_occurred_flag = True
                 error_message_text = f"Ошибка форматирования промпта: ключ {e} отсутствует."
                 # Сохраняем ошибку и выходим
                 self._save_chat_history(user, user_message, final_response_to_user, prompt_to_save, scenario, error_occurred_flag, error_message_text)
                 return Response({'response': final_response_to_user}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 4. Вызываем ИИ
            ai_response_raw = self._call_ai_service(prompt)
            final_response_to_user = ai_response_raw # Ответ по умолчанию для пользователя

            # --- 5. Парсинг и создание квеста (интегрировано) ---
            created_quest = None
            status_code = status.HTTP_200_OK # По умолчанию успех, если ИИ ответил

            # Проверяем, не вернул ли сам вызов ИИ ошибку
            # Более надежная проверка на строки, возвращаемые _call_ai_service в случае ошибки
            if ai_response_raw.startswith("[Система] Ошибка") or ai_response_raw == "[Система] Не могу обработать запрос в данный момент." or ai_response_raw == "[Система] Внутренняя ошибка при обработке вашего запроса.":
                 logger.warning(f"Вызов ИИ вернул ошибку для {user.id}, парсинг квеста пропускается.")
                 error_occurred_flag = True # Отмечаем как ошибку
                 error_message_text = ai_response_raw # Сохраняем сообщение об ошибке от ИИ
                 status_code = status.HTTP_503_SERVICE_UNAVAILABLE # Сервис ИИ недоступен или ошибся
            else:
                # ИИ ответил без явной ошибки, пытаемся найти и обработать квест
                try:
                    start_index = ai_response_raw.find(QUEST_START_TAG)
                    end_index = ai_response_raw.find(QUEST_END_TAG)

                    if start_index != -1 and end_index != -1 and start_index < end_index:
                        quest_block_start = start_index + len(QUEST_START_TAG)
                        quest_block_end = end_index
                        quest_text_block = ai_response_raw[quest_block_start:quest_block_end]

                        new_quest_object = self._parse_and_create_quest(quest_text_block, user)

                        if new_quest_object:
                            created_quest = new_quest_object
                            response_before_quest = ai_response_raw[:start_index].strip()
                            response_after_quest = ai_response_raw[end_index + len(QUEST_END_TAG):].strip()
                            confirmation_message = f"[Система] Новый квест '{new_quest_object.title}' добавлен в ваш журнал."
                            parts = [part for part in [response_before_quest, confirmation_message, response_after_quest] if part]
                            final_response_to_user = '\n'.join(parts) # Обновляем ответ для пользователя
                        else:
                            logger.warning(f"Обнаружен блок квеста, но не обработан для {user.id}. Ответ ИИ оставлен без изменений.")
                            # Можно добавить к error_message_text информацию о неудачном парсинге, но не считать это критической ошибкой
                            # error_message_text = (error_message_text + "\n" if error_message_text else "") + "Ошибка парсинга блока квеста."

                except Exception as e:
                     logger.error(f"Ошибка во время парсинга блока квеста для {user.id}: {e}", exc_info=True)
                     # Оставляем final_response_to_user как ai_response_raw
                     # Отмечаем, что была ошибка, но не обязательно критическая для всего ответа
                     error_occurred_flag = True # Считаем ошибкой, т.к. ожидаемый парсинг не удался
                     error_message_text = (error_message_text + "\n" if error_message_text else "") + f"Ошибка парсинга квеста: {e}"


            # --- 6. Сохраняем в историю чата (перед возвратом) ---
            self._save_chat_history(
                user=user,
                user_msg=user_message,
                ai_resp=final_response_to_user, # Сохраняем финальный ответ, отправленный пользователю
                prompt_msg=prompt_to_save,
                scenario_str=scenario,
                error_flag=error_occurred_flag,
                err_msg=error_message_text
            )

            # 7. Возвращаем финальный ответ пользователю
            return Response({'response': final_response_to_user}, status=status_code)

        except Exception as e:
            # --- Отлов глобальных непредвиденных ошибок ---
            logger.error(f"Неожиданная глобальная ошибка в AssistantAPIView.post для {user.id}: {e}", exc_info=True)
            final_response_to_user = "[Система] Произошла внутренняя ошибка сервера."
            error_occurred_flag = True
            error_message_text = f"Глобальная ошибка: {e}"
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            # Сохраняем запись об ошибке
            self._save_chat_history(
                user=user,
                user_msg=user_message,
                ai_resp=final_response_to_user,
                prompt_msg=prompt_to_save, # Может быть None, если ошибка до его формирования
                scenario_str=scenario, # Может быть None
                error_flag=error_occurred_flag,
                err_msg=error_message_text
            )

            return Response({'response': final_response_to_user}, status=status_code)