from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Task, Profile, Friendship, Message
from django.contrib.auth.models import User
from django.contrib.auth import authenticate


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


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Invalid username or password.")
        data['user'] = user
        return data


class ProfileSerializer(ModelSerializer):
    class Meta:
        model = Profile
        fields = ['bio', 'avatar', 'points', 'level']


class FriendshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Friendship
        fields = '__all__'


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'



