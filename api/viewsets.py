import logging
from datetime import timedelta
from django.utils import timezone
from django.utils.timezone import now

from django.db.models.functions import TruncDate
from django.db.models import (
    Q,
    Case,
    When,
    F,
    Max,
    Subquery,
    OuterRef,
    ForeignKey,
    Q,
    Count,
    DateField,
    F,
    Sum,
)
from django.db import models



from rest_framework import viewsets, mixins, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from .models import Task, Quest, Profile, UserHabit, Friendship, Notification, User, Message, Group, GroupMessage, ConsumedCalories, UserNutritionGoal, Achievement, UserAchievement, Category, UnitType
from .serializers import TaskSerializer, QuestSerializer, ProfileSerializer, UserHabitSerializer, FriendshipSerializer, MessageSerializer, GroupMessageSerializer, GroupSerializer, NotificationSerializer, ConsumedCaloriesSerializer, UserNutritionGoalSerializer, UserAchievementSerializer, AchievementSerializer, UnitTypeSerializer, CategorySerializer
from .permissions import IsGroupHost
from .services.achievement_service import AchievementService

logger = logging.getLogger(__name__)

class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления задачами (Task).

    Предоставляет эндпоинты для:
    - list: Получение списка невыполненных задач текущего пользователя.
    - retrieve: Получение конкретной задачи по ID (только для владельца).
    - create: Создание новой задачи для текущего пользователя.
    - update: Полное обновление задачи по ID (только для владельца).
    - partial_update: Частичное обновление задачи по ID (только для владельца).
    - destroy: Удаление задачи по ID (только для владельца).
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated] 

    def get_queryset(self):
        
        user = self.request.user
        logger.debug(f"Запрос queryset задач для пользователя: {user.username}")
        queryset = Task.objects.filter(user=user)
        logger.info(f"Найден queryset из {queryset.count()} задач для пользователя {user.username}")
        return queryset

    def list(self, request, *args, **kwargs):
        """
        Переопределяем стандартный метод list, чтобы по умолчанию
        возвращать только НЕЗАВЕРШЕННЫЕ задачи пользователя,
        как это было в оригинальной вью-функции tasksView.
        """
        queryset = self.get_queryset().filter(completed=False)
        logger.info(f"Фильтрация списка задач: показ только невыполненных для {request.user.username}")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            logger.debug(f"Возвращается пагинированный список невыполненных задач для {request.user.username}")
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        logger.debug(f"Возвращается полный список невыполненных задач для {request.user.username}")
        return Response(serializer.data)

    def perform_create(self, serializer):
        """
        Переопределяем метод для автоматического присвоения
        текущего пользователя создаваемой задаче.
        Вызывается перед сохранением сериализатора в методе create.
        """
        instance = serializer.save(user=self.request.user)
        logger.info(
            f"Пользователь {self.request.user.username} создал задачу id={instance.id}: '{instance.title[:30]}...'"
        )

    def perform_update(self, serializer):
        """
        Переопределяем для логирования.
        Вызывается перед сохранением сериализатора в методах update и partial_update.
        """
        instance = serializer.save()
        logger.info(
            f"Пользователь {self.request.user.username} обновил задачу id={instance.id}: '{instance.title[:30]}...'"
        )

    def perform_destroy(self, instance):
        """
        Переопределяем для логирования перед удалением.
        Вызывается перед удалением объекта в методе destroy.
        """
        task_id = instance.id
        task_title = instance.title
        user = self.request.user 
        instance.delete()
        logger.warning(
            f"Пользователь {user.username} УДАЛИЛ задачу id={task_id}: '{task_title[:30]}...'"
        )

    
    @action(detail=True, methods=['put'], url_path='complete')
    def complete(self, request, pk=None):
        """
        Помечает задачу как выполненную и начисляет очки/уровень пользователю.
        """
        print(f"Complete action called with method: {request.method}") 

        if request.method == 'OPTIONS':
            return Response(status=status.HTTP_200_OK)
        
        task = self.get_object()
        if task.completed:
            logger.warning(f"Попытка повторно завершить уже выполненную задачу id={task.id} пользователем {request.user.username}")
            serializer = self.get_serializer(task)
            return Response(
                {"detail": "Task is already completed.", "task": serializer.data},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            with transaction.atomic():
                task.completed = True
                task.save()
                logger.info(f"Задача id={task.id} помечена как выполненная пользователем {request.user.username}")
            
                try:
                    profile = request.user.profile
                except AttributeError:
                    logger.error(f"Не найден профиль для пользователя {request.user.username} при завершении задачи id={task.id}")
                    return Response({"error": "User profile not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
                original_points = profile.points
                original_level = profile.level
                profile.points += task.points 
                xp_threshold = int(1000 * (1.5 ** (profile.level - 1)))
                while profile.points >= xp_threshold:
                    profile.level += 1
                    profile.points -= xp_threshold
                    xp_threshold = int(1000 * (1.5 ** (profile.level - 1)))
                profile.save()
                logger.info(
                    f"Обновлен профиль пользователя {request.user.username}: "
                    f"Очки {original_points} -> {profile.points}, "
                    f"Уровень {original_level} -> {profile.level}"
                )
        except Exception as e:
            logger.exception(f"Ошибка при завершении задачи id={task.id} пользователем {request.user.username}: {e}")
            return Response({"error": "An error occurred while completing the task."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], name='List Completed Tasks')
    def completed(self, request, *args, **kwargs):
        """
        Возвращает список выполненных задач текущего пользователя.
        Доступно по GET /api/tasks/completed/
        """
        queryset = self.get_queryset().filter(completed=True)
        logger.info(f"Запрос списка ВЫПОЛНЕННЫХ задач для {request.user.username}")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            logger.debug(f"Возвращается пагинированный список ВЫПОЛНЕННЫХ задач для {request.user.username}")
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        logger.debug(f"Возвращается полный список ВЫПОЛНЕННЫХ задач для {request.user.username}")
        return Response(serializer.data)


class QuestViewSet(viewsets.ReadOnlyModelViewSet): 
    """
    ViewSet ТОЛЬКО для ПРОСМОТРА квестов (Quest).

    Предоставляет эндпоинты для:
    - list: Получение списка квестов текущего пользователя.
    - retrieve: Получение конкретного квеста по ID (только для владельца).

    Создание, обновление и удаление квестов через этот API НЕ предполагается.
    """
    serializer_class = QuestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Критически важно: Возвращает ТОЛЬКО квесты текущего пользователя.
        Это гарантирует, что пользователь сможет видеть только свои квесты
        как в списке (list), так и при запросе по ID (retrieve).
        """
        user = self.request.user
        logger.debug(f"Запрос queryset квестов для пользователя: {user.username}")
        return Quest.objects.filter(user=user)
    
    
    @action(detail=True, methods=['patch'], url_path='complete', name='Complete Quest')
    def complete(self, request, pk=None):
        """
        Помечает АКТИВНЫЙ квест как выполненный, обновляет профиль пользователя.
        Доступно по PATCH /api/quests/{pk}/complete/
        """
        user = self.request.user

        quest_to_complete = self.get_object()
        if quest_to_complete.status != 'ACTIVE':
            logger.warning(f"Попытка завершить неактивный квест id={pk} пользователем {user.username}. Статус: {quest_to_complete.status}")
            return Response(
                {"detail": f"Квест неактивен (статус: {quest_to_complete.status}) и не может быть завершен."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                try:
                    profile = Profile.objects.select_for_update().get(user=quest_to_complete.user)
                except Profile.DoesNotExist:
                     logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: Профиль для пользователя {quest_to_complete.user.username} (id={quest_to_complete.user.id}) не найден при попытке завершить квест {quest_to_complete.id}.")
                     return Response({"detail": "Профиль пользователя не найден."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


                quest_to_complete.status = 'COMPLETED'
                quest_to_complete.completed_at = timezone.now()

                reward_points = quest_to_complete.reward_points
                original_points = profile.points 
                original_level = profile.level 

                if reward_points > 0:
                    profile.points += reward_points
                    logger.info(f"Игроку {user.username} начислено {reward_points} Points за квест '{quest_to_complete.title}'. Очки до: {original_points}, после: {profile.points}")

                    xp_threshold = int(1000 * (1.5 ** (profile.level - 1)))
                    if xp_threshold <= 0: xp_threshold = 1000 # Защита

                    leveled_up = False
                    while profile.points >= xp_threshold:
                        leveled_up = True
                        profile.points -= xp_threshold
                        profile.level += 1
                        logger.info(f"Игрок {user.username} ДОСТИГ УРОВНЯ {profile.level}!")
                        xp_threshold = int(1000 * (1.5 ** (profile.level - 1)))
                        if xp_threshold <= 0: xp_threshold = 1000 + (profile.level -1) * 500 

                    if leveled_up:
                         logger.info(f"Обновлен профиль {user.username} после левел-апа: Уровень {original_level}->{profile.level}, Очки {original_points}->{profile.points}.")

                quest_to_complete.save()
                profile.save()

                logger.info(f"Квест id={quest_to_complete.id} '{quest_to_complete.title[:30]}...' успешно завершен пользователем {user.username}.")

            serializer = self.get_serializer(quest_to_complete)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Ошибка при завершении квеста {pk} для пользователя {user.username} внутри транзакции: {e}")
            return Response(
                {"detail": "Не удалось завершить квест из-за внутренней ошибки."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HabitViewSet(viewsets.ModelViewSet):

    serializer_class = UserHabitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        logger.debug(f"Запрос queryset привычек для пользователя: {user.username}")

        queryset = UserHabit.objects.filter(user=user)
        logger.info(f"Найден queryset из {queryset.count()} привычек для пользователя {user.username}")

        return queryset
    
    def list(self, request, *args, **kwargs):

        queryset = self.get_queryset().filter(is_active=True)
        logger.info(f"Фильтрация списка привычек: показ только активных для {request.user.username}")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            logger.debug(f"Возвращается пагинированный список активных привычек для {request.user.username}")
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        logger.debug(f"Возвращается полный список активных привычек для {request.user.username}")
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        logger.info(f"Пользователь {request.user.username} запросил задачу id={instance.id}")
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def perform_create(self, serializer):

        instance = serializer.save(user=self.request.user)
        logger.info(
            f"Пользователь {self.request.user.username} создал привычку id={instance.id}: '{instance.title[:30]}...'"
        )

    def perform_update(self, serializer):

        instance = serializer.save()
        logger.info(
            f"Пользователь {self.request.user.username} обновил привычку id={instance.id}: '{instance.title[:30]}...'"
        )

    def perform_destroy(self, instance):

        habit_id = instance.id
        habit_title = instance.title
        user = self.request.user 
        instance.delete()
        logger.warning(
            f"Пользователь {user.username} УДАЛИЛ привычку id={habit_id}: '{habit_title[:30]}...'"
        )

    @action(detail=True, methods=['post'], url_path='track')
    def track(self, request, pk=None):

        habit = self.get_object()

        try:
            tracked = habit.track_habit()

            if tracked:
                logger.info(
                    f"User '{request.user.username}' successfully tracked "
                    f"habit '{habit.title}' (ID: {habit.id}). Current streak: {habit.streak}"
                )
                return Response(
                    {
                        "detail": "Habit tracked successfully!",
                        "streak": habit.streak,
                        "last_tracked": habit.last_tracked
                    },
                    status=status.HTTP_200_OK
                )
            else:
                logger.warning(
                    f"User '{request.user.username}' tried to track already tracked "
                    f"habit '{habit.title}' (ID: {habit.id}) today."
                )
                return Response(
                    {
                        "detail": "Habit has already been tracked today!",
                        "streak": habit.streak,
                        "last_tracked": habit.last_tracked
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(
                f"Failed to track habit (ID: {habit.id}) for user '{request.user.username}'. Error: {e}",
                exc_info=True
            )
            return Response(
                {"detail": "An unexpected error occurred while tracking the habit."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProfileViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)

    def get_object(self):
        return self.request.user.profile

    def retrieve(self, request, *args, **kwargs):
        logger.info(f"Пользователь {request.user.username} запросил свой профиль")
        return super().retrieve(request, *args, **kwargs)

    def perform_update(self, serializer):
        instance = serializer.save()
        logger.info(
            f"Профиль пользователя {self.request.user.username} обновлён: "
            f"username={instance.user.username}, bio={instance.bio[:30]}..."
        )



class FriendshipViewSet(viewsets.ViewSet):
    """
    ViewSet для отправки, принятия и отклонения запросов в друзья.
    Регистрируется в роутере как:
        router.register(r'friendship', FriendshipViewSet, basename='friendship')
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FriendshipSerializer

    @action(detail=True, methods=['post'], url_path='send')
    def send(self, request, pk=None):
        """
        POST /friendship/{pk}/send/
        Отправить запрос в друзья пользователю с id=pk
        """
        user_id = int(pk)
        if request.user.id == user_id:
            return Response(
                {"detail": "You can't send a friend request to yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )

        recipient = get_object_or_404(User, id=user_id)

        if Friendship.objects.filter(user=request.user, friend=recipient).exists() or \
           Friendship.objects.filter(user=recipient, friend=request.user).exists():
            return Response(
                {"detail": "Friendship or request already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            with transaction.atomic():
                friendship = Friendship.objects.create(
                    user=request.user,
                    friend=recipient,
                    status='PENDING'
                )
                Notification.objects.create(
                    user=recipient,
                    notification_type='friend_request',
                    message=f"{request.user.username} sent you a friend request."
                )
        except Exception as e:
            logger.error(f"Error sending friend request from {request.user.id} to {user_id}: {e}", exc_info=True)
            return Response(
                {"detail": "An error occurred while sending the friend request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        serializer = self.serializer_class(friendship)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

        

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        try:
            sender_id = int(pk)
        except (ValueError, TypeError):
            return Response(
                 {"detail": "Invalid user ID format."},
                 status=status.HTTP_400_BAD_REQUEST
             )

        friendship = get_object_or_404(
            Friendship,
            user__id=sender_id,
            friend=request.user,
            status='PENDING'
        )

        sender_user = friendship.user

        try:
            with transaction.atomic():
                friendship.delete()

                Friendship.objects.create(
                    user=request.user,
                    friend=sender_user, 
                    status='FRIEND'
                )
                Notification.objects.create(
                    user=friendship.user,
                    notification_type='friend_request_accepted',
                    message=f"{request.user.username} accepted your friend request"
                )

        except Exception as e:
            logger.error(f"Error accepting friend request id {friendship.id} by user {request.user.id}: {e}", exc_info=True)
            return Response(
                {"detail": "An error occurred while accepting the friend request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"detail": "Friend request accepted"},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        try:
            sender_id = int(pk)
        except (ValueError, TypeError):
             return Response(
                 {"detail": "Invalid user ID format."},
                 status=status.HTTP_400_BAD_REQUEST
             )

        friendship = get_object_or_404(
            Friendship,
            user__id=sender_id,
            friend=request.user,
            status='PENDING'
        )

        sender_user = friendship.user
        friendship_id_for_log = friendship.id 

        try:
            with transaction.atomic():
                friendship.delete()

                Notification.objects.create(
                    user=sender_user, 
                    notification_type='friend_request_rejected',
                    message=f"{request.user.username} rejected your friend request."
                )
        except Exception as e:
            logger.error(f"Error rejecting friend request id {friendship_id_for_log} by user {request.user.id}: {e}", exc_info=True)
            return Response(
                {"detail": "An error occurred while rejecting the friend request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"detail": "Friend request rejected"},
            status=status.HTTP_200_OK
        )


class MessageViewSet(viewsets.ModelViewSet):

    queryset = Message.objects.select_related('sender', 'recipient').all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(
        Q(sender=user) | Q(recipient=user)
    ).select_related('sender', 'recipient').order_by('-timestamp')
    
    def perform_create(self, serializer):
        with transaction.atomic():
            message = serializer.save(sender=self.request.user)
            Notification.objects.create(
                user=message.recipient,
                notification_type='message',
                message=f"You have a new message from {message.sender.username}."
            )

    @action(detail=False, methods=['get'])
    def inbox(self, request):
        qs = self.get_queryset().filter(recipient=request.user, is_read=False).order_by('-timestamp')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
    

    @action(detail=False, methods=['get'])
    def outbox(self, request):
        qs = self.get_queryset().filter(sender=request.user)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
    

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        msg = self.get_object()
        if msg.recipient != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        msg.is_read = True
        msg.save(update_fields=['is_read'])
        return Response(self.get_serializer(msg).data)


    @action(detail=False, methods=['get'])
    def threads(self, request):
        """
        Список диалогов: для каждого собеседника — время и текст последнего сообщения.
        """
        user = request.user
        threads = (
            Message.objects
            .filter(Q(sender=user) | Q(recipient=user))
            .annotate(
                other=Case(
                    When(sender=user, then=F('recipient')),
                    When(recipient=user, then=F('sender')),
                    output_field=ForeignKey(User, on_delete=models.CASCADE)
                )
            )
            .values('other')
            .annotate(
                last_timestamp=Max('timestamp'),
                last_content=Subquery(
                    Message.objects.filter(
                        Q(sender=user, recipient=OuterRef('other')) |
                        Q(sender=OuterRef('other'), recipient=user)
                    ).order_by('-timestamp').values('content')[:1]
                )
            )
            .order_by('-last_timestamp')
        )
        return Response(threads)
    
    @action(detail=False, methods=['get'])
    def thread(self, request):
        """
        Конкретный диалог с user_id из ?with=<id>
        """
        other_id = request.query_params.get('with')
        user = request.user
        qs = Message.objects.filter(
            Q(sender=user, recipient_id=other_id) |
            Q(sender_id=other_id, recipient=user)
        ).order_by('timestamp')
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        return page and self.get_paginated_response(serializer.data) or Response(serializer.data)


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, IsGroupHost]

    def get_queryset(self):
        return Group.objects.filter(members=self.request.user)


    def perform_create(self, serializer):
        group = serializer.save(created_by=self.request.user)
        group.members.add(self.request.user)


    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        group = self.get_object()
        group.members.add(request.user)
        return Response({'status': 'joined'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        group = self.get_object()
        group.members.remove(request.user)
        return Response({'status': 'left'}, status=status.HTTP_200_OK)


class GroupMessageViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        group = get_object_or_404(Group, id=self.kwargs['group_id'])
        if self.reqeust.user not in group.members.all():
            raise PermissionDenied('You are not a member of this group')
        return GroupMessage.objects.filter(group=group)

    def perform_create(self, serializer):
        group = get_object_or_404(Group, id=self.kwargs['group_id'])
        if self.request.user not in group.members.all():
            raise PermissionDenied('You are not a member of this group')
        serializer.save(group=group, sender=self.request.user)



class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]


    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')


    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save(updated_fields=['is_read'])
        return Response({'status': 'marked as read'}, status=status.HTTP_200_OK)


    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        qs = self.get_queryset().filter(is_read=False).count()
        updated = qs.updated(is_read=True)
        return Response({'marked_count'}, updated)


    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count'}, count)


class ConsumedCaloriesViewSet(viewsets.ModelViewSet):
    queryset = ConsumedCalories.objects.all()
    serializer_class = ConsumedCaloriesSerializer
    permission_classes = [IsAuthenticated]
    lookup_id = 'id'


def get_queryset(self):
    return ConsumedCalories.objects.filter(user=self.request.user)


@action(detail=False, methods=['get'], url_path=r'by-days/(?P<period>week|month)')
def by_days(self, request, period=None):
    today = now().date()
    if period == 'week':
        start = today - timedelta(days=7)
    else:
        start = today - timedelta(days=30)

    records = (
        self.get_queryset()
        .filter(consumed_at__date__gte=start)
        .annotate(date=TruncDate('consumed_at'))
        .values('date')
        .annotate(
            total_calories=Sum('calories'),
            total_proteins=Sum('proteins'),
            total_fats=Sum('fats'),
            total_carbs=Sum('carbs')
        )
        .order_by('date')
    )
    return Response(records)


@action(detail=False, methods=['get'], url_path='summary')
def summary(self, request):
    today = now().date()

    daily = self.get_queryset().filter(consumed_at__date=today).aggregate(
        total_calories=Sum('calories'),
        total_proteins=Sum('proteins'),
        total_fats=Sum('fats'),
        total_carbs=Sum('carbs')
    )
    for k, v in daily.items():
        daily[k] = v or 0

    try:
        goals_obj = UserNutritionGoal.objects.get(user=request.user)
        goals = UserNutritionGoalSerializer(goals_obj).data
    except UserNutritionGoal.DoesNotExist:
        goals = {
            'calories_goal': 1800,
            'proteins_goal': 50,
            'fats_goal': 70,
            'carbs_goal': 300,
        }
    meals = self.get_queryset().filter(consumed_at__date=today).order_by('-consumed_at')
    meals_data = ConsumedCaloriesSerializer(meals, many=True).data

    response = {
        **daily,
        **goals,
        'meals': meals_data,
        'remaining': {
            'calories': goals['calories_goal'] - daily['total_calories'],
            'proteins': goals['proteins_goal'] - daily['total_proteins'],
            'fats': goals['fats_goal'] - daily['total_fats'],
            'carbs': goals['carbs_goal'] - daily['total_carbs']
        }
    }
    return Response(response)


class UserNutritionGoalViewSet(
    viewsets.GenericViewSet,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin
):
    serializer_class = UserNutritionGoalSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, created = UserNutritionGoal.objects.get_or_create(
            user=self.request.user,
            defaults={
                'calories_goal': 2000,
                'proteins_goal': 50,
                'fats_goal': 70,
                'carbs_goal': 260,
            }
        )
        return obj  


    def perform_update(self, serializer):
        serializer.save(user=self.request.user)



class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, IsGroupHost]

    def get_queryset(self):
        return Group.objects.filter(members=self.request.user)


    def perform_create(self, serializer):
        group = serializer.save(created_by=self.request.user)
        group.members.add(self.request.user)


    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        group = self.get_object()
        group.members.add(request.user)
        return Response({'status': 'joined'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        group = self.get_object()
        group.members.remove(request.user)
        return Response({'status': 'left'}, status=status.HTTP_200_OK)


class GroupMessageViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        group = get_object_or_404(Group, id=self.kwargs['group_id'])
        if self.reqeust.user not in group.members.all():
            raise PermissionDenied('You are not a member of this group')
        return GroupMessage.objects.filter(group=group)


    def perform_create(self, serializer):
        group = get_object_or_404(Group, id=self.kwargs['group_id'])
        if self.request.user not in group.members.all():
            raise PermissionDenied('You are not a member of this group')
        serializer.save(group=group, sender=self.request.user)



class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]


    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')


    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save(updated_fields=['is_read'])
        return Response({'status': 'marked as read'}, status=status.HTTP_200_OK)


    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        qs = self.get_queryset().filter(is_read=False).count()
        updated = qs.updated(is_read=True)
        return Response({'marked_count'}, updated)


    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count'}, count)


class ConsumedCaloriesViewSet(viewsets.ModelViewSet):
    queryset = ConsumedCalories.objects.all()
    serializer_class = ConsumedCaloriesSerializer
    permission_classes = [IsAuthenticated]
    lookup_id = 'id'


def get_queryset(self):
    return ConsumedCalories.objects.filter(user=self.request.user)


@action(detail=False, methods=['get'], url_path=r'by-days/(?P<period>week|month)')
def by_days(self, request, period=None):
    today = now().date()
    if period == 'week':
        start = today - timedelta(days=7)
    else:
        start = today - timedelta(days=30)

    records = (
        self.get_queryset()
        .filter(consumed_at__date__gte=start)
        .annotate(date=TruncDate('consumed_at'))
        .values('date')
        .annotate(
            total_calories=Sum('calories'),
            total_proteins=Sum('proteins'),
            total_fats=Sum('fats'),
            total_carbs=Sum('carbs')
        )
        .order_by('date')
    )
    return Response(records)


@action(detail=False, methods=['get'], url_path='summary')
def summary(self, request):
    today = now().date()

    daily = self.get_queryset().filter(consumed_at__date=today).aggregate(
        total_calories=Sum('calories'),
        total_proteins=Sum('proteins'),
        total_fats=Sum('fats'),
        total_carbs=Sum('carbs')
    )
    for k, v in daily.items():
        daily[k] = v or 0

    try:
        goals_obj = UserNutritionGoal.objects.get(user=request.user)
        goals = UserNutritionGoalSerializer(goals_obj).data
    except UserNutritionGoal.DoesNotExist:
        goals = {
            'calories_goal': 1800,
            'proteins_goal': 50,
            'fats_goal': 70,
            'carbs_goal': 300,
        }
    meals = self.get_queryset().filter(consumed_at__date=today).order_by('-consumed_at')
    meals_data = ConsumedCaloriesSerializer(meals, many=True).data

    response = {
        **daily,
        **goals,
        'meals': meals_data,
        'remaining': {
            'calories': goals['calories_goal'] - daily['total_calories'],
            'proteins': goals['proteins_goal'] - daily['total_proteins'],
            'fats': goals['fats_goal'] - daily['total_fats'],
            'carbs': goals['carbs_goal'] - daily['total_carbs']
        }
    }
    return Response(response)


class UserNutritionGoalViewSet(
    viewsets.GenericViewSet,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin
):
    serializer_class = UserNutritionGoalSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, created = UserNutritionGoal.objects.get_or_create(
            user=self.request.user,
            defaults={
                'calories_goal': 2000,
                'proteins_goal': 50,
                'fats_goal': 70,
                'carbs_goal': 260,
            }
        )
        return obj  


    def perform_update(self, serializer):
        serializer.save(user=self.request.user)


class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра шаблонов достижений
    """
    
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description', 'category__name']


class UserAchievementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserAchievementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserAchievement.objects.filter(user=self.request.user)
    

    @action(detail=False, methods=['get'])
    def progress(self):
        """
        Получение прогресса всех достижений пользователя в удобном формате
        """
        progress_data = AchievementService.get_achievement_progress(self.request.user)
        return Response(progress_data)

    
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра категорий задач
    """
     
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]


class UnitTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра типов единиц измерения
    """
    queryset = UnitType.objects.all()
    serializer_class = UnitTypeSerializer
    permission_classes = [IsAuthenticated]


     


