from django.db import models

class Task(models.Model):
    body = models.TextField()
    description = models.TextField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.body[0:50], self.description[0:100]
    
    class Meta:
        ordering = ['-updated']
    


