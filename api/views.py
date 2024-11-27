from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import TaskSerializer
from .models import Task
from .serializers import UserRegistrationSerializer
from .models import Profile
from .serializers import ProfileSerializer
from rest_framework.authtoken.models import Token
from .serializers import LoginSerializer


@api_view(['GET'])
def getRoutes(request):
    routes = [
        {
            'Endpoint': '/tasks/',
            'method': 'GET',
            'body': None,
            'description': 'Returns an array of tasks'
        },
        {
            'Endpoint': '/tasks/id',
            'method': 'GET',
            'body': None,
            'description': 'Returns a single task object'
        },
        {
            'Endpoint': '/tasks/create/',
            'method': 'POST',
            'body': {'body': "The content of the task"},
            'description': 'Creates a new task with data sent in POST request'
        },
        {
            'Endpoint': '/tasks/id/update/',
            'method': 'PUT',
            'body': {'body': "Updated content of the task"},
            'description': 'Updates an existing task with data sent in PUT request'
        },
        {
            'Endpoint': '/tasks/id/delete/',
            'method': 'DELETE',
            'body': None,
            'description': 'Deletes an existing task'
        }
    ]
    return Response(routes)


@api_view(['GET'])
def tasksView(request):
    tasks = Task.objects.filter(user=request.user, completed=False)
    serializer = TaskSerializer(tasks, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def getTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)
        serializer = TaskSerializer(task, many=False)
        return Response(serializer.data)
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not meant for this user"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def createTask(request):
    data = request.data

    task = Task.objects.create(
        title = data['title']
    )
    user = request.user
    serializer = TaskSerializer(task, many=False)
    return Response(serializer.data)

@api_view(['PUT'])
def updateTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)
        serializer = TaskSerializer(task, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not owned by the user"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
def completeTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)  # Получаем задачу по ID и пользователю
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not owned by the user"}, status=status.HTTP_404_NOT_FOUND)
    
    task.completed = True  # Помечаем задачу как завершённую
    task.save()  # Сохраняем изменения
    
    serializer = TaskSerializer(task)
    return Response(serializer.data, status=status.HTTP_200_OK)

    

@api_view(['DELETE'])
def deleteTask(request, pk):
    try:
        task = Task.objects.get(id=pk, user=request.user)
        task.delete()
        return Response("Task has been deleted")
    except Task.DoesNotExist:
        return Response({"error": "Task not found or not owned by the user"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def registerAccount(request):
    if request.method == 'POST':
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "User created succssefuly"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def loginUser(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "message": "Login successful"}, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def logoutUser(request):
    try:
        token = request.user.auth_token
        if token:
            token.delete()
            return Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        return Response({"error": "No token provided"}, status=status.HTTP_400_BAD_REQUEST)
    except:
        return Response({"error": "An error occured during logout"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET', 'PUT'])
def userProfile(request):
    if request.method == 'GET':
        try:
            profile = request.user.profile
            serializer = ProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Profile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
    elif request.method == 'PUT':
        try:
            profile = request.user.profile
            serializer = ProfileSerializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Profile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
        










