from django.urls import path

from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.anasayfa_view, name='anasayfa'),

    path('article/<int:article_id>/<slug:slug>/', views.article_detail_view, name='article_detail'),
    path('resume/', views.resume_view, name='resume'),
    path('generate-article/', views.generate_article_view, name='generate_article'),
    path('contact/', views.contact_view, name='contact'),
    path('logout/', views.custom_logout_view, name='logout'),
    path('robots.txt', views.robots_txt_view, name='robots_txt'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),

    path('logout/', views.custom_logout_view, name='logout'),

]