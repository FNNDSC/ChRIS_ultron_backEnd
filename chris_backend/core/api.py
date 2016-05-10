from django.conf.urls import url, include

from rest_framework.urlpatterns import format_suffix_patterns

from feeds import views


# API v1 endpoints
urlpatterns = format_suffix_patterns([
    url(r'^v1/$', views.FeedList.as_view(), name='feed-list'),
    url(r'^v1/(?P<pk>[0-9]+)/$',
        views.FeedDetail.as_view(), name='feed-detail'),
])

# Login and logout views for Djangos' browsable API
urlpatterns += [
    url(r'^v1/auth/', include('rest_framework.urls',  namespace='rest_framework')),
]

