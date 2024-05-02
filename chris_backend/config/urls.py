"""
URL configuration for chris_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from users import views as group_admin_views


urlpatterns = [
    path('chris-admin/api/v1/',
         plugin_admin_views.PluginAdminList.as_view(),
         name='admin-plugin-list'),

    path('chris-admin/api/v1/<int:pk>/',
         plugin_admin_views.PluginAdminDetail.as_view(), name='admin-plugin-detail'),

    path('chris-admin/api/v1/computeresources/',
         plugin_admin_views.ComputeResourceAdminList.as_view(),
         name='admin-computeresource-list'),

    path('chris-admin/api/v1/computeresources/<int:pk>/',
         plugin_admin_views.ComputeResourceAdminDetail.as_view(),
         name='admin-computeresource-detail'),

    path('chris-admin/api/v1/groups/',
         group_admin_views.GroupList.as_view(),
         name='group-list'),

    path('chris-admin/api/v1/groups/search/',
         group_admin_views.GroupListQuerySearch.as_view(),
         name='group-list-query-search'),

    path('chris-admin/api/v1/groups/<int:pk>/',
         group_admin_views.GroupDetail.as_view(),
         name='group-detail'),

    path('chris-admin/api/v1/groups/<int:pk>/users/',
         group_admin_views.GroupUserList.as_view(),
         name='group-user-list'),

    path('chris-admin/api/v1/groups/users/<int:pk>/',
         group_admin_views.GroupUserDetail.as_view(),
         name='user_groups-detail'),

    path('chris-admin/', admin.site.urls),

    path('api/', include('core.api')),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
