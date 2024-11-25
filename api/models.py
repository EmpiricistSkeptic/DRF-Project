from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks', default=1)
    title = models.TextField()
    description = models.TextField(null=True, blank=True)
    deadline = models.DateTimeField("default=datetime=now")
    completed = models.BooleanField(default=False)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return {self.title[0:50]} - {self.description[0:100]}
    
    class Meta:
        ordering = ['-updated']


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    points = models.IntegerField(default=0)
    level = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.user.username}'s Profile"
    


