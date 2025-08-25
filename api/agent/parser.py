from .config import QUEST_EXPECTED_KEYS
import logging
from api.models import Quest
from django.db import transaction

logger = logging.getLogger(__name__)


def _parse_and_create_quest(text_block, user):
    """
    Парсит блок текста с данными квеста и создает объект Quest.
    Возвращает созданный объект Quest или None в случае ошибки.
    (Версия из предыдущего ответа)
    """
    quest_data = {}
    lines = text_block.strip().splitlines()

    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in QUEST_EXPECTED_KEYS:
            quest_data[key] = value

    if not all(
        k in quest_data for k in ["type", "title", "description", "reward points"]
    ):
        logger.warning(f"Parsing the quest: missing required fields: {text_block}")
        return None

    try:
        valid_quest_types = [choice[0] for choice in Quest.QUEST_TYPES]
        parsed_type = quest_data.get("type", "").upper()
        if parsed_type not in valid_quest_types:
            logger.warning(
                f"Parsing the quest: unacceptable type '{parsed_type}', using CHALLENGE."
            )
            parsed_type = "CHALLENGE"

        model_data = {
            "user": user,
            "title": quest_data.get("title", "Quest without a title"),
            "description": quest_data.get("description", ""),
            "quest_type": parsed_type,
            "reward_points": int(quest_data.get("reward points", 0)),
            "reward_other": quest_data.get("reward other", None),
            "penalty_info": quest_data.get("penalty info", None),
        }
        if not model_data["reward_other"] or model_data["reward_other"].lower() == "no":
            model_data["reward_other"] = None
        if not model_data["penalty_info"] or model_data["penalty_info"].lower() == "no":
            model_data["penalty_info"] = None

    except ValueError:
        logger.error(
            f"Parsing the quest: conversion error reward points in number: {quest_data.get('reward points')}"
        )
        return None
    except Exception as e:
        logger.error(
            f"Parsing quest: unexpected data preparation error: {e}", exc_info=True
        )
        return None

    try:
        with transaction.atomic():
            new_quest = Quest.objects.create(**model_data)
        logger.info(
            f"Created quest ID {new_quest.id} '{new_quest.title}' for {user.username}"
        )
        return new_quest
    except Exception as e:
        logger.error(
            f"Error creating the quest in DB for {user.id}: {e}", exc_info=True
        )
        return None
