from django.conf.urls import url, include

from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework.authtoken.views import obtain_auth_token

from feeds import views as feed_views
from plugins import views as plugin_views
from uploadedfiles import views as uploaded_file_views
from users import views as user_views

# API v1 endpoints
urlpatterns = format_suffix_patterns([

    url(r'^v1/auth-token/$',
        obtain_auth_token),


    url(r'^v1/users/$',
        user_views.UserCreate.as_view(), name='user-create'),

    url(r'^v1/users/(?P<pk>[0-9]+)/$',
        user_views.UserDetail.as_view(), name='user-detail'),


    url(r'^v1/$',
        feed_views.FeedList.as_view(), name='feed-list'),

    url(r'^v1/search/$',
        feed_views.FeedListQuerySearch.as_view(), name='feed-list-query-search'),

    url(r'^v1/(?P<pk>[0-9]+)/$',
        feed_views.FeedDetail.as_view(), name='feed-detail'),

    url(r'^v1/note(?P<pk>[0-9]+)/$',
        feed_views.NoteDetail.as_view(), name='note-detail'),

    url(r'^v1/(?P<pk>[0-9]+)/comments/$',
        feed_views.CommentList.as_view(), name='comment-list'),

    url(r'^v1/comments/(?P<pk>[0-9]+)/$',
        feed_views.CommentDetail.as_view(), name='comment-detail'),

    url(r'^v1/(?P<pk>[0-9]+)/files/$',
        feed_views.FeedFileList.as_view(), name='feedfile-list'),

    url(r'^v1/(?P<pk>[0-9]+)/plugininstances/$',
        feed_views.FeedPluginInstanceList.as_view(), name='feed-plugininstance-list'),

    url(r'^v1/(?P<pk>[0-9]+)/tags/$',
        feed_views.FeedTagList.as_view(), name='feed-tag-list'),

    url(r'^v1/(?P<pk>[0-9]+)/taggings/$',
        feed_views.FeedTaggingList.as_view(), name='feed-tagging-list'),


    url(r'^v1/tags/$',
        feed_views.TagList.as_view(), name='tag-list'),

    url(r'^v1/tags/(?P<pk>[0-9]+)/$',
        feed_views.TagDetail.as_view(), name='tag-detail'),

    url(r'^v1/tags/(?P<pk>[0-9]+)/feeds/$',
        feed_views.TagFeedList.as_view(), name='tag-feed-list'),

    url(r'^v1/tags/(?P<pk>[0-9]+)/taggings/$',
        feed_views.TagTaggingList.as_view(), name='tag-tagging-list'),

    url(r'^v1/taggings/(?P<pk>[0-9]+)/$',
        feed_views.TaggingDetail.as_view(), name='tagging-detail'),


    url(r'^v1/plugins/$',
        plugin_views.PluginList.as_view(), name='plugin-list'),

    url(r'^v1/plugins/search/$',
        plugin_views.PluginListQuerySearch.as_view(), name='plugin-list-query-search'),

    url(r'^v1/plugins/(?P<pk>[0-9]+)/$',
        plugin_views.PluginDetail.as_view(), name='plugin-detail'),

    url(r'^v1/plugins/(?P<pk>[0-9]+)/parameters/$',
        plugin_views.PluginParameterList.as_view(), name='pluginparameter-list'),

    url(r'^v1/plugins/parameters/(?P<pk>[0-9]+)/$',
        plugin_views.PluginParameterDetail.as_view(), name='pluginparameter-detail'),

    url(r'^v1/plugins/(?P<pk>[0-9]+)/instances/$',
        plugin_views.PluginInstanceList.as_view(), name='plugininstance-list'),

    url(r'^v1/plugins/instances/search/$',
        plugin_views.PluginInstanceListQuerySearch.as_view(),
        name='plugininstance-list-query-search'),

    url(r'^v1/plugins/instances/(?P<pk>[0-9]+)/$',
        plugin_views.PluginInstanceDetail.as_view(), name='plugininstance-detail'),

    url(r'^v1/plugins/instances/(?P<pk>[0-9]+)/descendants/$',
        plugin_views.PluginInstanceDescendantList.as_view(),
        name='plugininstance-descendant-list'),

    url(r'^v1/plugins/instances/(?P<pk>[0-9]+)/files/$',
        plugin_views.PluginInstanceFileList.as_view(),
        name='plugininstancefile-list'),

    url(r'^v1/plugins/instances/files/(?P<pk>[0-9]+)/$',
        plugin_views.PluginInstanceFileDetail.as_view(),
        name='plugininstancefile-detail'),

    url(r'^v1/plugins/instances/files/(?P<pk>[0-9]+)/.*$',
        plugin_views.FileResource.as_view(), name='plugininstancefile-resource'),

    url(r'^v1/plugins/instances/(?P<pk>[0-9]+)/parameters/$',
        plugin_views.PluginInstanceParameterList.as_view(),
        name='plugininstance-parameter-list'),

    url(r'^v1/plugins/string-parameter/(?P<pk>[0-9]+)/$',
        plugin_views.StringParameterDetail.as_view(), name='stringparameter-detail'),

    url(r'^v1/plugins/integer-parameter/(?P<pk>[0-9]+)/$',
        plugin_views.IntParameterDetail.as_view(), name='intparameter-detail'),

    url(r'^v1/plugins/float-parameter/(?P<pk>[0-9]+)/$',
        plugin_views.FloatParameterDetail.as_view(), name='floatparameter-detail'),

    url(r'^v1/plugins/boolean-parameter/(?P<pk>[0-9]+)/$',
        plugin_views.BoolParameterDetail.as_view(), name='boolparameter-detail'),

    url(r'^v1/plugins/path-parameter/(?P<pk>[0-9]+)/$',
        plugin_views.PathParameterDetail.as_view(), name='pathparameter-detail'),


    url(r'^v1/uploadedfiles/$',
        uploaded_file_views.UploadedFileList.as_view(), name='uploadedfile-list'),

    url(r'^v1/uploadedfiles/(?P<pk>[0-9]+)/$',
        uploaded_file_views.UploadedFileDetail.as_view(), name='uploadedfile-detail'),

    url(r'^v1/uploadedfiles/(?P<pk>[0-9]+)/.*$',
        uploaded_file_views.UploadedFileResource.as_view(), name='uploadedfile-resource'),

])

# Login and logout views for Djangos' browsable API
urlpatterns += [
    url(r'^v1/auth/', include('rest_framework.urls',  namespace='rest_framework')),
]