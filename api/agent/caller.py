from .config import AI_API_ENDPOINT, AI_API_KEY
from .prompts import SYSTEM_PERSONA
import requests
import logging


logger = logging.getLogger(__name__)


def _call_ai_service(prompt):
    """Выполняет вызов внешнего ИИ API."""

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PERSONA},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 400,
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            AI_API_ENDPOINT, headers=headers, json=payload, timeout=15
        )
        response.raise_for_status()
        response_data = response.json()

        ai_text = (
            response_data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not ai_text:
            logger.warning(
                f"AI returned empty response. Payload (patrially): {payload.get('messages')}"
            )
            return "[System] I cannot process the request at the moment."

        if not ai_text.startswith("[System]"):
            ai_text = f"[System] {ai_text}"

        return ai_text

    except requests.exceptions.RequestException as e:
        logger.error(f"Call error AI API ({AI_API_ENDPOINT}): {e}")
        return "[System] Connection error via the AI server. Please, Try again later."
    except Exception as e:
        logger.error(f"Unexpected error while processing the response: {e}")
        return "[System] Internal error while handling your request."
