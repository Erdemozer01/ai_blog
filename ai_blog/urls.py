"""
URL configuration for ai_blog project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin, auth
from django.urls import path, include
from django.contrib.sitemaps.views import sitemap
from django.views.generic import RedirectView

from blog.sitemaps import ArticleSitemap
from django.conf import settings
from django.conf.urls.static import static

from django.templatetags.static import static as static_url

sitemaps = {
    'articles': ArticleSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),

    path('accounts/', include('django.contrib.auth.urls')),

    path('django_plotly_dash/', include('django_plotly_dash.urls')),
    path('', include('blog.urls')),
    path('billing/', include('billing.urls')),
    path('bio-tools/', include('bio_tools.urls')),

    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    path('site.webmanifest', RedirectView.as_view(url=static_url('images/site.webmanifest'), permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "AI Blog Yönetim Paneli"
admin.site.site_title = "AI Blog Yönetim Portalı"
admin.site.index_title = "Yönetim Paneline Hoş Geldiniz"