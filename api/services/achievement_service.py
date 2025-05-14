from django.db.models import F
from django.utils import timezone
from api.models import Achievement, UserAchievement

class AchievementService:
    @staticmethod
    def register_user_achievements(user):
        """
        Создает записи UserAchievement для всех доступных достижений
        при регистрации нового пользователя
        """
        
        achievements = Achievement.objects.all()
        
        user_achievements = [
            UserAchievement(
                user=user,
                achievement=achievement,
                current_progress=0,
                current_tier='BRONZE',
            )
            for achievement in achievements
        ]
        
        UserAchievement.objects.bulk_create(user_achievements)
    
    @staticmethod
    def update_achievements_on_task_completion(user, task):
        """
        Обновляет прогресс достижений при выполнении задачи
        """
        
        if not task.category or not task.unit_type or task.unit_amount <= 0:
            return
            
        user_achievements = UserAchievement.objects.filter(
            user=user,
            achievement__category=task.category,
            achievement__unit_type=task.unit_type,
            completed=False
        )
        
        for user_achievement in user_achievements:
            user_achievement.update_progress(task.unit_amount)
            
    @staticmethod
    def get_achievements_progress(user):
        """
        Возвращает прогресс пользователя по всем достижениям
        """
        
        user_achievements = UserAchievement.objects.filter(user=user).select_related('achievement')
        
        progress_data = []
        for ua in user_achievements:
            achievement = ua.achievement
            
            next_tier = None
            next_requirement = None
            
            if ua.current_tier == 'BRONZE':
                next_tier = 'SILVER'
                next_requirement = achievement.silver_requirement
            elif ua.current_tier == 'SILVER':
                next_tier = 'GOLD'
                next_requirement = achievement.gold_requirement
            elif ua.current_tier == 'GOLD':
                next_tier = 'PLATINUM'
                next_requirement = achievement.platinum_requirement
            elif ua.current_tier == 'PLATINUM':
                next_tier = 'DIAMOND'
                next_requirement = achievement.diamond_requirement
                
            progress_data.append({
                'id': ua.id,
                'name': achievement.name,
                'description': achievement.description,
                'icon': achievement.icon.url if achievement.icon else None,
                'current_progress': ua.current_progress,
                'current_tier': ua.current_tier,
                'next_tier': next_tier,
                'next_requirement': next_requirement,
                'progress_percentage': min(100, int((ua.current_progress / next_requirement) * 100)) if next_requirement else 100,
                'completed': ua.completed,
                'completed_at': ua.completed_at,
            })
            
        return progress_data
            


        
