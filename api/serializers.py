from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import (
    Task, Profile, Friendship, Message, Notification, Group, GroupMessage, ConsumedCalories, Achievement, UserAchievement, UserNutritionGoal, Quest, UserHabit
)
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from django.shortcuts import get_object_or_404

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.urls import reverse
from users.tokens import account_activation_token



class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'deadline', 'completed', 'difficulty', 'points', 'updated', 'created']


class UserRegistrationSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True, label="Потдверждение пароля")
    email = serializers.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2']
        extra_kwargs = {
            'username': {'validators': []},
        }

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exist():
            raise serializers.ValidationError("Этот email уже зарегестрирован!")
        return value.lower()
    
    def validate(self, value):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Пароли не совпадают."})
        validate_password(attrs['password'])
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_active=False
        )
        refresh = RefreshToken.for_user(user)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        activation_link = self.context['request'].build_absolute_url(
            reverse('activate-account', kwargs={'uid64': uid, 'token': token})
        )
        send_mail(
            subject="Подтвердите ваш аккаунт",
            message="Перейдите по ссылке, чтобы подтвердить аккаунт: {activation_link}",
            from_email="no-reply",
            recipient_list=[user.email],
        )

        return {
            'user': user,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    
      


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data.get('username'), password=data.get('password'))

        if not user:
            raise serializers.ValidationError("Invalid username or password.")
        if not user.is_active:
            raise serializers.ValidationError("Account has not been activated. Check your mail.")
        
        refresh = RefreshToken.for_user(user)
        return {
            'user_id': user.pk,
            'username': user.username,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    


class ProfileSerializer(serializers.ModelSerializer):
    # Read/write fields
    username = serializers.CharField(source='user.username', required=False)
    avatar = serializers.ImageField(write_only=True, required=False, allow_null=True)
    avatar_clear = serializers.BooleanField(write_only=True, required=False)

    # Read-only fields
    email = serializers.EmailField(source='user.email', read_only=True)
    points = serializers.IntegerField(read_only=True)
    total_points = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()


    class Meta:
        model = Profile
        fields = ['username', 'email', 'bio', 'avatar', 'avatar_clear',
            'avatar_url', 'points', 'total_points', 'level']
        read_only_fields = ['email', 'points', 'total_points', 'avatar_url', 'level']
    
    def get_total_points(self, obj):
        # Exponential growth of total points by level
        return int(1000 * (1.5 ** (obj.level - 1)))
    
    def get_avatar_url(self, obj):
        if obj.avatar and hasattr(obj.avatar, 'url'):
            request = self.context.get('request')
            url = obj.avatar.url
            return request.build_absolute_uri(url) if request else url
        return None
    
    def update(self, instance, validated_data):
        # Update nested user fields
        user_data = validated_data.pop('user', {})
        if 'username' in user_data:
            instance.user.username = user_data['username']
            instance.user.save()

        # Handle avatar clearing or updating
        if validated_data.pop('avatar_clear', False):
            if instance.avatar:
                instance.avatar.delete(save=False)
            instance.avatar = None
        elif 'avatar' in validated_data:
            # Replace existing avatar if new one provided
            new_avatar = validated_data.pop('avatar')
            if instance.avatar:
                instance.avatar.delete(save=False)
            instance.avatar = new_avatar

        # Update remaining profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FriendshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Friendship
        fields = '__all__'


class MessageSerializer(serializers.ModelSerializer):
    recipient_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'recipient', 'recipient_id', 'timestamp', 'is_read']
        read_only_fields = ['id', 'sender', 'recipient', 'timestamp']

    def validate_recipient_id(self, value):
        if value == self.context['request'].user.id:
            raise serializers.ValidationError("You cannot send a message to yourself")
        get_object_or_404(User, id=value)
        return value
    
    def validate_content(Self, value):
        if not value.strip():
            raise serializers.ValidationError("Content cannot be empty.")
        return value.strip()
    
    def create(self, validated_data):
        recipient_id = validated_data.pop('recipient_id')
        recipient = get_object_or_404(User, id=recipient_id)
        return Message.objects.create(
            sender=self.context['request'].user,
            recipient=recipient,
            **validated_data
        )
        

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'notification_type', 'message', 'created_at', 'is_read']
        read_only_fields = ['created_at']


class GroupSerializer(serializers.ModelSerializer):
    members = serializers.StringRelatedField(many=True, read_only=True)
    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'created_by', 'members', 'created_at']


class GroupMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMessage
        fields = ['id', 'group', 'sender', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']




class ConsumedCaloriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsumedCalories
        fields = ['id', 'user', 'product_name', 'calories', 'proteins', 'fats', 'carbs', 'weight']
        read_only_fields = ['id', 'user']


class UserNutritionGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNutritionGoal
        fields = ['calories_goal', 'proteins_goal', 'fats_goal', 'carbs_goal']
        
    def create(self, validated_data):
        user = self.context['request'].user
        nutrition_goal, created = UserNutritionGoal.objects.update_or_create(
            user=user,
            defaults=validated_data
        )
        return nutrition_goal




class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = ['id', 'title', 'description', 'icon']


class UserAchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAchievement
        fields = ['achievement', 'unlocked', 'unlocked_at']




    
class QuestSerializer(serializers.ModelSerializer):
    quest_type_display = serializers.CharField(source='get_quest_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Quest
        fields = [
            'id', 'title', 'description', 'quest_type', 'quest_type_display',
            'status', 'status_display', 'reward_points', 'reward_other',
            'penalty_info', 'generated_at', 'expires_at', 'completed_at'
        ]
        read_only_fields = ['generated_at', 'completed_at']
        

class UserHabitSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели UserHabit.
    Используется для создания, обновления (частичного) и получения привычек.
    Поля streak и last_tracked обновляются через отдельный endpoint/логику.
    """
    # Можно добавить поле для отображения username, если нужно
    # user_username = serializers.CharField(source='user.username', read_only=True) 
    
    class Meta:
        model = UserHabit
        fields = [
            'id', 
            'title', 
            'description', 
            'icon', 
            'frequency', # Добавлено поле
            'notification_enabled', # Добавлено поле
            'streak', # Отображаем, но не изменяем напрямую
            'last_tracked', # Отображаем, но не изменяем напрямую
            'is_active', # Позволяем изменять (для деактивации)
            'created_at', 
            'updated_at',
            # 'user_username' # Если добавили выше
            # 'user' # Обычно ID пользователя не возвращают или делают read_only
        ]
        
        # Поля, которые НЕЛЬЗЯ изменять через стандартные POST/PATCH запросы
        # Они либо устанавливаются автоматически, либо через специальную логику (track_habit)
        read_only_fields = [
            'id', 
            'streak', 
            'last_tracked', 
            'created_at', 
            'updated_at',
            # 'user' # Если решите включить user ID, сделайте его read_only
        ]
        
        # Дополнительные настройки для полей
        extra_kwargs = {
            'title': {
                'required': True, 
                'error_messages': { # Кастомные сообщения об ошибках
                    'required': 'Пожалуйста, укажите название привычки.',
                    'blank': 'Название привычки не может быть пустым.',
                }
            },
            'description': {'required': False, 'allow_blank': True, 'allow_null': True},
            'icon': {'required': False, 'allow_blank': True, 'allow_null': True},
            'frequency': {'required': False}, # Можно сделать обязательным, если нужно
            'notification_enabled': {'required': False},
            'is_active': {'required': False},
        }
        
