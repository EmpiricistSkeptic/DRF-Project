import logging 

from rest_framework import viewsets, mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Task, Quest, Profile, UserHabit, Friendship, Notification, User
from .serializers import TaskSerializer, QuestSerializer, ProfileSerializer, UserHabitSerializer, FriendshipSerializer

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
    permission_classes = [IsAuthenticated]  # Права доступа применяются ко всем действиям ViewSet

    def get_queryset(self):
        
        user = self.request.user
        # Логируем, для какого пользователя запрашиваются задачи
        logger.debug(f"Запрос queryset задач для пользователя: {user.username}")
        # Возвращаем только задачи текущего пользователя
        queryset = Task.objects.filter(user=user)
        # Логируем количество найденных задач (может быть полезно для отладки)
        # Уровень INFO - менее подробный, чем DEBUG
        logger.info(f"Найден queryset из {queryset.count()} задач для пользователя {user.username}")
        return queryset

    def list(self, request, *args, **kwargs):
        """
        Переопределяем стандартный метод list, чтобы по умолчанию
        возвращать только НЕЗАВЕРШЕННЫЕ задачи пользователя,
        как это было в оригинальной вью-функции tasksView.
        """
        # Получаем базовый queryset (уже отфильтрованный по пользователю в get_queryset)
        queryset = self.get_queryset().filter(completed=False)
        logger.info(f"Фильтрация списка задач: показ только невыполненных для {request.user.username}")

        # Стандартная логика list из DRF (включая пагинацию, если настроена)
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
        # Логируем успешное создание задачи
        logger.info(
            f"Пользователь {self.request.user.username} создал задачу id={instance.id}: '{instance.title[:30]}...'"
        )
        # Не нужно возвращать Response, DRF сделает это сам

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
        user = self.request.user # Получаем пользователя до удаления
        instance.delete()
        # Используем уровень WARNING для потенциально деструктивных операций
        logger.warning(
            f"Пользователь {user.username} УДАЛИЛ задачу id={task_id}: '{task_title[:30]}...'"
        )

    @action(detail=True, methods=['put'], name='Complete Task')
    # detail=True: Действие выполняется для конкретного объекта (нужен pk в URL)
    # methods=['put']: Реагирует на PUT-запросы
    # name: Имя для отображения в Browsable API DRF
    def complete(self, request, pk=None):
        """
        Помечает задачу как выполненную и начисляет очки/уровень пользователю.
        """
        # get_object() автоматически найдет задачу по pk И проверит права доступа
        # через get_queryset(), выбросив 404 если не найдено или не принадлежит юзеру.
        task = self.get_object()

        # Проверка, не выполнена ли задача уже
        if task.completed:
            logger.warning(f"Попытка повторно завершить уже выполненную задачу id={task.id} пользователем {request.user.username}")
            # Можно вернуть ошибку или просто текущее состояние задачи
            serializer = self.get_serializer(task) # Используем get_serializer для консистентности
            return Response(
                {"detail": "Task is already completed.", "task": serializer.data},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Используем транзакцию, чтобы обновление задачи и профиля были атомарны
        # Либо обе операции пройдут успешно, либо ни одна не сохранится.
        try:
            with transaction.atomic():
                # 1. Обновляем задачу
                task.completed = True
                task.save()
                logger.info(f"Задача id={task.id} помечена как выполненная пользователем {request.user.username}")

                # 2. Обновляем профиль пользователя
                # Убедись, что у модели User есть связь с Profile (обычно OneToOneField)
                # и доступ к ней через request.user.profile
                try:
                    profile = request.user.profile # или task.user.profile
                except AttributeError:
                    # Обработка случая, если профиля нет (хотя он должен быть для этой логики)
                    logger.error(f"Не найден профиль для пользователя {request.user.username} при завершении задачи id={task.id}")
                    # Откатываем транзакцию (произойдет автоматически при выходе из try с ошибкой)
                    # и возвращаем ошибку сервера
                    return Response({"error": "User profile not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


                original_points = profile.points
                original_level = profile.level

                profile.points += task.points # Используем task.points

                # Логика повышения уровня (оставляем твою)
                xp_threshold = int(1000 * (1.5 ** (profile.level - 1))) # Используй int(), если xp_threshold должен быть целым
                while profile.points >= xp_threshold:
                    profile.level += 1
                    profile.points -= xp_threshold
                    xp_threshold = int(1000 * (1.5 ** (profile.level - 1))) # Пересчитываем для следующего уровня

                profile.save()
                logger.info(
                    f"Обновлен профиль пользователя {request.user.username}: "
                    f"Очки {original_points} -> {profile.points}, "
                    f"Уровень {original_level} -> {profile.level}"
                )

        except Exception as e:
            # Логируем непредвиденную ошибку во время транзакции
            logger.exception(f"Ошибка при завершении задачи id={task.id} пользователем {request.user.username}: {e}")
            return Response({"error": "An error occurred while completing the task."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Возвращаем обновленную задачу
        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], name='List Completed Tasks')
    # detail=False: Действие относится ко всему списку, а не к одной задаче (нет pk)
    # methods=['get']: Реагирует на GET-запросы
    def completed(self, request, *args, **kwargs):
        """
        Возвращает список выполненных задач текущего пользователя.
        Доступно по GET /api/tasks/completed/
        """
        queryset = self.get_queryset().filter(completed=True) # Фильтруем по ВЫПОЛНЕННЫМ
        logger.info(f"Запрос списка ВЫПОЛНЕННЫХ задач для {request.user.username}")

        # Логика пагинации и сериализации (такая же, как в list)
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
                # 1. Блокируем и получаем профиль
                try:
                    # Попытка получить профиль, связанный с пользователем квеста
                    profile = Profile.objects.select_for_update().get(user=quest_to_complete.user)
                except Profile.DoesNotExist:
                     # Это не должно происходить, если у каждого пользователя есть профиль
                     logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: Профиль для пользователя {quest_to_complete.user.username} (id={quest_to_complete.user.id}) не найден при попытке завершить квест {quest_to_complete.id}.")
                     return Response({"detail": "Профиль пользователя не найден."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


                # 2. Обновляем квест
                quest_to_complete.status = 'COMPLETED'
                quest_to_complete.completed_at = timezone.now()
                # Не сохраняем сразу, сохраним в конце транзакции, если награды начислятся

                # 3. Начисляем очки и обрабатываем уровень
                reward_points = quest_to_complete.reward_points
                original_points = profile.points # Сохраняем для логирования
                original_level = profile.level   # Сохраняем для логирования

                if reward_points > 0:
                    profile.points += reward_points
                    logger.info(f"Игроку {user.username} начислено {reward_points} Points за квест '{quest_to_complete.title}'. Очки до: {original_points}, после: {profile.points}")

                    # Логика повышения уровня
                    xp_threshold = int(1000 * (1.5 ** (profile.level - 1)))
                    if xp_threshold <= 0: xp_threshold = 1000 # Защита

                    leveled_up = False
                    while profile.points >= xp_threshold:
                        leveled_up = True
                        profile.points -= xp_threshold
                        profile.level += 1
                        logger.info(f"Игрок {user.username} ДОСТИГ УРОВНЯ {profile.level}!")
                        # Пересчитываем порог для НОВОГО уровня
                        xp_threshold = int(1000 * (1.5 ** (profile.level - 1)))
                        if xp_threshold <= 0: xp_threshold = 1000 + (profile.level -1) * 500 # Защита/альтернатива

                    if leveled_up:
                         logger.info(f"Обновлен профиль {user.username} после левел-апа: Уровень {original_level}->{profile.level}, Очки {original_points}->{profile.points}.")

                # Сохраняем и квест, и профиль в конце атомарной операции
                quest_to_complete.save()
                profile.save()

                logger.info(f"Квест id={quest_to_complete.id} '{quest_to_complete.title[:30]}...' успешно завершен пользователем {user.username}.")

            # Транзакция прошла успешно
            # Используем self.get_serializer() для получения сериализатора с контекстом
            serializer = self.get_serializer(quest_to_complete)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            # Ловим другие ошибки внутри транзакции
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
        user = self.request.user # Получаем пользователя до удаления
        instance.delete()
        # Используем уровень WARNING для потенциально деструктивных операций
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
                        "detail": "Habit has already been tracked today.",
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

        # Fetch the pending request outside the transaction first
        friendship = get_object_or_404(
            Friendship,
            user__id=sender_id,
            friend=request.user,
            status='PENDING'
        )

        # Store the sender user object before deleting the friendship request
        sender_user = friendship.user

        try:
            with transaction.atomic():
                # Delete the pending request
                friendship.delete()

                # Create the established friendship record (assuming this is your model logic)
                # If your logic involves updating the existing record or creating two records, adjust accordingly.
                Friendship.objects.create(
                    user=request.user,
                    friend=sender_user, # Use the stored user object
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

        # Store the sender user object before deleting the friendship request
        sender_user = friendship.user
        friendship_id_for_log = friendship.id # Store ID for logging in case of error

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






            

