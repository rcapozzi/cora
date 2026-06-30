from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path
from cora import views

urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^application/(?P<id>[0-9a-f-]{36})/?$',   views.application_detail,  name='application_detail'),
    re_path(r'^application/(?P<id>[0-9a-f-]{36})/release/?$', views.application_release, name='application_release'),
    re_path(r'^ping/?$', views.ping, name='ping'),
    re_path(r'^application/?$', views.application_list, name='application_list'),
    path('application/import', views.application_import, name='application_import'),
    path('submission/import', views.application_import, name='submission_import'),
]
# Serve media files locally ONLY during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
