from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import (
    Task,
    Profile,
    Friendship,
    Message,
    Notification,
    Group,
    GroupMessage,
    ConsumedCalories,
    Achievement,
    UserAchievement,
    UserNutritionGoal,
    Quest,
    UserHabit,
    Achievement,
    UserAchievement,
    Category,
    UnitType,
)
from django.conf import settings

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
from api.users.tokens import account_activation_token


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class UnitTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitType
        fields = "__all__"


class AchievementSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    unit_type = UnitTypeSerializer(read_only=True)

    class Meta:
        model = Achievement
        fields = "__all__"


class UserAchievementSerializer(serializers.ModelSerializer):
    achievement = AchievementSerializer(read_only=True)

    next_tier = serializers.SerializerMethodField()
    next_requirement = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = UserAchievement
        fields = [
            "id",
            "achievement",
            "current_progress",
            "current_tier",
            "next_tier",
            "next_requirement",
            "progress_percentage",
            "completed",
            "completed_at",
        ]

    def get_next_tier(self, obj):
        """Получить следующий уровень достижения"""
        if obj.current_tier == "BRONZE":
            return "SILVER"
        elif obj.current_tier == "SILVER":
            return "GOLD"
        elif obj.current_tier == "GOLD":
            return "PLATINUM"
        elif obj.current_tier == "PLATINUM":
            return "DIAMOND"
        return None

    def get_next_requirement(self, obj):
        """Получить требование для следующего уровня"""
        if obj.current_tier == "BRONZE":
            return obj.achievement.silver_requirement
        elif obj.current_tier == "SILVER":
            return obj.achievement.gold_requirement
        elif obj.current_tier == "GOLD":
            return obj.achievement.platinum_requirement
        elif obj.current_tier == "PLATINUM":
            return obj.achievement.diamond_requirement
        return None

    def get_progress_percentage(self, obj):
        """Вычислить процент прогресса к следующему уровню"""
        next_req = self.get_next_requirement(obj)
        if not next_req:
            return 100

        curr_tier_req = 0
        if obj.current_tier == "SILVER":
            curr_tier_req = obj.achievement.bronze_requirement
        elif obj.current_tier == "GOLD":
            curr_tier_req = obj.achievement.silver_requirement
        elif obj.current_tier == "PLATINUM":
            curr_tier_req = obj.achievement.gold_requirement
        elif obj.current_tier == "DIAMOND":
            curr_tier_req = obj.achievement.platinum_requirement

        progress_in_tier = obj.current_progress - curr_tier_req
        tier_range = next_req - curr_tier_req

        return (
            min(100, int((progress_in_tier / tier_range) * 100))
            if tier_range > 0
            else 100
        )


class TaskSerializer(ModelSerializer):

    category = CategorySerializer(read_only=True)
    unit_type = UnitTypeSerializer(read_only=True)

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True
    )

    unit_type_id = serializers.PrimaryKeyRelatedField(
        queryset=UnitType.objects.all(),
        source="unit_type",
        write_only=True,
        required=False,
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "deadline",
            "completed",
            "difficulty",
            "points",
            "category",
            "category_id",
            "unit_type",
            "unit_type_id",
            "unit_amount",
            "updated",
        ]
        read_only_fields = ["updated"]


