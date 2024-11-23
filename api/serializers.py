from rest_framework.serializers import ModelSerializer
from .models import Task
from django.contrib.auth.models import User

class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'


class UserRegistrationSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'password', 'email']
        extra_kwargs = {'password':{'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


