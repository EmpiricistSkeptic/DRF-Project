from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import Achievement, Category, UnitType

class Command(BaseCommand):
    help = 'Create initial achievement data'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Creating categories...'))
        
        categories = {
            'english': Category.objects.get_or_create(
                name='English',
                defaults={'description': 'Learning English language'}
            )[0],
            'fitness': Category.objects.get_or_create(
                name='Fitness',
                defaults={'description': 'Physical exercises and training'}
            )[0],
            'reading': Category.objects.get_or_create(
                name='Reading',
                defaults={'description': 'Reading books and articles'}
            )[0],
            'coding': Category.objects.get_or_create(
                name='Coding',
                defaults={'description': 'Programming and development'}
            )[0],
        }
        
        self.stdout.write(self.style.NOTICE('Creating unit types...'))
        
        unit_types = {
            'hours': UnitType.objects.get_or_create(name='Hours', defaults={'symbol': 'h'})[0],
            'minutes': UnitType.objects.get_or_create(name='Minutes', defaults={'symbol': 'min'})[0],
            'words': UnitType.objects.get_or_create(name='Words', defaults={'symbol': 'words'})[0],
            'pages': UnitType.objects.get_or_create(name='Pages', defaults={'symbol': 'pg'})[0],
            'hits': UnitType.objects.get_or_create(name='Hits', defaults={'symbol': 'hits'})[0],
            'exercises': UnitType.objects.get_or_create(name='Exercises', defaults={'symbol': 'ex'})[0],
            'problems': UnitType.objects.get_or_create(name='Problems', defaults={'symbol': 'prob'})[0],
        }
        
        self.stdout.write(self.style.NOTICE('Creating achievements...'))
        
        achievements_data = [
            # English achievements
            {
                'name': 'English Listener',
                'description': 'Listen to English audio content',
                'category': categories['english'],
                'unit_type': unit_types['hours'],
                'bronze_requirement': 10,
                'silver_requirement': 50,
                'gold_requirement': 100,
                'platinum_requirement': 300,
                'diamond_requirement': 1000
            },
            {
                'name': 'Word Collector',
                'description': 'Learn new English words',
                'category': categories['english'],
                'unit_type': unit_types['words'],
                'bronze_requirement': 50,
                'silver_requirement': 200,
                'gold_requirement': 500,
                'platinum_requirement': 1000,
                'diamond_requirement': 3000
            },
            {
                'name': 'Conversation Master',
                'description': 'Practice speaking English',
                'category': categories['english'],
                'unit_type': unit_types['minutes'],
                'bronze_requirement': 300,
                'silver_requirement': 1000,
                'gold_requirement': 3000,
                'platinum_requirement': 10000,
                'diamond_requirement': 30000
            },
            
            # Fitness achievements
            {
                'name': 'Workout Warrior',
                'description': 'Complete workout sessions',
                'category': categories['fitness'],
                'unit_type': unit_types['hours'],
                'bronze_requirement': 10,
                'silver_requirement': 50,
                'gold_requirement': 100,
                'platinum_requirement': 300,
                'diamond_requirement': 1000
            },
            {
                'name': 'Punch Counter',
                'description': 'Track your punches in training',
                'category': categories['fitness'],
                'unit_type': unit_types['hits'],
                'bronze_requirement': 1000,
                'silver_requirement': 5000,
                'gold_requirement': 10000,
                'platinum_requirement': 50000,
                'diamond_requirement': 100000
            },
            
            # Reading achievements
            {
                'name': 'Bookworm',
                'description': 'Read books and articles',
                'category': categories['reading'],
                'unit_type': unit_types['pages'],
                'bronze_requirement': 100,
                'silver_requirement': 500,
                'gold_requirement': 1000,
                'platinum_requirement': 5000,
                'diamond_requirement': 10000
            },
            
            # Coding achievements
            {
                'name': 'Code Ninja',
                'description': 'Time spent coding',
                'category': categories['coding'],
                'unit_type': unit_types['hours'],
                'bronze_requirement': 10,
                'silver_requirement': 50,
                'gold_requirement': 100,
                'platinum_requirement': 500,
                'diamond_requirement': 1000
            },
            {
                'name': 'Problem Solver',
                'description': 'Solve programming problems',
                'category': categories['coding'],
                'unit_type': unit_types['problems'],
                'bronze_requirement': 10,
                'silver_requirement': 50,
                'gold_requirement': 100,
                'platinum_requirement': 500,
                'diamond_requirement': 1000
            },
        ]
        
        created_count = 0
        for achievement_data in achievements_data: 
            achievement, created = Achievement.objects.get_or_create(
                name=achievement_data['name'],
                defaults=achievement_data
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} new achievements!'))
        self.stdout.write(self.style.SUCCESS('All data is now in place.'))