from django.conf.urls import url, include

from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework.authtoken.views import obtain_auth_token

from feeds import views
from plugins import views as pl_views

# API v1 endpoints
urlpatterns = format_suffix_patterns([

    url(r'^v1/auth-token/$', obtain_auth_token),

    url(r'^v1/$', views.FeedList.as_view(), name='feed-list'),

    url(r'^v1/search/$',
        views.FeedListQuerySearch.as_view(), name='feed-list-query-search'),

    url(r'^v1/(?P<pk>[0-9]+)/$',
        views.FeedDetail.as_view(), name='feed-detail'),

    url(r'^v1/note(?P<pk>[0-9]+)/$',
        views.NoteDetail.as_view(), name='note-detail'),

    url(r'^v1/(?P<pk>[0-9]+)/tags/$',
        views.TagList.as_view(), name='tag-list'),

    url(r'^v1/tags/$',
        views.FullTagList.as_view(), name='full-tag-list'),

    url(r'^v1/tags/(?P<pk>[0-9]+)/$',
        views.TagDetail.as_view(), name='tag-detail'),

    url(r'^v1/(?P<pk>[0-9]+)/comments/$',
        views.CommentList.as_view(), name='comment-list'),

    url(r'^v1/comments/(?P<pk>[0-9]+)/$',
        views.CommentDetail.as_view(), name='comment-detail'),

    url(r'^v1/(?P<pk>[0-9]+)/files/$',
        views.FeedFileList.as_view(), name='feedfile-list'),

    url(r'^v1/files/(?P<pk>[0-9]+)/$',
        views.FeedFileDetail.as_view(), name='feedfile-detail'),

    url(r'^v1/files/(?P<pk>[0-9]+)/.*$',
        views.FileResource.as_view(), name='file-resource'),

    url(r'^v1/plugins/$', pl_views.PluginList.as_view(), name='plugin-list'),

    url(r'^v1/plugins/search/$',
        pl_views.PluginListQuerySearch.as_view(), name='plugin-list-query-search'),

    url(r'^v1/plugins/(?P<pk>[0-9]+)/$',
        pl_views.PluginDetail.as_view(), name='plugin-detail'),

    url(r'^v1/plugins/(?P<pk>[0-9]+)/parameters/$',
        pl_views.PluginParameterList.as_view(), name='pluginparameter-list'),

    url(r'^v1/plugins/parameters/(?P<pk>[0-9]+)/$',
        pl_views.PluginParameterDetail.as_view(), name='pluginparameter-detail'),

    url(r'^v1/plugins/(?P<pk>[0-9]+)/instances/$',
        pl_views.PluginInstanceList.as_view(), name='plugininstance-list'),

    url(r'^v1/plugins/instances/search/$',
        pl_views.PluginInstanceListQuerySearch.as_view(),
        name='plugininstance-list-query-search'),

    url(r'^v1/plugins/instances/(?P<pk>[0-9]+)/$',
        pl_views.PluginInstanceDetail.as_view(), name='plugininstance-detail'),

    url(r'^v1/plugins/string-parameter/(?P<pk>[0-9]+)/$',
        pl_views.StringParameterDetail.as_view(), name='stringparameter-detail'),

    url(r'^v1/plugins/int-parameter/(?P<pk>[0-9]+)/$',
        pl_views.IntParameterDetail.as_view(), name='intparameter-detail'),

    url(r'^v1/plugins/float-parameter/(?P<pk>[0-9]+)/$',
        pl_views.FloatParameterDetail.as_view(), name='floatparameter-detail'),

    url(r'^v1/plugins/bool-parameter/(?P<pk>[0-9]+)/$',
        pl_views.BoolParameterDetail.as_view(), name='boolparameter-detail'),

    url(r'^v1/plugins/path-parameter/(?P<pk>[0-9]+)/$',
        pl_views.PathParameterDetail.as_view(), name='pathparameter-detail'),

    url(r'^v1/users/$',
        views.UserList.as_view(), name='user-list'),

    url(r'^v1/users/(?P<pk>[0-9]+)/$',
        views.UserDetail.as_view(), name='user-detail'),

    url(r'^v1/sandboxedfiles/$',
        views.UserFileList.as_view(), name='userfile-list'),

    url(r'^v1/sandboxedfiles/(?P<pk>[0-9]+)/$',
        views.UserFileDetail.as_view(), name='userfile-detail'),

    url(r'^v1/sandboxedfiles/(?P<pk>[0-9]+)/.*$',
        views.UserFileResource.as_view(), name='userfile-resource'),

])

# Login and logout views for Djangos' browsable API
urlpatterns += [
    url(r'^v1/auth/', include('rest_framework.urls',  namespace='rest_framework')),
]

