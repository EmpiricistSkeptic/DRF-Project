import os, logging
logger = logging.getLogger(__name__)
AI_API_ENDPOINT = os.getenv('AI_API_ENDPOINT')
AI_API_KEY = os.getenv('AI_API_KEY')

if not AI_API_ENDPOINT:
    logger.critical("Переменная окружения AI_API_ENDPOINT не установлена!")

if not AI_API_KEY:
    logger.critical("Переменная окружения AI_API_KEY не установлена!")


QUEST_START_TAG = "[QUEST_DATA_START]"
QUEST_END_TAG = "[QUEST_DATA_END]"
QUEST_EXPECTED_KEYS = ['type', 'title', 'description', 'reward points', 'reward other', 'penalty info']