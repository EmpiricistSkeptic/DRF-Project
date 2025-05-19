import os
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

import requests
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from api.users.tokens import account_activation_token
from rest_framework_simplejwt.tokens import RefreshToken


from .models import ( 
    ChatHistory
)
from .serializers import ( 
    ConsumedCaloriesSerializer,  LoginSerializer,
     UserRegistrationSerializer, 
)

logger = logging.getLogger(__name__)



class RegistrationAPIView(generics.GenericAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        return Response(data, status=status.HTTP_201_CREATED)
    

class ActivateAccountAPIView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, uidb64, token, *args, **kwargs):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = get_object_or_404(User, pk=uid)
        except (TypeError, ValueError, OverflowError):
            return Response({'detail': 'Неверная ссылка активации.'}, status=status.HTTP_400_BAD_REQUEST)
    
        if account_activation_token.check_token(user, token):
            user.is_active = True
            user.save()
            return Response({'detail': 'Аккаунт успешно активирован.'})
        else:
            return Response({'detail': 'Ссылка недействительна или истекла.'})
        

class LoginAPIView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]



class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({'detail': 'Invalid token or already blacklisted'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'detail': 'Logout successful'}, status=status.HTTP_205_RESET_CONTENT)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_calories(request):
    API_KEY = os.environ.get('API_KEY') 
    APP_ID = os.environ.get('APP_ID')   
    endpoint = os.environ.get('endpoint')
    
    headers = {
        'x-app-id': APP_ID,
        'x-app-key': API_KEY,
        'Content-Type': 'application/json',
    }

    print("Request data:", request.data)

    product_name = request.data.get('product_name')
    weight = request.data.get('weight')
    if not product_name or not weight:
        print("Error: Product name or weight is missing")
        return Response({'error': 'Product name and weight are required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    query = f'{product_name} {weight}g'
    print("Query to Nutritionix:", query)

    body = {
        'query': query,
        'timezone': 'Europe/Ukraine'
    }
    
    try:
        print("Sending request to Nutritionix with body:", body)
        response = requests.post(endpoint, headers=headers, json=body)
        print("Response status:", response.status_code)
        print("Response content:", response.content)
    
        if response.status_code == 200:
            data = response.json()
            print("Parsed JSON data:", data)
            
            if not data.get('foods'):
                print("Error: No food data returned in response")
                return Response({'error': 'No food data returned.'}, status=status.HTTP_400_BAD_REQUEST)
            
            nutrients = data['foods'][0]
            print("Extracted nutrients:", nutrients)
            
            result = {
                'product_name': nutrients.get('food_name'),
                'calories': nutrients.get('nf_calories'),
                'proteins': nutrients.get('nf_protein'),  
                'fats': nutrients.get('nf_total_fat'),  
                'carbs': nutrients.get('nf_total_carbohydrate'), 
                'weight': weight
            }
            print("Result to be serialized:", result)
            
            serializer = ConsumedCaloriesSerializer(data=result)
            if serializer.is_valid():
                print("Serializer is valid")
                serializer.save(user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                print("Serializer errors:", serializer.errors)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            print("Error response from API:", response.text)
            return Response({'error': f'Failed to fetch data from Nutritionix. Status code: {response.status_code}'}, 
                          status=response.status_code)
    except Exception as e:
        print("Exception during API request:", str(e))
        return Response({'error': f'API request failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_history(request):
    user = request.user

    history_records = ChatHistory.objects.filter(user=user).order_by('timestamp')

    messages_for_frontend = []

    if not history_records.exists():
        messages_for_frontend.append({
            'id': 'initial-system-message-backend',
            'text': '[System] The conversation history is empty. Start a conversation.',
            'sender': 'ai', 
            'timestamp': timezone.now().isoformat(),
        })
    else:
        for record in history_records:
            messages_for_frontend.append({
                'id': f'hist-{record.pk}-user', 
                'text': record.user_message,
                'sender': 'user',
                'timestamp': record.timestamp.isoformat() 
            }) 

            if record.error_occurred and record.error_message:
                 messages_for_frontend.append({
                    'id': f'hist-{record.pk}-error', 
                    'text': f'[System] Error: {record.error_message}',
                    'sender': 'ai', 
                    'timestamp': record.timestamp.isoformat()
                })
            elif record.ai_response:
                messages_for_frontend.append({
                    'id': f'hist-{record.pk}-ai',
                    'text': record.ai_response,
                    'sender': 'ai',
                    'timestamp': record.timestamp.isoformat()
                })

    return Response(messages_for_frontend, status=status.HTTP_200_OK)

