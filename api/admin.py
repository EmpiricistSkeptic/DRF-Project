from django.contrib import admin
from .models import Task, Profile, Message, Friendship, Notification, Group, GroupMessage, PomodoroTimer, EducationalContent, ConsumedCalories, Achievement

admin.site.register(Task)
admin.site.register(Profile)
admin.site.register(Message)
admin.site.register(Friendship)
admin.site.register(Notification)
admin.site.register(Group)
admin.site.register(GroupMessage)
admin.site.register(PomodoroTimer)
admin.site.register(EducationalContent)
admin.site.register(ConsumedCalories)
admin.site.register(Achievement)

