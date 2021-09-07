"""chris_backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

from plugins import admin as plugin_admin_views


urlpatterns = [
    path('chris-admin/', admin.site.urls),

    path('chris-admin/api/v1/',
         plugin_admin_views.PluginAdminList.as_view(),
         name='admin-plugin-list'),

    path('chris-admin/api/v1/computeresources/',
         plugin_admin_views.ComputeResourceAdminList.as_view(),
         name='admin-computeresource-list'),

    path('api/', include('core.api')),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
