from django.conf.urls import url, include

from rest_framework.urlpatterns import format_suffix_patterns

from feeds import views


# API v1 endpoints
urlpatterns = format_suffix_patterns([
    url(r'^v1/$', views.api_root, name='api-root'),
    url(r'^v1/feeds/$', views.FeedList.as_view(), name='feed-list'),
    url(r'^v1/feeds/(?P<pk>[0-9]+)/$',
        views.FeedDetail.as_view(), name='feed-detail'),
    url(r'^v1/users/$', views.UserList.as_view(), name='user-list'),
    url(r'^v1/users/(?P<pk>[0-9]+)/$', views.UserDetail.as_view(), name='user-detail')
])

# Login and logout views for Djangos' browsable API
urlpatterns += [
    url(r'^v1/auth/', include('rest_framework.urls',  namespace='rest_framework')),
]

