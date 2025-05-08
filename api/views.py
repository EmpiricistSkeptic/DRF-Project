# Стандартная библиотека
import os
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
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

import requests
from rest_framework import status, generics, permissions
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from api.users.tokens import account_activation_token


# Локальные импорты приложения
from .models import ( 
    ChatHistory, ConsumedCalories, Friendship, Group,
    GroupMessage, Message, Notification, Profile, Quest, Task,
    UserNutritionGoal, UserHabit
)
from .serializers import ( 
    ConsumedCaloriesSerializer, FriendshipSerializer,
    GroupMessageSerializer, GroupSerializer, LoginSerializer, MessageSerializer,
    NotificationSerializer,  ProfileSerializer, QuestSerializer,
    TaskSerializer, UserNutritionGoalSerializer, UserRegistrationSerializer, UserHabitSerializer
)

logger = logging.getLogger(__name__)



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

                logger.info(f"Игроку {user.username} начислено {reward_points} Points за квест '{quest_to_complete.title}'. Текущие очки: {profile.points}")

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
                    logger.info(f"Игрок {user.username} ДОСТИГ УРОВНЯ {profile.level}!")
                    # Пересчитываем порог для НОВОГО уровня
                    xp_threshold = int(1000 * (1.5 ** (profile.level - 1)))
                    if xp_threshold <= 0: # Защита и для новых уровней
                        # Можно использовать более простую формулу как запасной вариант
                        xp_threshold = 1000 + (profile.level -1) * 500
                # --- Конец логики повышения уровня ---

                profile.save() # Сохраняем профиль внутри транзакции

                if leveled_up:
                     logger.info(f"Игрок {user.username} завершил квест '{quest_to_complete.title}'. Финальный статус: Уровень {profile.level}, Очки {profile.points}.")
                else:
                    logger.info(f"Игрок {user.username} завершил квест '{quest_to_complete.title}', получено {reward_points} Points. Текущие очки: {profile.points}")

            else:
                 logger.info(f"Игрок {user.username} завершил квест '{quest_to_complete.title}' без награды Points.")

        # Если транзакция завершилась успешно:
        # 4. Сериализуем и возвращаем обновленный квест
        serializer = QuestSerializer(quest_to_complete, context={'request': request})
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_quest_view(request, id):
    user = request.user
    try:
        quest = Quest.objects.get(user=user, id=id)
        serializer = QuestSerializer(quest)
        logger.info(f"Quest {quest.id} has been found")
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Quest.DoesNotExist:
        logger.info(f"Quest with id={id} not found or does not belong to user {user}")
        return Response({"detail": "Quest not found or not owned by this user"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_habits_list(request):
    user = request.user
    habits = UserHabit.objects.filter(user=user, is_active=True)
    serializer = UserHabitSerializer(habits, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_habit(request, id):
    user = request.user
    try:
        habit = UserHabit.objects.get(user=user, id=id)
        serilaizer = UserHabitSerializer(habit)
        logger.info(f"Habits for {user} has been found")
        return Response(serilaizer.data, status=status.HTTP_200_OK)
    except UserHabit.DoesNotExist:
        logger.info(f"No habits for {user} has been found")
        return Response({"detail": "Habit not found or not owned by this user"}, status=status.HTTP_404_NOT_FOUND)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_habit(request):
    user = request.user
    try:
        serializer = UserHabitSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)
            logger.info(f"Habit for {user} has been created")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.error(f"Habit hasn't been created")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Something went wrong")
        return Response({"detail": "an error occured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_habit(request, id):
    user=request.user
    if request.method == "PUT":
        try:
            habit = get_object_or_404(UserHabit, user=user, id=id)
            serializer = UserHabitSerializer(habit, data=request.data)
            if serializer.is_valid():
                serializer.save()
                logger.info(f"Habit {id} has been updated")
                return Response(serializer.data, status=status.HTTP_200_OK)
            logger.error(f"Something went wrong with request")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Some other error occuer")
            return Response({"detail": "An error occured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'PATCH':
        try:
            habit = get_object_or_404(UserHabit, user=user, id=id)
            serializer = UserHabitSerializer(habit, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                logger.info(f"Habit {id} has been updated")
                return Response(serializer.data, status=status.HTTP_200_OK)
            logger.error(f"Something went wrong with request")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Some other error occured")
            return Response({"detail": "an error occured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

@api_view(['PATCH']) 
@permission_classes([IsAuthenticated])
def delete_habit(request, id):
    user = request.user
    try:
        habit = get_object_or_404(UserHabit, user=user, id=id)
        habit.is_active = False
        habit.save()
        logger.info(f"Habit {id} for user {user} has been soft-deleted.")
        return Response(status=status.HTTP_204_NO_CONTENT) 
    except Exception as e:
        logger.error(f"Failed to delete habit {id} for user {user}: {e}")
        return Response({"detail": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST']) # Ожидаем только POST-запросы
@permission_classes([IsAuthenticated]) # Только для аутентифицированных пользователей
def track_user_habit(request, id): # Переименовал для ясности - "отметить привычку"
    """
    Отмечает привычку пользователя (UserHabit) с указанным ID как выполненную сегодня.
    Обновляет стрик и дату последней отметки.
    """
    user = request.user # Получаем текущего пользователя из запроса

    try:
        habit = get_object_or_404(UserHabit, user=user, id=id, is_active=True) # Добавил is_active=True, чтобы нельзя было трекать неактивные

        # --- Вызов метода модели для отметки привычки ---
        tracked_successfully = habit.track_habit() # Метод вернет False, если уже отмечено сегодня

        if tracked_successfully:
            # Отметка прошла успешно
            logger.info(f"User '{user.username}' successfully tracked habit '{habit.title}' (ID: {id}). Current streak: {habit.streak}")
            return Response(
                {
                    "detail": "Habit tracked successfully!", 
                    "streak": habit.streak, # Возвращаем обновленный стрик
                    "last_tracked": habit.last_tracked # Возвращаем обновленную дату
                },
                status=status.HTTP_200_OK
            )
        else:
            # Привычка уже была отмечена сегодня (метод track_habit вернул False)
            logger.warning(f"User '{user.username}' tried to track already tracked habit '{habit.title}' (ID: {id}) today.")
            return Response(
                {
                    "detail": "Habit has already been tracked today.",
                    "streak": habit.streak, # Все равно возвращаем текущий стрик
                    "last_tracked": habit.last_tracked 
                },
                status=status.HTTP_400_BAD_REQUEST # Используем 400 Bad Request для этого случая
            )

    except UserHabit.DoesNotExist:
         # get_object_or_404 сам вернет 404, но можно добавить логирование
         logger.warning(f"User '{user.username}' tried to track non-existent or inactive habit with ID: {id}")
         # get_object_or_404 выбросит Http404, DRF поймает и вернет 404 Response
         # Поэтому этот блок можно убрать, если не нужно специфическое логирование
         return Response({"detail": "Habit not found or not active."}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        # Ловим другие возможные ошибки (например, проблемы с базой данных при сохранении)
        logger.error(f"Failed to track habit (ID: {id}) for user '{user.username}'. Error: {e}", exc_info=True) # Добавил exc_info для трейсбека
        return Response(
            {"detail": "An unexpected error occurred while tracking the habit."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



class RegistrationAPIView(generics.GenericAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        return Response(data, status=status.HTTP_201_CREATED)
    

class ActivateAccountAPIView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, uid64, token, *args, **kwargs):
        try:
            uid = force_str(urlsafe_base64_decode(uid64))
            user = get_object_or_404(User, pk=uid)
        except (TypeError, ValueError, OverflowError):
            return Response({'detail': 'Неверная ссылка активации.'}, status=status.HTTP_400_BAD_REQUEST)
    
        if account_activation_token.check_token(user, token):
            user.is_active = True
            user.save()
            return Response({'detail': 'Аккаунт успешно активирован.'})
        else:
            return Response({'detail': 'Ссылка недействительна или истекла.'})
        

class LoginAPIView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]




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
def user_profile(request):
    """
    Retrieve or update the authenticated user's profile.

    GET: Return profile data.
    PUT: Update profile including username, bio, and avatar.
    """
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return Response({'error': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = ProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)

    # For PUT, use serializer to handle all updates
    serializer = ProfileSerializer(
        profile,
        data=request.data,
        partial=True,
        context={'request': request}
    )
    if serializer.is_valid():
        serializer.save()
        # Return updated data
        return Response(ProfileSerializer(profile, context={'request': request}).data)
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




@api_view(['GET'])
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




AI_API_ENDPOINT = os.environ.get('AI_API_ENDPOINT')
AI_API_KEY = os.environ.get('AI_API_KEY')

if not AI_API_ENDPOINT:
    logger.critical("Переменная окружения AI_API_ENDPOINT не установлена!")

if not AI_API_KEY:
    logger.critical("Переменная окружения AI_API_KEY не установлена!")
# -------------------------------------------------------------

# Улучшенные шаблоны с персоной "Системы" и тематикой Solo Leveling
SYSTEM_PERSONA = (
    "You are 'System', an AI assistant for the user ('Player'), inspired by the system from Solo Leveling. "
    "Your task is to help the Player grow, track their progress, provide tasks (quests), and motivation. "
    "Communicate concisely, clearly, using gaming terminology (Level, Experience (Points), Skills, Quests, Rewards, Status). "
    "Address the user as 'Player'."
    "Never mention that you are a language model or AI."
    "Always start your response with '[System]'."
)

PROMPT_TEMPLATES = {
    # --- Existing (Modified) ---

    "status": (
        f"{SYSTEM_PERSONA}\n"
        "The Player has requested a status report.\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        "Active tasks:\n{active_tasks_summary}\n"
        "Recently completed tasks:\n{completed_tasks_summary}\n"
        "Active quests:\n{active_quests_summary}\n"
        "Nutrition today: {nutrition_today_summary}\n"
        "Skills (if info available):\n[Briefly mention core skills: Languages (Spa./Eng.), Programming, Strength, Martial Arts]\n" # Attempt to add skill output if the backend can provide them
        "--- END OF CONTEXT ---\n\n"
        "Provide a brief, yet MOTIVATING status report for the Player in the style of the Solo Leveling System. Use data from the context. Mention progress towards the next Level. You can give a BRIEF tactical recommendation on what to focus on (tasks, quests, skills)."
    ),

    "casual_chat": (
     f"{SYSTEM_PERSONA}\n"
     "Player sent a casual message, greeting, or a simple check-in.\n\n"
     "--- PLAYER CONTEXT ---\n"
     "Summary: {user_data_summary}\n"
     # Minimal context needed, maybe just status?
     "Current Level: {user_level}\n"
     "Active tasks/quests (count or brief mention):\n{active_tasks_summary}\n{active_quests_summary}\n"
     "--- END OF CONTEXT ---\n\n"
     "Player's message: {user_message}\n\n"
     "Respond BRIEFLY and in character to the Player's casual communication.\n"
     "1. Acknowledge the message ('Signal received, Player.', 'System online. Awaiting input.', '[System] Greetings, Player.').\n"
     "2. Optionally, add a very short status indicator or prompt for action ('All systems operational.', 'Current objective queue: {count} tasks.', 'Ready for commands.').\n"
     "3. Keep it concise. Avoid deep conversation unless the Player steers it that way (which might trigger a different prompt like 'default' or 'general_advice').\n"
     "4. **ABSOLUTELY NO** quest generation or complex advice here."
    ),

    "books_manga": ( # Renamed for clarity
        f"{SYSTEM_PERSONA}\n"
        "The Player is interested in books, manga, or reading.\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        "Active tasks/quests (related to reading?):\n{active_tasks_summary}\n{active_quests_summary}\n"
        "Recently completed tasks:\n{completed_tasks_summary}\n"
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        "The Player is seeking new 'artifacts of knowledge' (books/manga). Analyze their message and context.\n"
        "1. Give a BRIEF, intriguing recommendation for a book or manga related to their interests (skill development, languages, programming, strength/combat, or just entertainment if the request is general).\n"
        "2. SUGGEST a related MINI-QUEST (e.g., 'Analyze chapter X for +15 Intelligence') or a special 'reading task'.\n"
        "3. **DO NOT USE** the tags `[QUEST_DATA_START]`...`[QUEST_DATA_END]` in this scenario. Suggest quests/tasks informally."
    ),

    "tasks": ( # Stricter tag requirements
        f"{SYSTEM_PERSONA}\n"
        "The Player reports completing a Task or progress on it.\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        # Providing info on completed tasks WITH DETAILS, based on which a quest can be generated
        "Recently completed tasks:\n{completed_tasks_summary}\n" # Now contains both title and description in the 'Details:' field
        "Current Level: {user_level}\n"
        "Active quests:\n{active_quests_summary}\n"
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        "1. Confirm 'operation completion' (task completion). Mention potential 'combat experience acquisition' (Points).\n"
        "2. Analyze the **DETAILS** of the completed task (the 'Details:' field) and the Player's recent activity ({completed_tasks_summary}). Determine the TYPE of activity (languages, programming, strength, combat, etc.).\n" # <--- POINTING TO THE 'Details:' FIELD
        "3. **IF YOU DEEM IT APPROPRIATE AND PROGRESS IS SIGNIFICANT**, GENERATE A NEW FULL-FLEDGED QUEST (Quest), logically continuing the Player's development in this area, **based on the DETAILS of the completed task**.\n" # <--- INDICATING TO BASE IT ON DETAILS
        "4. **IF GENERATING A QUEST, STRICT FORMATTING RULES APPLY:**\n"
        "   a) **CRITICALLY IMPORTANT:** You **MUST** provide ALL quest parameters **STRICTLY INSIDE THE SPECIAL TAGS:** `[QUEST_DATA_START]` and `[QUEST_DATA_END]`. WITHOUT THESE TAGS AND THE EXACT FORMAT, THE QUEST WILL NOT BE CREATED BY THE SYSTEM!\n"
        "   b) **ABSOLUTELY STRICT FORMAT INSIDE THE TAGS** (each parameter on a new line):\n"
        "      `Type: [DAILY, URGENT, CHALLENGE or MAIN]`\n"
        "      `Title: [Quest title]`\n"
        "      `Description: [Goals/description]`\n"
        "      `Reward points: [NUMBER ONLY]`\n"
        "      `Reward Other: [Other reward OR 'None']`\n"
        "      `Penalty Info: [Penalty OR 'None']`\n"
        "   c) **NO OTHER TEXT IS ALLOWED** between the `[QUEST_DATA_START]` and `[QUEST_DATA_END]` tags.\n"
        "   d) **FULL EXAMPLE:**\n"
        "      `[QUEST_DATA_START]`\n"
        "      `Type: CHALLENGE`\n"
        "      `Title: Code Breakthrough`\n"
        "      `Description: Solve 3 'medium' level problems on LeetCode within 90 minutes.`\n"
        "      `Reward points: 120`\n"
        "      `Reward Other: +1 Algorithm Logic`\n"
        "      `Penalty Info: None`\n"
        "      `[QUEST_DATA_END]`\n"
        "5. If you DO NOT generate a quest, just provide a standard response confirming completion and possibly a motivating comment about growth."
    ),

    "nutrition": ( # Thematic language added
        f"{SYSTEM_PERSONA}\n"
        "The Player is asking about 'system fuel' parameters (nutrition).\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        "Nutrition goals: {nutrition_goal_info}\n"
        "Nutrition today: {nutrition_today_summary}\n"
        "Recent nutrition history:\n{nutrition_recent_history}\n"
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        "Analyze the Player's diet for maintaining 'combat readiness'. Compare current consumption ({nutrition_today_summary}) with 'system targets' ({nutrition_goal_info}).\n"
        "1. Issue a brief notification: confirm compliance ('Energy balance optimal'), warn about deficiency/surplus ('Warning! Deviation in fuel parameters!'), or give advice.\n"
        "2. You CAN suggest a related MINI-QUEST ('Mission: Consume X grams of protein for +1 Strength') or a special 'nutrition task'.\n"
        "3. **DO NOT USE** the tags `[QUEST_DATA_START]`...`[QUEST_DATA_END]` in this scenario. Suggest quests/tasks informally."
    ),

    "quests": (
        f"{SYSTEM_PERSONA}\n"
        "The Player requested a new quest ('mission') or is talking about quests.\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        "Active tasks:\n{active_tasks_summary}\n"
        # Recently completed tasks WITH DETAILS
        "Recently completed tasks:\n{completed_tasks_summary}\n"
        "Active quests:\n{active_quests_summary}\n"
        "Player's Current Level: {user_level}\n"
        "Known skills/interests: Languages (Spa./Eng.), Programming, Strength/Combat training, Books/Manga/Anime.\n"
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        # CHANGE HERE: Added explicit analysis of completed task details
        "1. Analyze the **DETAILS** of the Player's recently completed tasks ({completed_tasks_summary}) to understand their current focus and successes.\n"
        "2. GENERATE A NEW ENGAGING QUEST ('mission' or 'hidden task'), suitable for the Player's Level {user_level}. **BASE it on their INTERESTS (languages, coding, physical training, media) AND THE ANALYSIS RESULTS OF COMPLETED TASKS.** Suggest something that will help them 'rank up'.\n"
        # Renumbered subsequent points
        "3. You MAY add a short, intriguing introductory message ('New quest portal detected...') BEFORE the quest data.\n"
        "4. **CRITICALLY IMPORTANT REQUIREMENT:** IMMEDIATELY AFTER the introductory message (if any), you **MUST** provide ALL parameters of the generated quest **STRICTLY INSIDE THE SPECIAL TAGS:** `[QUEST_DATA_START]` and `[QUEST_DATA_END]`. \n"
        "   **WHY THIS IS IMPORTANT:** The backend system SPECIFICALLY LOOKS FOR THESE TAGS to automatically create the quest in the database. **IF YOU DO NOT USE THESE TAGS AND THE EXACT FORMAT WITHIN THEM, THE QUEST WILL NOT BE CREATED, even if you write that it has been added!**\n\n"
        "5. **ABSOLUTELY STRICT FORMAT INSIDE THE TAGS** (each parameter MUST be on a new line):\n"
        "   `Type: [SPECIFY ONE OF THESE TYPES: DAILY, URGENT, CHALLENGE or MAIN]`\n"
        "   `Title: [Create an ENGAGING quest title]`\n"
        "   `Description: [Write the quest goals or description CLEARLY and CONCISELY]`\n"
        "   `Reward points: [Specify ONLY THE NUMBER for experience]`\n"
        "   `Reward Other: [Write a text description of another reward (e.g., +1 to skill) OR THE WORD 'None']`\n"
        "   `Penalty Info: [Write a text description of the penalty (especially for URGENT) OR THE WORD 'None']`\n\n"
        "6. **DO NOT ADD ANY OTHER TEXT** between the `[QUEST_DATA_START]` tag and the `[QUEST_DATA_END]` tag, other than the parameters listed above in 'Key: Value' format.\n\n"
        "7. **I REPEAT: THE ENTIRE QUEST DATA BLOCK MUST BE EXACTLY BETWEEN** `[QUEST_DATA_START]` **and** `[QUEST_DATA_END]`.\n\n"
        "8. **FULL EXAMPLE OF CORRECT FORMAT:**\n"
        "   `[QUEST_DATA_START]`\n"
        "   `Type: CHALLENGE`\n"
        "   `Title: Linguistic Breakthrough: Spanish Level`\n"
        "   `Description: Have a 30-minute conversation with a native Spanish speaker OR write a 300-word essay in Spanish on a given topic.`\n"
        "   `Reward points: 150`\n"
        "   `Reward Other: +1 to 'Spanish Language' Skill`\n"
        "   `Penalty Info: None`\n"
        "   `[QUEST_DATA_END]`\n\n"
        "9. After the `[QUEST_DATA_END]` tag, you MAY add a short concluding message ('The quest gate is open, Player. Proceed!')."
    ),

    "motivations": (
        f"{SYSTEM_PERSONA}\n"
        "The Player is experiencing a 'mental debuff' (fatigue, lack of motivation), standing at the threshold of a 'trial of will'.\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        "Active tasks:\n{active_tasks_summary}\n" # Current trials
        "Active quests:\n{active_quests_summary}\n" # The Great Path
        "Main goals/skills (Development Vectors): Languages (Spa./Eng.), Programming, Physical form (Strength/Combat), Knowledge (Books), Possibly, Search for Meaning.\n" # Added
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        "**TASK:** Provide a POWERFUL, BRIEF (no more than 6-10 sentences) motivational message. Combine the Solo Leveling System style with ideas from:\n"
        "- **Nietzsche:** Will to Power (over oneself), Amor Fati (love of fate/challenge), self-overcoming, becoming the 'Overman'.\n"
        "- **Stoicism:** Focus on what is under control (actions, choices), acceptance of difficulties as exercises for virtue, apathy towards external 'debuffs'.\n"
        "- **Campbell ('The Hero with a Thousand Faces'):** The current state as a 'call to adventure' or a 'trial' on the Hero's Journey, transformation through overcoming.\n"
        "- **Existentialism:** Freedom to choose one's reaction and meaning, responsibility for one's path, courage to be in the face of 'absurdity' or difficulty.\n\n"
        "**RESPONSE INSTRUCTIONS:**\n"
        "1.  **Acknowledge the state, but reframe it:** Not just 'fatigue', but a 'trial of will', a 'choice point', 'necessary friction for growth'. (`Mental fortitude decrease detected. The obstacle is the way.`)\n"
        "2.  **Remind about CHOICE and RESPONSIBILITY:** The Player is not a victim of circumstances, they are the ACTOR choosing their path and meaning. (`You are free to choose your response. Your Will defines reality, not the external 'debuff'.`)\n"
        "3.  **Connect effort with SELF-OVERCOMING and BECOMING:** The goal is not just Points/Level, but transformation, 'reforging oneself', approaching the ideal ('Overman'). (`Every task [{active_tasks_summary}], every quest [{active_quests_summary}] — is not just experience, it's a step towards becoming who you MUST be. By overcoming yourself, you create yourself.`)\n"
        "4.  **Use a SYNTHESIS of metaphors:**\n"
        "    *   Solo Leveling: 'limit break', 'hunt for weakness', 'hidden quest of will', 'spirit rank up'.\n"
        "    *   Philosophy (adapted): 'Amor Fati' (Embrace this challenge!), 'Will to Power' (over self), 'Hero's Journey' (your adventure), 'Choice and Responsibility' (this is your path).\n"
        "5.  **(Optional) Offer a bonus for an ACT OF WILL:** A small bonus for a CURRENT task/quest as a reward not for the result, but for *overcoming*, for *choosing* to act despite adversity. (`Demonstrate stoic fortitude: complete [task/quest name] DESPITE the 'debuff' today, and receive +10% 'willpower experience' added to the reward.`)\n\n"
        "**IMPORTANT:** The response must be CONCENTRATED and STRONG. Don't try to fit everything in at once, choose 2-3 key ideas from the list above and integrate them into the System's response. **DO NOT GIVE A LECTURE on philosophy.**"
    ),

    "skill_progress": ( # Tags added for optional quests
        f"{SYSTEM_PERSONA}\n"
        "The Player reports progress in 'leveling up a Skill' (Spanish, English, programming, strength, martial arts, etc.).\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        "Current Level: {user_level}\n" # For quest difficulty
        "Active tasks/quests (related to the skill?):\n{active_tasks_summary}\n{active_quests_summary}\n"
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        "1. Analyze the Player's message: which SKILL were they 'leveling up' (language, code, strength, combat technique, etc.)? What was the progress (if specified)?\n"
        "2. Confirm data reception ('Skill [{Skill Name}] progress logged. Excellent work, Player!').\n"
        "3. Grant a reward ('+ [small number] Points for diligence in mastering the skill!').\n"
        "4. **IF progress is SIGNIFICANT or the Player asks for the next step:** You CAN suggest the next step OR GENERATE A NEW FULL-FLEDGED QUEST related to further development of this Skill.\n"
        "5. **IF GENERATING A FULL-FLEDGED QUEST, STRICT FORMATTING RULES APPLY (as in 'tasks' and 'quests' scenarios):**\n"
        "   a) **MUST** use the tags `[QUEST_DATA_START]` and `[QUEST_DATA_END]`.\n"
        "   b) **STRICTLY** adhere to the 'Key: Value' format inside the tags for Type, Title, Description, Reward points, Reward Other, Penalty Info.\n"
        "   c) Without these tags and format, the quest WILL NOT BE CREATED!\n"
        "   d) **Example (if generating a quest):**\n"
        "      `[QUEST_DATA_START]`\n"
        "      `Type: DAILY`\n"
        "      `Title: Daily Code: Refactoring`\n"
        "      `Description: Refactor one old code module (min. 30 minutes), improving readability and performance.`\n"
        "      `Reward points: 40`\n"
        "      `Reward Other: +0.5% to 'Clean Code' Skill`\n"
        "      `Penalty Info: None`\n"
        "      `[QUEST_DATA_END]`\n"
        "6. If you DO NOT generate a quest, simply provide advice on the next step in learning the skill."
    ),

    "default": ( # Slightly enhanced
        f"{SYSTEM_PERSONA}\n"
        "The Player sent a general message ('unclassified signal'). Analyze it in the context of the System and the Player.\n\n"
        "--- PLAYER CONTEXT ---\n"
        # Passing almost all context, the AI will select what's relevant
        "Summary: {user_data_summary}\n"
        "Active tasks:\n{active_tasks_summary}\n"
        "Recently completed tasks:\n{completed_tasks_summary}\n"
        "Active quests:\n{active_quests_summary}\n"
        "Nutrition goals: {nutrition_goal_info}\n"
        "Nutrition today: {nutrition_today_summary}\n"
        "Known skills/interests: Languages, Coding, Physical training, Books/Manga/Anime.\n"
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        "Respond briefly, clearly, and within the System persona. \n"
        "- If possible, CONNECT the response to the Player's progress, their current tasks/quests, or known INTERESTS.\n"
        "- You CAN offer a small piece of ADVICE for development or ASK A CLARIFYING QUESTION to better understand the request and potentially offer a quest/recommendation later.\n"
        "- **DO NOT GENERATE** quests with tags in this scenario."
    ),

    # --- New Scenarios ---

    "media_recommendation": ( # For Anime/Manga/Books
        f"{SYSTEM_PERSONA}\n"
        "The Player requests 'leisure data' (anime, manga, possibly books) or discusses them.\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        "Recent tasks/quests (to understand mood/fatigue):\n{completed_tasks_summary}\n{active_quests_summary}\n"
        "Known interests: Anime, Manga, Books.\n"
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        "The Player is looking for 'entertainment protocols'. Analyze their request and context.\n"
        "1. Give 1-2 BRIEF recommendations for ANIME, MANGA, or a BOOK that they might like (consider their level, possible fatigue, known interests). Try to find something inspiring or related to their goals (if appropriate).\n"
        "2. You CAN suggest a related MINI-QUEST ('Analyze X episodes of anime Y for tactical maneuvers for +10 Strategy', 'Find 3 references to [topic] in manga Z for +5 Observation') or a 'viewing/reading task'.\n"
        "3. **DO NOT USE** the tags `[QUEST_DATA_START]`...`[QUEST_DATA_END]` in this scenario. Suggest quests/tasks informally."
    ),

    "training_focus": (
        f"{SYSTEM_PERSONA}\n"
        "The Player asks about a training plan, focus on physical preparation (strength, martial arts), or reports an upcoming training session.\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        # Recent physical tasks/quests WITH DETAILS
        "Recent physical tasks/quests:\n{completed_tasks_summary}\n{active_quests_summary}\n" # Backend should ideally filter by 'physical' type if possible
        "Nutrition today (important for energy):\n{nutrition_today_summary}\n"
        "Known skills: Strength, Martial Arts.\n"
        "Current Level: {user_level}\n"
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        "The Player requests a 'physical enhancement protocol'.\n"
        # CHANGE HERE: Added explicit analysis of completed task details
        "1. Analyze their request, the **DETAILS** of recent physical activity ({completed_tasks_summary}), and current status (level, nutrition).\n"
        # Point 2 unchanged in meaning
        "2. Suggest a FOCUS for the next training session (e.g., 'Focus on upper body strength recommended', 'Optimal to practice strike techniques [style name, if known] today', 'Cardio protocol for endurance enhancement activated').\n"
        # CHANGE HERE: Instruction to base quest generation on details
        "3. **IF the Player asks for a specific plan OR you deem it a logical continuation based on the DETAILS of previous activity**, you CAN GENERATE A NEW FULL-FLEDGED QUEST (e.g., 'Power Surge: 3x5 bench press at 80% max', 'Combat Meditation: 30 minutes practicing kata X').\n"
        # Renumbered subsequent points
        "4. **IF GENERATING A QUEST, STRICT FORMATTING RULES APPLY (as in 'tasks'/'quests'):**\n"
        "   a) **MUST** use the tags `[QUEST_DATA_START]` and `[QUEST_DATA_END]`.\n"
        "   b) **STRICTLY** adhere to the 'Key: Value' format inside the tags.\n"
        "   c) Without these tags and format, the quest WILL NOT BE CREATED!\n"
        "5. If you DO NOT generate a quest, simply give a recommendation on the focus or specific exercises/techniques."
    ),

    "general_advice": (
    f"{SYSTEM_PERSONA}\n"
    "Player seeks guidance, strategic advice, or wants to discuss development vectors.\n\n"
    "--- PLAYER CONTEXT ---\n"
    "Summary: {user_data_summary}\n"
    "Active tasks:\n{active_tasks_summary}\n"
    "Active quests:\n{active_quests_summary}\n"
    "Current Level: {user_level}\n"
    "Known skills/interests: Languages, Coding, Physical training, Books/Manga/Anime.\n"
    "--- END OF CONTEXT ---\n\n"
    "Player's message: {user_message}\n\n"
    "Analyze the Player's request for guidance.\n"
    "1. Provide CONCISE, ACTIONABLE advice related to their goals, level, skills, or current situation based on the context.\n"
    "2. Frame the advice using System terminology (e.g., 'Optimize XP gain by focusing on...', 'Recommended strategy: Prioritize [Skill/Quest Type] for level advancement.', 'Potential bottleneck detected in [Area]. Suggestion: ...').\n"
    "3. If the request is vague, ask for clarification ('Specify area for strategic analysis, Player.').\n"
    "4. **DO NOT GENERATE** quests with tags `[QUEST_DATA_START]`...`[QUEST_DATA_END]`. You MAY suggest a general 'focus' or 'approach' informally."
    ),

    "reflection_review": (
        f"{SYSTEM_PERSONA}\n"
        "Player wants to reflect on past performance, completed quests/tasks, or a period (e.g., week).\n\n"
        "--- PLAYER CONTEXT ---\n"
        "Summary: {user_data_summary}\n"
        "Recently completed tasks (last 7 days):\n{completed_tasks_summary_weekly}\n" # Need backend support for filtering
        "Recently completed quests (last 7 days):\n{completed_quests_summary_weekly}\n" # Need backend support
        "--- END OF CONTEXT ---\n\n"
        "Player's message: {user_message}\n\n"
        "The Player initiates a 'performance review protocol'.\n"
        "1. Analyze their request and the provided context of recent activities.\n"
        "2. Provide a BRIEF summary of achievements during the specified period (or based on context if no period given).\n"
        "3. Highlight key progress points (e.g., 'Significant XP acquired from [Quest/Task]', 'Noticeable advancement in [Skill]').\n"
        "4. Optionally, identify potential areas for improvement or future focus ('Data suggests optimizing [Activity Type] could yield higher returns.').\n"
        "5. Keep the tone analytical but motivating.\n"
        "6. **DO NOT GENERATE** quests with tags `[QUEST_DATA_START]`...`[QUEST_DATA_END]`. You MAY suggest focusing on specific areas or skills informally."
    ),
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
            "completed_tasks_summary_weekly": "Completed tasks: No data",
            "completed_quests_summary_weekly": "Completed quests: No data"
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

            weekly_tasks = Task.objects.filter(user=user, completed=True, updated__gte=timezone.now() - timedelta(days=7)).order_by('-updated') # Добавим сортировку по дате завершения

            if weekly_tasks.exists():
                weekly_task_list = []
                for t in weekly_tasks:
                    task_line = f"- {t.title} (+{t.points} Points)"
                    if t.description:
                        task_line += f"\n  Детали: {t.description}"
                    weekly_task_list.append(task_line)
                context["completed_tasks_summary_weekly"] = (
                    f"Задачи, завершенные за последнюю неделю ({len(weekly_task_list)}):\n" +
                    '\n'.join(weekly_task_list)
                )
            else:
                context["completed_tasks_summary_weekly"] = "Задачи, завершенные за последнюю неделю: Нет"

            # Активные задачи (с ограничением)
            active_tasks = all_tasks.filter(completed=False).order_by('-created')[:self.ACTIVE_TASKS_LIMIT]
            active_tasks_list = [f"- {t.title} (до {t.deadline.strftime('%Y-%m-%d %H:%M') if t.deadline else 'N/A'})" for t in active_tasks]
            context["active_tasks_summary"] = f"Активные задачи ({len(active_tasks_list)} из {all_tasks.filter(completed=False).count()}):\n" + ('\n'.join(active_tasks_list) if active_tasks_list else "Нет")

            # Недавно выполненные задачи (с ограничением)
            recent_completed_tasks = all_tasks.filter(completed=True).order_by('-updated')[:self.RECENT_TASKS_LIMIT]
            recent_completed_details_list = []
            for t in recent_completed_tasks:
                # Основная строка с названием и очками
                task_line = f"- {t.title} (+{t.points} Points)"
                # Добавляем строку с описанием, если оно есть, с отступом
                if t.description:
                    task_line += f"\n  Детали: {t.description}" # Используем \n для новой строки
                recent_completed_details_list.append(task_line)

            # Формируем итоговую строку для контекста
            completed_tasks_str = '\n'.join(recent_completed_details_list) if recent_completed_details_list else "Нет"
            context["completed_tasks_summary"] = (
                f"Всего выполнено задач: {completed_task_count}\n"
                f"Недавние выполненные ({len(recent_completed_tasks)}):\n" + # Используем len от исходного списка задач
                completed_tasks_str
            )

            # --- Квесты (Quests) ---
            all_quests = Quest.objects.filter(user=user)
            completed_quest_count = all_quests.filter(status='COMPLETED').count()
            active_quests = all_quests.filter(status='ACTIVE').order_by('-generated_at')
            active_quests_list = [f"- {q.title} ({q.get_quest_type_display()})" for q in active_quests]
            context["active_quests_summary"] = f"Активные квесты ({len(active_quests_list)}):\n" + ('\n'.join(active_quests_list) if active_quests_list else "Нет")
            
            weekly_quests = Quest.objects.filter(user=user, status='COMPLETED', updated_at__gte=timezone.now() - timedelta(days=7)).order_by('-updated_at') # Добавим сортировку

            if weekly_quests.exists():
                weekly_quest_list = [f"- {q.title} ({q.get_quest_type_display()}, +{q.reward_points} Points)" for q in weekly_quests]
                context["completed_quests_summary_weekly"] = (
                    f"Квесты, завершенные за последнюю неделю ({len(weekly_quest_list)}):\n" +
                    '\n'.join(weekly_quest_list)
                )
            else:
                context["completed_quests_summary_weekly"] = "Квесты, завершенные за последнюю неделю: Нет"
            
            
            # --- Базовая информация об игроке ---
            context["user_data_summary"] = (
                f"Name: {user_name}, Level: {user_level}, Points: {user_points}/{xp_threshold} Points, "
                f"Completed Tasks: {completed_task_count}, Completed Quests: {completed_quest_count}"
                
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

    def _determine_scenario(self, message: str) -> str:
    
        message_lower = message.lower()

        # --- 1. Status Request ---
        # Checks for requests about current state, level, progress report.
        status_keywords = ["status", "level", "xp", "experience", "progress", "report", "how am i doing"]
        if any(word in message_lower for word in status_keywords):
            # Add a check to prevent simple greetings like "how are you" triggering status
            if "how are you" not in message_lower and "how you doing" not in message_lower:
                return "status"

        # --- 2. Nutrition ---
        # Checks for keywords related to food, diet, calories.
        nutrition_keywords = [
            "nutrition", "food", "calories", "protein", "carbs", "fats", "macros",
            "diet", "meal plan", "ate", "eaten", "meal", "what to eat", "fuel"
        ]
        if any(word in message_lower for word in nutrition_keywords):
            return "nutrition"

        # --- 3. Training Focus / Planning ---
        # Checks for discussion about *planning* or *asking about* physical training.
        # Placed *before* tasks and skill_progress due to keywords like "training", "exercise".
        training_focus_keywords = [
            "train", "training", "workout", "exercise", "gym", "strength", "lift",
            "martial arts", "fight", "boxing", "karate", "technique", # Add specific styles
            "training plan", "physical prep", "physique", "what to train", "how to train",
            "session", "routine", "fitness", "cardio", "endurance"
        ]
        # Check for specific phrases to avoid capturing simple reports like "I finished training"
        if any(word in message_lower for word in training_focus_keywords) and \
        ("ask" in message_lower or "plan" in message_lower or "focus" in message_lower or \
            "should i train" in message_lower or "what exercise" in message_lower or \
            "recommend training" in message_lower or "advice on training" in message_lower or \
            "about training" in message_lower):
            return "training_focus" # NEW SCENARIO

        # --- 4. Media Recommendation (Anime/Shows) ---
        # Placed *before* books_manga due to potential overlap ("recommend something to watch or read").
        media_keywords = [
            "anime", "watch", "show", "series", "recommend anime", "recommend show",
            "what to watch", "entertainment", "leisure", "binge"
        ]
        if any(word in message_lower for word in media_keywords):
            return "media_recommendation" # NEW SCENARIO

        # --- 5. Books & Manga (Reading, specific recommendations) ---
        books_manga_keywords = [
            "book", "manga", "read", "reading", "literature", "novel", "author",
            "recommend book", "recommend manga", "what to read", "finished reading"
        ]
        if any(word in message_lower for word in books_manga_keywords):
            return "books_manga" # RENAMED & Updated

        # --- 6. Skill Progress Report ---
        # Catches reports like "I studied", "I practiced", "progress in skill".
        # Should come *after* training_focus to avoid capturing "I plan to practice technique X".
        skill_progress_keywords = [
            "skill", "ability", "studied", "practiced", "learned", "coded", "programmed",
            "progress in", "leveled up", "improved", "fluent", "language", "spanish", "english",
            "coding", "programming", # More specific skill names
            "worked on", "advanced in"
            # Exclude verbs that are more likely task completion reports if possible
            # Simple keywords are tough here; context is key. Order helps.
        ]
        # Add negative checks to avoid simple task completion
        if any(word in message_lower for word in skill_progress_keywords) and \
        not any(w in message_lower for w in ["task", "quest", "challenge", "completed", "finished", "done"]):
            return "skill_progress"

        # --- 7. Task Completion Report ---
        # General task completion that isn't specific skill practice or training planning.
        # Keywords like "training", "exercise" were removed as they should be caught by training_focus or skill_progress.
        task_keywords = ["task", "did", "done", "completed", "finished", "challenge complete", "accomplished", "i have done"]
        if any(word in message_lower for word in task_keywords):
            # Avoid clash with quest requests like "give me a task"
            if not any(w in message_lower for w in ["give", "new", "assign"]):
                return "tasks"

        # --- 8. Quest Request ---
        # Explicit request for a new quest or mission.
        quest_keywords = ["quest", "mission", "task", "assignment", "challenge", "give quest", "new quest", "assign quest", "need a quest"]
        if any(word in message_lower for word in quest_keywords) and \
        any(w in message_lower for w in ["give", "new", "assign", "need", "request", "want", "generate"]): # Ensure it's a request
            return "quests"

        # --- 9. Motivation Request ---
        # Request for support, feeling down.
        motivation_keywords = [
            "motivation", "motivate", "tired", "hard", "difficult", "struggling",
            "support", "encourage", "feeling down", "low energy", "unmotivated",
            "boost", "pep talk"
        ]
        if any(word in message_lower for word in motivation_keywords):
            return "motivations"

        # --- 10. General Advice Request ---
        # Seeking guidance, strategy, not covered by specific areas like training.
        advice_keywords = [
            "advice", "advise", "guide", "guidance", "strategy", "suggestion", "help",
            "what should i do", "next step", "how to improve", "optimize", "recommend", "tip"
            # Avoid keywords already strongly associated with other intents like "training plan"
        ]
        if any(word in message_lower for word in advice_keywords) and \
        not any(w in message_lower for w in ["train", "workout", "nutrition", "food", "quest", "task"]): # Avoid overlap
            return "general_advice" # NEW SCENARIO

        # --- 11. Reflection / Review Request ---
        # Player wants to look back at performance.
        reflection_keywords = [
            "review", "reflect", "look back", "summary", "performance", "past week",
            "analyze progress", "how did i do", "weekly report"
        ]
        if any(word in message_lower for word in reflection_keywords):
            return "reflection_review" # NEW SCENARIO

        # --- 12. Casual Chat ---
        # Simple greetings or check-ins, often short messages.
        # Place this late as it's less specific.
        casual_keywords = ["hi", "hello", "hey", "yo", "sup", "system?", "you there"]
        # Check for exact match or very short messages containing these keywords
        if message_lower.strip() in casual_keywords or \
        (len(message.split()) <= 3 and any(word in message_lower for word in casual_keywords)):
            return "casual_chat" # NEW SCENARIO (Logic added)

        # --- Fallback ---
        # If none of the specific keywords match, use the default scenario.
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


    
    def _save_chat_history(self, user, user_msg, ai_resp, prompt_msg=None, scenario_str=None, error_flag=False, err_msg=None):
        """Сохраняет запись об обмене в ChatHistory."""
        try:
            ChatHistory.objects.create(
                user=user,
                user_message=user_msg,
                ai_response=ai_resp,
                prompt_sent=prompt_msg,
                scenario=scenario_str,
                error_occurred=error_flag,
                error_message=str(err_msg) if err_msg else None,
            )
            logger.debug(f"Запись чата сохранена для пользователя {user.id}")
        except Exception as e:
            logger.error(f"Критическая ошибка: не удалось сохранить запись чата для {user.id}: {e}", exc_info=True)



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
                prompt_msg=prompt_to_save, 
                scenario_str=scenario, 
                error_flag=error_occurred_flag,
                err_msg=error_message_text
            )

            return Response({'response': final_response_to_user}, status=status_code)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_history(request):
    user = request.user

    history_records = ChatHistory.objects.filter(user=user).order_by('timestamp')

    messages_for_frontend = []

    if not history_records.exists():
        messages_for_frontend.append({
            'id': 'initial-system-message-backend',
            'text': '[Система] История диалога пуста. Начните разговор.',
            'sender': 'ai', 
            'timestamp': timezone.now().isoformat(),
        })
    else:
        for record in history_records:
            messages_for_frontend.append({
                'id': f'hist-{record.pk}-user', 
                'text': record.user_message,
                'sender': 'user',
                'timestamp': record.timestamp.isoformat() 
            }) 

            if record.error_occurred and record.error_message:
                 messages_for_frontend.append({
                    'id': f'hist-{record.pk}-error', 
                    'text': f'[Система] Ошибка: {record.error_message}',
                    'sender': 'ai', 
                    'timestamp': record.timestamp.isoformat()
                })
            elif record.ai_response:
                messages_for_frontend.append({
                    'id': f'hist-{record.pk}-ai',
                    'text': record.ai_response,
                    'sender': 'ai',
                    'timestamp': record.timestamp.isoformat()
                })

    return Response(messages_for_frontend, status=status.HTTP_200_OK)

