from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('credits/', views.credits_view, name='credits'),
]
