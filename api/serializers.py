from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Task, Profile, Friendship, Message, Notification, Group, GroupMessage, PomodoroTimer, EducationalContent, ConsumedCalories, Achievement, UserAchievement, UserNutritionGoal
from django.contrib.auth.models import User
from django.contrib.auth import authenticate


class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'deadline', 'completed', 'difficulty', 'exp', 'updated', 'created']


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


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    points = serializers.IntegerField(source='exp', read_only=True)
    total_points = serializers.SerializerMethodField()

    def get_total_points(self, obj):
        return int(100 * (1.5 ** (obj.level - 1)))

    
    class Meta:
        model = Profile
        fields = ['username', 'email', 'bio', 'avatar', 'points', 'total_points', 'level']


class FriendshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Friendship
        fields = '__all__'


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'


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


class PomodoroTimerSerializer(serializers.ModelSerializer):
    class Meta:
        model = PomodoroTimer
        fields = ['id', 'start_timer', 'duration_minutes', 'short_break_minutes', 'long_break_minutes', 'is_completed']
        read_only_fields = ['id', 'start_timer']


class EducationalContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EducationalContent
        fields = ['id', 'title', 'content', 'category', 'created_at']
        read_only_fields = ['id', 'created_at']


class ConsumedCaloriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsumedCalories
        fields = ['id', 'user', 'product_name', 'calories', 'proteins', 'fats', 'carbs', 'weight']
        read_only_fields = ['id', 'user']




class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = ['id', 'title', 'description', 'icon']


class UserAchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAchievement
        fields = ['achievement', 'unlocked', 'unlocked_at']


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
        