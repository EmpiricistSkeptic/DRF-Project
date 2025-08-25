def _determine_scenario(message: str) -> str:

    message_lower = message.lower()

    # --- 1. Status Request ---
    # Checks for requests about current state, level, progress report.
    status_keywords = [
        "status",
        "level",
        "xp",
        "experience",
        "progress",
        "report",
        "how am i doing",
    ]
    if any(word in message_lower for word in status_keywords):
        # Add a check to prevent simple greetings like "how are you" triggering status
        if "how are you" not in message_lower and "how you doing" not in message_lower:
            return "status"

    # --- 2. Nutrition ---
    # Checks for keywords related to food, diet, calories.
    nutrition_keywords = [
        "nutrition",
        "food",
        "calories",
        "protein",
        "carbs",
        "fats",
        "macros",
        "diet",
        "meal plan",
        "ate",
        "eaten",
        "meal",
        "what to eat",
        "fuel",
    ]
    if any(word in message_lower for word in nutrition_keywords):
        return "nutrition"

    # --- 3. Training Focus / Planning ---
    # Checks for discussion about *planning* or *asking about* physical training.
    # Placed *before* tasks and skill_progress due to keywords like "training", "exercise".
    training_focus_keywords = [
        "train",
        "training",
        "workout",
        "exercise",
        "gym",
        "strength",
        "lift",
        "martial arts",
        "fight",
        "boxing",
        "karate",
        "technique",  # Add specific styles
        "training plan",
        "physical prep",
        "physique",
        "what to train",
        "how to train",
        "session",
        "routine",
        "fitness",
        "cardio",
        "endurance",
    ]
    # Check for specific phrases to avoid capturing simple reports like "I finished training"
    if any(word in message_lower for word in training_focus_keywords) and (
        "ask" in message_lower
        or "plan" in message_lower
        or "focus" in message_lower
        or "should i train" in message_lower
        or "what exercise" in message_lower
        or "recommend training" in message_lower
        or "advice on training" in message_lower
        or "about training" in message_lower
    ):
        return "training_focus"  # NEW SCENARIO

    # --- 4. Media Recommendation (Anime/Shows) ---
    # Placed *before* books_manga due to potential overlap ("recommend something to watch or read").
    media_keywords = [
        "anime",
        "watch",
        "show",
        "series",
        "recommend anime",
        "recommend show",
        "what to watch",
        "entertainment",
        "leisure",
        "binge",
    ]
    if any(word in message_lower for word in media_keywords):
        return "media_recommendation"  # NEW SCENARIO

    # --- 5. Books & Manga (Reading, specific recommendations) ---
    books_manga_keywords = [
        "book",
        "manga",
        "read",
        "reading",
        "literature",
        "novel",
        "author",
        "recommend book",
        "recommend manga",
        "what to read",
        "finished reading",
    ]
    if any(word in message_lower for word in books_manga_keywords):
        return "books_manga"  # RENAMED & Updated

    # --- 6. Skill Progress Report ---
    # Catches reports like "I studied", "I practiced", "progress in skill".
    # Should come *after* training_focus to avoid capturing "I plan to practice technique X".
    skill_progress_keywords = [
        "skill",
        "ability",
        "studied",
        "practiced",
        "learned",
        "coded",
        "programmed",
        "progress in",
        "leveled up",
        "improved",
        "fluent",
        "language",
        "spanish",
        "english",
        "coding",
        "programming",  # More specific skill names
        "worked on",
        "advanced in",
        # Exclude verbs that are more likely task completion reports if possible
        # Simple keywords are tough here; context is key. Order helps.
    ]
    # Add negative checks to avoid simple task completion
    if any(word in message_lower for word in skill_progress_keywords) and not any(
        w in message_lower
        for w in ["task", "quest", "challenge", "completed", "finished", "done"]
    ):
        return "skill_progress"

    # --- 7. Task Completion Report ---
    # General task completion that isn't specific skill practice or training planning.
    # Keywords like "training", "exercise" were removed as they should be caught by training_focus or skill_progress.
    task_keywords = [
        "task",
        "did",
        "done",
        "completed",
        "finished",
        "challenge complete",
        "accomplished",
        "i have done",
    ]
    if any(word in message_lower for word in task_keywords):
        # Avoid clash with quest requests like "give me a task"
        if not any(w in message_lower for w in ["give", "new", "assign"]):
            return "tasks"

    # --- 8. Quest Request ---
    # Explicit request for a new quest or mission.
    quest_keywords = [
        "quest",
        "mission",
        "task",
        "assignment",
        "challenge",
        "give quest",
        "new quest",
        "assign quest",
        "need a quest",
    ]
    if any(word in message_lower for word in quest_keywords) and any(
        w in message_lower
        for w in ["give", "new", "assign", "need", "request", "want", "generate"]
    ):  # Ensure it's a request
        return "quests"

    # --- 9. Motivation Request ---
    # Request for support, feeling down.
    motivation_keywords = [
        "motivation",
        "motivate",
        "tired",
        "hard",
        "difficult",
        "struggling",
        "support",
        "encourage",
        "feeling down",
        "low energy",
        "unmotivated",
        "boost",
        "pep talk",
    ]
    if any(word in message_lower for word in motivation_keywords):
        return "motivations"

    # --- 10. General Advice Request ---
    # Seeking guidance, strategy, not covered by specific areas like training.
    advice_keywords = [
        "advice",
        "advise",
        "guide",
        "guidance",
        "strategy",
        "suggestion",
        "help",
        "what should i do",
        "next step",
        "how to improve",
        "optimize",
        "recommend",
        "tip",
        # Avoid keywords already strongly associated with other intents like "training plan"
    ]
    if any(word in message_lower for word in advice_keywords) and not any(
        w in message_lower
        for w in ["train", "workout", "nutrition", "food", "quest", "task"]
    ):  # Avoid overlap
        return "general_advice"  # NEW SCENARIO

    # --- 11. Reflection / Review Request ---
    # Player wants to look back at performance.
    reflection_keywords = [
        "review",
        "reflect",
        "look back",
        "summary",
        "performance",
        "past week",
        "analyze progress",
        "how did i do",
        "weekly report",
    ]
    if any(word in message_lower for word in reflection_keywords):
        return "reflection_review"  # NEW SCENARIO

    # --- 12. Casual Chat ---
    # Simple greetings or check-ins, often short messages.
    # Place this late as it's less specific.
    casual_keywords = ["hi", "hello", "hey", "yo", "sup", "system?", "you there"]
    # Check for exact match or very short messages containing these keywords
    if message_lower.strip() in casual_keywords or (
        len(message.split()) <= 3
        and any(word in message_lower for word in casual_keywords)
    ):
        return "casual_chat"  # NEW SCENARIO (Logic added)

    # --- Fallback ---
    # If none of the specific keywords match, use the default scenario.
    return "default"
