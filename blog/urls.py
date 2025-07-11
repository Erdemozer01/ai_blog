from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.anasayfa_view, name='anasayfa'),

    path('generate-article/', views.generate_article_view, name='generate_article'),

    path('article/<int:article_id>/', views.article_detail_view, name='article_detail'),

    path('contact/', views.contact_view, name='contact'),

    path('robots.txt', views.robots_txt_view, name='robots_txt'),

    path('resume/', views.resume_view, name='resume'),

    path('logout/', views.custom_logout_view, name='logout'),

]
