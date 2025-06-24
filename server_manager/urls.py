from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

def home_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return redirect('authentication:login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_redirect, name='home'),
    path('auth/', include('authentication.urls', namespace='authentication')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('servers/', include('servers.urls', namespace='servers')),
    path('terminal/', include('terminal.urls', namespace='terminal')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)