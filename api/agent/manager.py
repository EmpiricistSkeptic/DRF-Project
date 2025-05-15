import logging, requests
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from django.db.models import Sum

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .config import AI_API_ENDPOINT, AI_API_KEY, QUEST_START_TAG, QUEST_END_TAG, QUEST_EXPECTED_KEYS
from .prompts import PROMPT_TEMPLATES, SYSTEM_PERSONA
from api.models import Profile, Task, Quest, ConsumedCalories, UserNutritionGoal, ChatHistory



logger = logging.getLogger(__name__)

class AssistantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    RECENT_TASKS_LIMIT = 35
    RECENT_FOOD_LIMIT = 20
    # Сколько активных задач показать?
    ACTIVE_TASKS_LIMIT = 15
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
            "user_data_summary": "Status: Error loading data",
            "active_tasks_summary": "Active tasks: No data",
            "completed_tasks_summary": "Completed tasks: No data",
            "nutrition_goal_info": "Nutritional Goals: No data",
            "nutrition_today_summary": "Today's Meals: No data",
            "nutrition_recent_history": "Recent meals: No data",
            "active_quests_summary": "Active Quests: No data",
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
                        task_line += f"\n  Details: {t.description}"
                    weekly_task_list.append(task_line)
                context["completed_tasks_summary_weekly"] = (
                    f"Tasks completed in the last week ({len(weekly_task_list)}):\n" +
                    '\n'.join(weekly_task_list)
                )
            else:
                context["completed_tasks_summary_weekly"] = "Tasks completed in the last week: None"

            # Активные задачи (с ограничением)
            active_tasks = all_tasks.filter(completed=False).order_by('-created')[:self.ACTIVE_TASKS_LIMIT]
            active_tasks_list = [f"- {t.title} (untill {t.deadline.strftime('%Y-%m-%d %H:%M') if t.deadline else 'N/A'})" for t in active_tasks]
            context["active_tasks_summary"] = f"Active tasks ({len(active_tasks_list)} from {all_tasks.filter(completed=False).count()}):\n" + ('\n'.join(active_tasks_list) if active_tasks_list else "No")

            # Недавно выполненные задачи (с ограничением)
            recent_completed_tasks = all_tasks.filter(completed=True).order_by('-updated')[:self.RECENT_TASKS_LIMIT]
            recent_completed_details_list = []
            for t in recent_completed_tasks:
                # Основная строка с названием и очками
                task_line = f"- {t.title} (+{t.points} Points)"
                # Добавляем строку с описанием, если оно есть, с отступом
                if t.description:
                    task_line += f"\n  Details: {t.description}" # Используем \n для новой строки
                recent_completed_details_list.append(task_line)

            # Формируем итоговую строку для контекста
            completed_tasks_str = '\n'.join(recent_completed_details_list) if recent_completed_details_list else "Нет"
            context["completed_tasks_summary"] = (
                f"Total tasks completed: {completed_task_count}\n"
                f"Recently completed ({len(recent_completed_tasks)}):\n" + # Используем len от исходного списка задач
                completed_tasks_str
            )

            # --- Квесты (Quests) ---
            all_quests = Quest.objects.filter(user=user)
            completed_quest_count = all_quests.filter(status='COMPLETED').count()
            active_quests = all_quests.filter(status='ACTIVE').order_by('-generated_at')
            active_quests_list = [f"- {q.title} ({q.get_quest_type_display()})" for q in active_quests]
            context["active_quests_summary"] = f"Active quests ({len(active_quests_list)}):\n" + ('\n'.join(active_quests_list) if active_quests_list else "No")
            
            weekly_quests = Quest.objects.filter(user=user, status='COMPLETED', updated_at__gte=timezone.now() - timedelta(days=7)).order_by('-updated_at') # Добавим сортировку

            if weekly_quests.exists():
                weekly_quest_list = [f"- {q.title} ({q.get_quest_type_display()}, +{q.reward_points} Points)" for q in weekly_quests]
                context["completed_quests_summary_weekly"] = (
                    f"Quests completed in the last week ({len(weekly_quest_list)}):\n" +
                    '\n'.join(weekly_quest_list)
                )
            else:
                context["completed_quests_summary_weekly"] = "Quests completed in the last week: None"
            
            
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
                    f"Goals PFCC: {goal.calories_goal:.0f} kkal, "
                    f"{goal.proteins_goal:.0f}g P, {goal.fats_goal:.0f}g F, {goal.carbs_goal:.0f}g C"
                )
            except UserNutritionGoal.DoesNotExist:
                context["nutrition_goal_info"] = "Nutritional Goals: Not established"

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
                     f"Nutrition today: {calories_today:.0f} kkal, "
                     f"{proteins_today:.1f}g P, {fats_today:.1f}g F, {carbs_today:.1f}g C"
                )
            else:
                 context["nutrition_today_summary"] = "Today's Meals: No data"

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
                         f"- [{time_str}] {item['product_name']} ({item['weight']:.0f}g): "
                         f"{item['calories']:.0f} kkal "
                         f"(P:{item['proteins']:.1f} F:{item['fats']:.1f} C:{item['carbs']:.1f})"
                     )
                context["nutrition_recent_history"] = f"Recent meals ({len(food_history_list)}):\n" + '\n'.join(food_history_list)
            else:
                context["nutrition_recent_history"] = "Recent Meals: No entries"

            return context

        except Profile.DoesNotExist:
            logger.error(f"Profile for {user.id} not found.")
            # Возвращаем дефолтные значения с сообщением об ошибке
            context["user_data_summary"] = "Status: Profile not found"
            return context
        except Exception as e:
            logger.error(f"Error getting context for user {user.id}: {e}", exc_info=True)
            # Возвращаем дефолтные значения с сообщением об общей ошибке
            context["user_data_summary"] = "Status: Error loading data"
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
                logger.warning(f"AI returned empty response. Payload (patrially): {payload.get('messages')}")
                return "[System] I cannot process the request at the moment."

            # Добавляем префикс, если ИИ его не добавил
            if not ai_text.startswith("[System]"):
                ai_text = f"[System] {ai_text}"

            return ai_text

        except requests.exceptions.RequestException as e:
            logger.error(f"Call error AI API ({AI_API_ENDPOINT}): {e}")
            return "[System] Connection error via the AI server. Please, Try again later."
        except Exception as e:
            logger.error(f"Unexpected error while processing the response: {e}")
            return "[System] Internal error while handling your request."

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
             logger.warning(f"Parsing the quest: missing required fields: {text_block}")
             return None

        try:
            valid_quest_types = [choice[0] for choice in Quest.QUEST_TYPES]
            parsed_type = quest_data.get('type', '').upper()
            if parsed_type not in valid_quest_types:
                 logger.warning(f"Parsing the quest: unacceptable type '{parsed_type}', using CHALLENGE.")
                 parsed_type = 'CHALLENGE'

            model_data = {
                'user': user,
                'title': quest_data.get('title', 'Quest without a title'),
                'description': quest_data.get('description', ''),
                'quest_type': parsed_type,
                'reward_points': int(quest_data.get('reward points', 0)),
                'reward_other': quest_data.get('reward other', None),
                'penalty_info': quest_data.get('penalty info', None),
            }
            if not model_data['reward_other'] or model_data['reward_other'].lower() == 'no':
                model_data['reward_other'] = None
            if not model_data['penalty_info'] or model_data['penalty_info'].lower() == 'no':
                model_data['penalty_info'] = None

        except ValueError:
             logger.error(f"Parsing the quest: conversion error reward points in number: {quest_data.get('reward points')}")
             return None
        except Exception as e:
            logger.error(f"Parsing quest: unexpected data preparation error: {e}", exc_info=True)
            return None

        try:
            # Используем transaction.atomic для гарантии целостности
            with transaction.atomic():
                 new_quest = Quest.objects.create(**model_data)
            logger.info(f"Created quest ID {new_quest.id} '{new_quest.title}' for {user.username}")
            return new_quest
        except Exception as e:
            logger.error(f"Error creating the quest in DB for {user.id}: {e}", exc_info=True)
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
            logger.debug(f"The chat history has been saved for the user {user.id}")
        except Exception as e:
            logger.error(f"A critical error occured while trying to save the chat record for {user.id}: {e}", exc_info=True)



    def post(self, request, *args, **kwargs):
        """
        Обрабатывает POST-запрос с сообщением пользователя к ИИ и сохраняет историю.
        """
        user = request.user
        user_message = request.data.get('message', '').strip()

        # --- Инициализация переменных для сохранения ---
        prompt_to_save = None
        scenario = None
        ai_response_raw = "[System] A response wasn't generated." # Дефолт, если ИИ не вызван
        final_response_to_user = "[System] Request processing error." # Дефолт для пользователя
        error_occurred_flag = False
        error_message_text = None
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR # Дефолтный статус ошибки

        if not user_message:
            final_response_to_user = '[System] An empty message received.'
            error_occurred_flag = True
            error_message_text = "An empty message received from user."
            status_code = status.HTTP_400_BAD_REQUEST
            # Сохраняем запись об ошибке и выходим
            self._save_chat_history(
                user=user,
                user_msg="<EMPTY MESSAGE>", # Или сам user_message, если нужно
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
                 logger.error(f"Prompt formating error for the script '{scenario}': key {e}.")
                 final_response_to_user = '[System] Internal error: failed to prepare data.'
                 error_occurred_flag = True
                 error_message_text = f"Prompt formating error for the script: key {e} is missing."
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
            if ai_response_raw.startswith("[System] Error") or ai_response_raw == "[System] Cannot process the request at the moment." or ai_response_raw == "[System] Internal error while processing response.":
                 logger.warning(f"The call AI returned an error for {user.id}, parsing the quest is being skipped.")
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
                            confirmation_message = f"[System] The new quest '{new_quest_object.title}' has been added to your journal."
                            parts = [part for part in [response_before_quest, confirmation_message, response_after_quest] if part]
                            final_response_to_user = '\n'.join(parts) # Обновляем ответ для пользователя
                        else:
                            logger.warning(f"Quest block found but not processed for {user.id}. The AI's response remains unchanged.")
                            # Можно добавить к error_message_text информацию о неудачном парсинге, но не считать это критической ошибкой
                            # error_message_text = (error_message_text + "\n" if error_message_text else "") + "Ошибка парсинга блока квеста."

                except Exception as e:
                     logger.error(f"Error while parsing the quest block for {user.id}: {e}", exc_info=True)
                     # Оставляем final_response_to_user как ai_response_raw
                     # Отмечаем, что была ошибка, но не обязательно критическая для всего ответа
                     error_occurred_flag = True # Считаем ошибкой, т.к. ожидаемый парсинг не удался
                     error_message_text = (error_message_text + "\n" if error_message_text else "") + f"Quest parsing error: {e}"


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
            logger.error(f"Unexpected global error in AssistantAPIView.post for {user.id}: {e}", exc_info=True)
            final_response_to_user = "[System] An internal server error occurred."
            error_occurred_flag = True
            error_message_text = f"Global error: {e}"
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