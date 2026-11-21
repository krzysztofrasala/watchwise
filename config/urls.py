from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

urlpatterns = [
    path('healthz', lambda request: HttpResponse('ok'), name='healthz'),  # keep-alive ping target
    path('admin/', admin.site.urls),
    path('', include('movies.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
