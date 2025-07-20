from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('validate/', views.ChatSafetyValidationView.as_view(), name='validate_message'),
    path('guidelines/', views.chat_guidelines_view, name='guidelines'),
    
    # Authenticated user endpoints
    path('session/start/', views.start_chat_session_view, name='start_session'),
    path('session/end/', views.end_chat_session_view, name='end_session'),
    path('favorites/add/', views.add_restaurant_to_favorites_from_chat_view, name='add_favorite_from_chat'),
    path('user/context/', views.get_user_context_view, name='get_user_context'),
]