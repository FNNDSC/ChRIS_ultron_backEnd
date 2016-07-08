from django.conf.urls import url, include

from rest_framework.urlpatterns import format_suffix_patterns

from feeds import views
from plugins.views import PluginList, PluginDetail, PluginInstanceDetail 
from plugins.views import PluginInstanceList, PluginParameterList, PluginParameterDetail
from plugins.views import StringParameterDetail, IntParameterDetail, FloatParameterDetail
from plugins.views import BoolParameterDetail

# API v1 endpoints
urlpatterns = format_suffix_patterns([
    
    url(r'^v1/$', views.FeedList.as_view(), name='feed-list'),
    
    url(r'^v1/(?P<pk>[0-9]+)/$',
        views.FeedDetail.as_view(), name='feed-detail'),
    
    url(r'^v1/note(?P<pk>[0-9]+)/$',
        views.NoteDetail.as_view(), name='note-detail'),
    
    url(r'^v1/(?P<pk>[0-9]+)/tags/$',
        views.TagList.as_view(), name='tag-list'),

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

    url(r'^v1/plugins/$', PluginList.as_view(), name='plugin-list'),
    
    url(r'^v1/plugins/(?P<pk>[0-9]+)/$',
        PluginDetail.as_view(), name='plugin-detail'),

    url(r'^v1/plugins/(?P<pk>[0-9]+)/parameters/$',
        PluginParameterList.as_view(), name='pluginparam-list'),

    url(r'^v1/plugins/parameters/(?P<pk>[0-9]+)/$',
        PluginParameterDetail.as_view(), name='pluginparam-detail'),

    url(r'^v1/plugins/(?P<pk>[0-9]+)/instances/$',
        PluginInstanceList.as_view(), name='plugininst-list'),

    url(r'^v1/plugins/instances/(?P<pk>[0-9]+)/$',
        PluginInstanceDetail.as_view(), name='plugininst-detail'),

    url(r'^v1/plugins/string-parameter/(?P<pk>[0-9]+)/$',
        StringParameterDetail.as_view(), name='stringparam-detail'),
    
    url(r'^v1/plugins/int-parameter/(?P<pk>[0-9]+)/$',
        IntParameterDetail.as_view(), name='intparam-detail'),

    url(r'^v1/plugins/float-parameter/(?P<pk>[0-9]+)/$',
        FloatParameterDetail.as_view(), name='floatparam-detail'),

    url(r'^v1/plugins/bool-parameter/(?P<pk>[0-9]+)/$',
        BoolParameterDetail.as_view(), name='boolparam-detail'),

    url(r'^v1/users/$',
        views.UserList.as_view(), name='user-list'),
    
    url(r'^v1/users/(?P<pk>[0-9]+)/$',
        views.UserDetail.as_view(), name='user-detail'),

])

# Login and logout views for Djangos' browsable API
urlpatterns += [
    url(r'^v1/auth/', include('rest_framework.urls',  namespace='rest_framework')),
]

