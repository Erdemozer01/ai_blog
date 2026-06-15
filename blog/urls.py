from django.urls import path, re_path

from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.anasayfa_view, name='anasayfa'),

    path('article/<int:article_id>/download-pdf/', views.download_article_as_pdf, name='download_article_pdf'),
    path('article/<int:article_id>/yayin-talebi/', views.request_publish_view, name='request_publish'),

    re_path(r'^article/(?P<article_id>[0-9]+)/(?P<slug>[^/]+)/$', views.article_detail_view, name='article_detail'),

    path('resume/', views.resume_view, name='resume'),
    path('resume/<str:username>/', views.resume_view, name='resume_user'),

    path('generate-article/', views.generate_article_view, name='generate_article'),

    path('contact/', views.contact_view, name='contact'),

    path('logout/', views.custom_logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('set-language/<str:lang_code>/', views.set_language_view, name='set_language'),

    path('robots.txt', views.robots_txt_view, name='robots_txt'),

    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),

    path('search-articles/', views.article_search_view, name='article_search'),

]