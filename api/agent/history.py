import logging
from api.models import ChatHistory


logger = logging.getLogger(__name__)


def _save_chat_history(user, user_msg, ai_resp, prompt_msg=None, scenario_str=None, error_flag=False, err_msg=None):
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