class UserRegistrationSerializer(ModelSerializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True, label="Confirm password")
    email = serializers.EmailField()

    class Meta:
        model = User
        fields = ["username", "email", "password", "password2"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already registered!")
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": "The passwords do not match."}
            )
        validate_password(attrs["password"])
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("password2")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            is_active=False,
        )
        refresh = RefreshToken.for_user(user)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        activation_link = self.context["request"].build_absolute_uri(
            reverse("activate-account", kwargs={"uidb64": uid, "token": token})
        )
        send_mail(
            subject="Verify your account",
            message=f"Follow the link to confirm your account: {activation_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
        user_data = UserSerializer(user).data

        return {
            "user": user_data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "message": "User registered successfully. Please check your email to activate.",
        }


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(
            username=data.get("username"), password=data.get("password")
        )

        if not user:
            raise serializers.ValidationError("Invalid username or password.")
        if not user.is_active:
            raise serializers.ValidationError(
                "Account has not been activated. Check your mail."
            )

        refresh = RefreshToken.for_user(user)
        return {
            "user_id": user.pk,
            "username": user.username,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", required=False)
    avatar = serializers.ImageField(write_only=True, required=False, allow_null=True)
    avatar_clear = serializers.BooleanField(write_only=True, required=False)

    email = serializers.EmailField(source="user.email", read_only=True)
    points = serializers.IntegerField(read_only=True)
    total_points = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "email",
            "bio",
            "avatar",
            "avatar_clear",
            "avatar_url",
            "points",
            "total_points",
            "level",
        ]
        read_only_fields = ["email", "points", "total_points", "avatar_url", "level"]

    def get_total_points(self, obj):
        return int(1000 * (1.5 ** (obj.level - 1)))

    def get_avatar_url(self, obj):
        if obj.avatar and hasattr(obj.avatar, "url"):
            request = self.context.get("request")
            url = obj.avatar.url
            return request.build_absolute_uri(url) if request else url
        return None

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        if "username" in user_data:
            instance.user.username = user_data["username"]
            instance.user.save()

        if validated_data.pop("avatar_clear", False):
            if instance.avatar:
                instance.avatar.delete(save=False)
            instance.avatar = None
        elif "avatar" in validated_data:
            # Replace existing avatar if new one provided
            new_avatar = validated_data.pop("avatar")
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
        fields = "__all__"


class MessageSerializer(serializers.ModelSerializer):
    recipient_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Message
        fields = ["id", "sender", "recipient", "recipient_id", "timestamp", "is_read"]
        read_only_fields = ["id", "sender", "recipient", "timestamp"]

    def validate_recipient_id(self, value):
        if value == self.context["request"].user.id:
            raise serializers.ValidationError("You cannot send a message to yourself")
        get_object_or_404(User, id=value)
        return value

    def validate_content(Self, value):
        if not value.strip():
            raise serializers.ValidationError("Content cannot be empty.")
        return value.strip()

    def create(self, validated_data):
        recipient_id = validated_data.pop("recipient_id")
        recipient = get_object_or_404(User, id=recipient_id)
        return Message.objects.create(
            sender=self.context["request"].user, recipient=recipient, **validated_data
        )


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "user", "notification_type", "message", "created_at", "is_read"]
        read_only_fields = ["created_at"]


class GroupSerializer(serializers.ModelSerializer):
    members = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Group
        fields = ["id", "name", "description", "created_by", "members", "created_at"]


class GroupMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMessage
        fields = ["id", "group", "sender", "content", "created_at"]
        read_only_fields = ["id", "created_at"]


class ConsumedCaloriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsumedCalories
        fields = [
            "id",
            "user",
            "product_name",
            "calories",
            "proteins",
            "fats",
            "carbs",
            "weight",
            "consumed_at",
        ]
        read_only_fields = ["id", "user", "consumed_at"]


class UserNutritionGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNutritionGoal
        fields = ["calories_goal", "proteins_goal", "fats_goal", "carbs_goal"]

    def create(self, validated_data):
        user = self.context["request"].user
        nutrition_goal, created = UserNutritionGoal.objects.update_or_create(
            user=user, defaults=validated_data
        )
        return nutrition_goal


class QuestSerializer(serializers.ModelSerializer):
    quest_type_display = serializers.CharField(
        source="get_quest_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Quest
        fields = [
            "id",
            "title",
            "description",
            "quest_type",
            "quest_type_display",
            "status",
            "status_display",
            "reward_points",
            "reward_other",
            "penalty_info",
            "generated_at",
            "expires_at",
            "completed_at",
        ]
        read_only_fields = ["generated_at", "completed_at"]


class UserHabitSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели UserHabit.
    Используется для создания, обновления (частичного) и получения привычек.
    Поля streak и last_tracked обновляются через отдельный endpoint/логику.
    """

    class Meta:
        model = UserHabit
        fields = [
            "id",
            "title",
            "description",
            "icon",
            "frequency",
            "notification_enabled",
            "streak",
            "last_tracked",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "streak",
            "last_tracked",
            "created_at",
            "updated_at",
        ]

        extra_kwargs = {
            "title": {
                "required": True,
                "error_messages": {
                    "required": "Пожалуйста, укажите название привычки.",
                    "blank": "Название привычки не может быть пустым.",
                },
            },
            "description": {"required": False, "allow_blank": True, "allow_null": True},
            "icon": {"required": False, "allow_blank": True, "allow_null": True},
            "frequency": {"required": False},
            "notification_enabled": {"required": False},
            "is_active": {"required": False},
        }
