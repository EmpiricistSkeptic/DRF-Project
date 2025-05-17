import logging

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .config import QUEST_START_TAG, QUEST_END_TAG
from .prompts import PROMPT_TEMPLATES
from .context import _get_user_context
from .scenarios import _determine_scenario
from .history import _save_chat_history
from .parser import _parse_and_create_quest
from .caller import _call_ai_service


logger = logging.getLogger(__name__)

class AssistantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # --------------------------------

    _get_user_context = _get_user_context
    _determine_scenario = _determine_scenario
    _call_ai_service = _call_ai_service
    _parse_and_create_quest = _parse_and_create_quest
    _save_chat_history = _save_chat_history



    def post(self, request, *args, **kwargs):
        """
        Обрабатывает POST-запрос с сообщением пользователя к ИИ и сохраняет историю.
        """
        user = request.user
        user_message = request.data.get('message', '').strip()

        prompt_to_save = None
        scenario = None
        ai_response_raw = "[System] A response wasn't generated." # Дефолт, если ИИ не вызван
        final_response_to_user = "[System] Request processing error." 
        error_occurred_flag = False
        error_message_text = None
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        if not user_message:
            final_response_to_user = '[System] An empty message received.'
            error_occurred_flag = True
            error_message_text = "An empty message received from user."
            status_code = status.HTTP_400_BAD_REQUEST
            # Сохраняем запись об ошибке и выходим
            self._save_chat_history(
                user=user,
                user_msg="<EMPTY MESSAGE>", 
                ai_resp=final_response_to_user,
                error_flag=error_occurred_flag,
                err_msg=error_message_text
            )
            return Response({'response': final_response_to_user}, status=status_code)

        try:
            user_context = self._get_user_context(user)

            scenario = self._determine_scenario(user_message)
            template = PROMPT_TEMPLATES.get(scenario, PROMPT_TEMPLATES["default"])

            try:
                prompt = template.format(
                    user_message=user_message,
                    **user_context
                )
                prompt_to_save = prompt
            except KeyError as e:
                 logger.error(f"Prompt formating error for the script '{scenario}': key {e}.")
                 final_response_to_user = '[System] Internal error: failed to prepare data.'
                 error_occurred_flag = True
                 error_message_text = f"Prompt formating error for the script: key {e} is missing."
                 self._save_chat_history(user, user_message, final_response_to_user, prompt_to_save, scenario, error_occurred_flag, error_message_text)
                 return Response({'response': final_response_to_user}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            ai_response_raw = self._call_ai_service(prompt)
            final_response_to_user = ai_response_raw 

            # --- 5. Парсинг и создание квеста (интегрировано) ---
            created_quest = None
            status_code = status.HTTP_200_OK 

            if ai_response_raw.startswith("[System] Error") or ai_response_raw == "[System] Cannot process the request at the moment." or ai_response_raw == "[System] Internal error while processing response.":
                 logger.warning(f"The call AI returned an error for {user.id}, parsing the quest is being skipped.")
                 error_occurred_flag = True 
                 error_message_text = ai_response_raw 
                 status_code = status.HTTP_503_SERVICE_UNAVAILABLE 
            else:
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
                            final_response_to_user = '\n'.join(parts) 
                        else:
                            logger.warning(f"Quest block found but not processed for {user.id}. The AI's response remains unchanged.")

                except Exception as e:
                     logger.error(f"Error while parsing the quest block for {user.id}: {e}", exc_info=True)
                     
                     error_occurred_flag = True 
                     error_message_text = (error_message_text + "\n" if error_message_text else "") + f"Quest parsing error: {e}"


            # --- 6. Сохраняем в историю чата (перед возвратом) ---
            self._save_chat_history(
                user=user,
                user_msg=user_message,
                ai_resp=final_response_to_user,
                prompt_msg=prompt_to_save,
                scenario_str=scenario,
                error_flag=error_occurred_flag,
                err_msg=error_message_text
            )

            # 7. Возвращаем финальный ответ пользователю
            return Response({'response': final_response_to_user}, status=status_code)

        except Exception as e:
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