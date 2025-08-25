import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from api.models import (
    Profile,
    Task,
    Quest,
    ConsumedCalories,
    UserNutritionGoal,
    UserHabit,
)

logger = logging.getLogger(__name__)


def _get_user_context(user):
    """
    Собирает расширенный контекст пользователя для ИИ, включая:
    - Профиль (уровень, очки, порог)
    - Статистику по задачам (всего выполнено, активные, недавние выполненные)
    - Цели по питанию
    - Сводку по питанию за сегодня
    - Недавние приемы пищи
    - Статистику по квестам (всего выполнено, активные)
    """

    RECENT_TASKS_LIMIT = 35
    RECENT_FOOD_LIMIT = 20
    ACTIVE_TASKS_LIMIT = 15
    ACTIVE_HABITS_LIMIT = 15

    context = {
        "user_data_summary": "Status: Error loading data",
        "active_tasks_summary": "Active tasks: No data",
        "completed_tasks_summary": "Completed tasks: No data",
        "nutrition_goal_info": "Nutritional Goals: No data",
        "nutrition_today_summary": "Today's Meals: No data",
        "nutrition_recent_history": "Recent meals: No data",
        "active_quests_summary": "Active Quests: No data",
        "user_level": 1,
        "completed_tasks_summary_weekly": "Completed tasks: No data",
        "completed_quests_summary_weekly": "Completed quests: No data",
        "active_habits_streak_summary": "Active habits: No data",
    }
    try:
        profile = Profile.objects.select_related("user").get(user=user)
        user_name = profile.user.username
        user_level = profile.level
        user_points = profile.points

        level_decimal = Decimal(profile.level - 1)
        xp_threshold_decimal = Decimal(1000) * (Decimal(1.5) ** level_decimal)
        xp_threshold = int(
            xp_threshold_decimal.to_integral_value(rounding=ROUND_HALF_UP)
        )
        if xp_threshold <= 0:
            xp_threshold = 1000

        # --- Задачи (Tasks) ---
        all_tasks = Task.objects.filter(user=user)
        completed_task_count = all_tasks.filter(completed=True).count()

        weekly_tasks = (
            Task.objects.select_related("category", "unit_type")
            .filter(
                user=user,
                completed=True,
                updated__gte=timezone.now() - timedelta(days=7),
            )
            .order_by("-updated")
        )

        if weekly_tasks.exists():
            weekly_task_list = []
            for t in weekly_tasks:
                # Add category information if available
                category_info = f" [{t.category.name}]" if t.category else ""

                # Add unit information if available
                unit_info = ""
                if t.unit_type and t.unit_amount > 0:
                    unit_info = f" ({t.unit_amount} {t.unit_type.symbol})"

                task_line = (
                    f"- {t.title}{category_info}{unit_info} (+{t.points} Points)"
                )
                if t.description:
                    task_line += f"\n  Details: {t.description}"
                weekly_task_list.append(task_line)
            context["completed_tasks_summary_weekly"] = (
                f"Tasks completed in the last week ({len(weekly_task_list)}):\n"
                + "\n".join(weekly_task_list)
            )
        else:
            context["completed_tasks_summary_weekly"] = (
                "Tasks completed in the last week: None"
            )

        # Активные задачи (с ограничением)
        active_tasks = (
            all_tasks.select_related("category", "unit_type")
            .filter(completed=False)
            .order_by("-updated")[:ACTIVE_TASKS_LIMIT]
        )

        active_tasks_list = []
        for t in active_tasks:
            # Add category information if available
            category_info = f" [{t.category.name}]" if t.category else ""

            # Add unit information if available
            unit_info = ""
            if t.unit_type and t.unit_amount > 0:
                unit_info = f" ({t.unit_amount} {t.unit_type.symbol})"

            deadline_info = (
                f" (until {t.deadline.strftime('%Y-%m-%d %H:%M')})"
                if t.deadline
                else " (no deadline)"
            )
            active_tasks_list.append(
                f"- {t.title}{category_info}{unit_info}{deadline_info}"
            )

        context["active_tasks_summary"] = (
            f"Active tasks ({len(active_tasks_list)} from {all_tasks.filter(completed=False).count()}):\n"
            + ("\n".join(active_tasks_list) if active_tasks_list else "No active tasks")
        )

        # Недавно выполненные задачи (с ограничением)
        recent_completed_tasks = (
            all_tasks.select_related("category", "unit_type")
            .filter(completed=True)
            .order_by("-updated")[:RECENT_TASKS_LIMIT]
        )

        recent_completed_details_list = []
        for t in recent_completed_tasks:
            # Add category information if available
            category_info = f" [{t.category.name}]" if t.category else ""

            # Add unit information if available
            unit_info = ""
            if t.unit_type and t.unit_amount > 0:
                unit_info = f" ({t.unit_amount} {t.unit_type.symbol})"

            task_line = f"- {t.title}{category_info}{unit_info} (+{t.points} Points)"
            if t.description:
                task_line += f"\n  Details: {t.description}"
            recent_completed_details_list.append(task_line)

        completed_tasks_str = (
            "\n".join(recent_completed_details_list)
            if recent_completed_details_list
            else "Нет"
        )
        context["completed_tasks_summary"] = (
            f"Total tasks completed: {completed_task_count}\n"
            f"Recently completed ({len(recent_completed_tasks)}):\n"
            + completed_tasks_str
        )

        # --- Квесты (Quests) ---
        all_quests = Quest.objects.filter(user=user)
        completed_quest_count = all_quests.filter(status="COMPLETED").count()
        active_quests = all_quests.filter(status="ACTIVE").order_by("-generated_at")
        active_quests_list = [
            f"- {q.title} ({q.get_quest_type_display()})" for q in active_quests
        ]
        context["active_quests_summary"] = (
            f"Active quests ({len(active_quests_list)}):\n"
            + ("\n".join(active_quests_list) if active_quests_list else "No")
        )

        weekly_quests = Quest.objects.filter(
            user=user,
            status="COMPLETED",
            updated_at__gte=timezone.now() - timedelta(days=7),
        ).order_by(
            "-updated_at"
        )  # Добавим сортировку

        if weekly_quests.exists():
            weekly_quest_list = [
                f"- {q.title} ({q.get_quest_type_display()}, +{q.reward_points} Points)"
                for q in weekly_quests
            ]
            context["completed_quests_summary_weekly"] = (
                f"Quests completed in the last week ({len(weekly_quest_list)}):\n"
                + "\n".join(weekly_quest_list)
            )
        else:
            context["completed_quests_summary_weekly"] = (
                "Quests completed in the last week: None"
            )

        # --- Habits ---
        all_active_habits = UserHabit.objects.filter(
            user=user, is_active=True
        ).order_by("-streak", "created_at")[:ACTIVE_HABITS_LIMIT]
        all_active_habits_list = []

        for h in all_active_habits:
            habit_line = f"- {h.title} (Streak: {h.streak} days, Frequency: {h.get_frequency_display()})"
            if h.description:
                habit_line += f"\n  Details: {h.description}"

            if h.last_tracked:
                habit_line += f"\n  Last tracked: {h.last_tracked.strftime('%Y-%m-%d')}"

            all_active_habits_list.append(habit_line)

        context["active_habits_streak_summary"] = (
            f"Active habits with streaks ({len(all_active_habits_list)}):\n"
            + ("\n".join(all_active_habits_list) if all_active_habits_list else "None")
        )

        # --- Базовая информация об игроке ---
        context["user_data_summary"] = (
            f"Name: {user_name}, Level: {user_level}, Points: {user_points}/{xp_threshold} Points, "
            f"Completed Tasks: {completed_task_count}, Completed Quests: {completed_quest_count}, "
            f"Active Habits: {all_active_habits.count()}"
        )
        context["user_level"] = user_level

        # --- Питание ---
        today = timezone.now().date()
        all_consumed = ConsumedCalories.objects.filter(user=user)

        try:
            goal = UserNutritionGoal.objects.get(user=user)
            context["nutrition_goal_info"] = (
                f"Goals PFCC: {goal.calories_goal:.0f} kkal, "
                f"{goal.proteins_goal:.0f}g P, {goal.fats_goal:.0f}g F, {goal.carbs_goal:.0f}g C"
            )
        except UserNutritionGoal.DoesNotExist:
            context["nutrition_goal_info"] = "Nutritional Goals: Not established"

        today_consumed_agg = all_consumed.filter(consumed_at__date=today).aggregate(
            total_calories=Sum("calories", default=0),
            total_proteins=Sum("proteins", default=0),
            total_fats=Sum("fats", default=0),
            total_carbs=Sum("carbs", default=0),
        )
        calories_today = today_consumed_agg.get("total_calories") or 0
        proteins_today = today_consumed_agg.get("total_proteins") or 0
        fats_today = today_consumed_agg.get("total_fats") or 0
        carbs_today = today_consumed_agg.get("total_carbs") or 0

        if (
            calories_today > 0
            or proteins_today > 0
            or fats_today > 0
            or carbs_today > 0
        ):
            context["nutrition_today_summary"] = (
                f"Nutrition today: {calories_today:.0f} kkal, "
                f"{proteins_today:.1f}g P, {fats_today:.1f}g F, {carbs_today:.1f}g C"
            )
        else:
            context["nutrition_today_summary"] = "Today's Meals: No data"

        recent_food_items = all_consumed.order_by("-consumed_at").values(
            "product_name",
            "weight",
            "calories",
            "proteins",
            "fats",
            "carbs",
            "consumed_at",
        )[:RECENT_FOOD_LIMIT]

        if recent_food_items:
            food_history_list = []
            for item in recent_food_items:
                time_str = item["consumed_at"].strftime("%Y-%m-%d %H:%M")
                food_history_list.append(
                    f"- [{time_str}] {item['product_name']} ({item['weight']:.0f}g): "
                    f"{item['calories']:.0f} kkal "
                    f"(P:{item['proteins']:.1f} F:{item['fats']:.1f} C:{item['carbs']:.1f})"
                )
            context["nutrition_recent_history"] = (
                f"Recent meals ({len(food_history_list)}):\n"
                + "\n".join(food_history_list)
            )
        else:
            context["nutrition_recent_history"] = "Recent Meals: No entries"

        return context

    except Profile.DoesNotExist:
        logger.error(f"Profile for {user.id} not found.")
        context["user_data_summary"] = "Status: Profile not found"
        return context
    except Exception as e:
        logger.error(f"Error getting context for user {user.id}: {e}", exc_info=True)
        context["user_data_summary"] = "Status: Error loading data"
        return context
