import logging 

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction

from .models import Task
from .serializers import TaskSerializer

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