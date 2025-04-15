import logging 

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
        """
        Этот метод определяет базовый набор данных для ViewSet.
        Мы фильтруем задачи, чтобы возвращать ТОЛЬКО те,
        которые принадлежат текущему аутентифицированному пользователю.
        Это ключевой момент для безопасности и разделения данных.
        """
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