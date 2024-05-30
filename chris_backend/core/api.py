
from django.urls import path, re_path, include
from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework.authtoken.views import obtain_auth_token

from core import views as core_views
from feeds import views as feed_views
from plugins import views as plugin_views
from plugininstances import views as plugininstance_views
from pipelines import views as pipeline_views
from workflows import views as workflow_views
from userfiles import views as userfile_views
from pacsfiles import views as pacsfile_views
from filebrowser import views as filebrowser_views
from users import views as user_views


# API v1 endpoints
urlpatterns = format_suffix_patterns([

    path('v1/auth-token/',
        obtain_auth_token),


    path('v1/users/',
        user_views.UserCreate.as_view(), name='user-create'),

    path('v1/users/<int:pk>/',
        user_views.UserDetail.as_view(), name='user-detail'),

    path('v1/users/<int:pk>/groups/',
         user_views.UserGroupList.as_view(), name='user-group-list'),


    path('v1/downloadtokens/',
         core_views.FileDownloadTokenList.as_view(),
         name='filedownloadtoken-list'),

    path('v1/downloadtokens/search/',
         core_views.FileDownloadTokenListQuerySearch.as_view(),
         name='filedownloadtoken-list-query-search'),

    path('v1/downloadtokens/<int:pk>/',
         core_views.FileDownloadTokenDetail.as_view(),
         name='filedownloadtoken-detail'),


    path('v1/chrisinstance/<int:pk>/',
         core_views.ChrisInstanceDetail.as_view(), name='chrisinstance-detail'),


    path('v1/',
        feed_views.FeedList.as_view(), name='feed-list'),

    path('v1/search/',
        feed_views.FeedListQuerySearch.as_view(), name='feed-list-query-search'),

    path('v1/<int:pk>/',
        feed_views.FeedDetail.as_view(), name='feed-detail'),

    path('v1/note<int:pk>/',
        feed_views.NoteDetail.as_view(), name='note-detail'),

    path('v1/<int:pk>/grouppermissions/',
         feed_views.FeedGroupPermissionList.as_view(),
         name='feed-group-permission-list'),

    path('v1/<int:pk>/grouppermissions/search/',
         feed_views.FeedGroupPermissionListQuerySearch.as_view(),
         name='feed-group-permission-list-query-search'),

    path('v1/grouppermissions/<int:pk>/',
         feed_views.FeedGroupPermissionDetail.as_view(),
         name='feed-group-permission-detail'),

    path('v1/<int:pk>/userpermissions/',
         feed_views.FeedUserPermissionList.as_view(),
         name='feed-user-permission-list'),

    path('v1/<int:pk>/userpermissions/search/',
         feed_views.FeedUserPermissionListQuerySearch.as_view(),
         name='feed-user-permission-list-query-search'),

    path('v1/userpermissions/<int:pk>/',
         feed_views.FeedUserPermissionDetail.as_view(),
         name='feed-user-permission-detail'),

    path('v1/<int:pk>/comments/',
        feed_views.CommentList.as_view(), name='comment-list'),

    path('v1/<int:pk>/comments/search/',
        feed_views.CommentListQuerySearch.as_view(), name='comment-list-query-search'),

    path('v1/comments/<int:pk>/',
        feed_views.CommentDetail.as_view(), name='comment-detail'),

    path('v1/<int:pk>/plugininstances/',
        feed_views.FeedPluginInstanceList.as_view(), name='feed-plugininstance-list'),

    path('v1/<int:pk>/tags/',
        feed_views.FeedTagList.as_view(), name='feed-tag-list'),

    path('v1/<int:pk>/taggings/',
        feed_views.FeedTaggingList.as_view(), name='feed-tagging-list'),

    path('v1/tags/',
        feed_views.TagList.as_view(), name='tag-list'),

    path('v1/tags/search/',
        feed_views.TagListQuerySearch.as_view(), name='tag-list-query-search'),

    path('v1/tags/<int:pk>/',
        feed_views.TagDetail.as_view(), name='tag-detail'),

    path('v1/tags/<int:pk>/feeds/',
        feed_views.TagFeedList.as_view(), name='tag-feed-list'),

    path('v1/tags/<int:pk>/taggings/',
        feed_views.TagTaggingList.as_view(), name='tag-tagging-list'),

    path('v1/taggings/<int:pk>/',
        feed_views.TaggingDetail.as_view(), name='tagging-detail'),


    path('v1/publicfeeds/',
         feed_views.PublicFeedList.as_view(), name='publicfeed-list'),

    path('v1/publicfeeds/search/',
         feed_views.PublicFeedListQuerySearch.as_view(),
         name='publicfeed-list-query-search'),


    path('v1/computeresources/',
         plugin_views.ComputeResourceList.as_view(), name='computeresource-list'),

    path('v1/computeresources/search/',
         plugin_views.ComputeResourceListQuerySearch.as_view(),
         name='computeresource-list-query-search'),

    path('v1/computeresources/<int:pk>/',
         plugin_views.ComputeResourceDetail.as_view(), name='computeresource-detail'),


    path('v1/plugins/metas/',
         plugin_views.PluginMetaList.as_view(),
         name='pluginmeta-list'),

    path('v1/plugins/metas/search/',
         plugin_views.PluginMetaListQuerySearch.as_view(),
         name='pluginmeta-list-query-search'),

    path('v1/plugins/metas/<int:pk>/',
         plugin_views.PluginMetaDetail.as_view(),
         name='pluginmeta-detail'),

    path('v1/plugins/metas/<int:pk>/plugins/',
         plugin_views.PluginMetaPluginList.as_view(),
         name='pluginmeta-plugin-list'),


    path('v1/plugins/',
        plugin_views.PluginList.as_view(), name='plugin-list'),

    path('v1/plugins/search/',
        plugin_views.PluginListQuerySearch.as_view(), name='plugin-list-query-search'),

    path('v1/plugins/<int:pk>/',
        plugin_views.PluginDetail.as_view(), name='plugin-detail'),

    path('v1/plugins/<int:pk>/parameters/',
        plugin_views.PluginParameterList.as_view(), name='pluginparameter-list'),

    path('v1/plugins/parameters/<int:pk>/',
        plugin_views.PluginParameterDetail.as_view(), name='pluginparameter-detail'),

    path('v1/plugins/<int:pk>/computeresources/',
        plugin_views.PluginComputeResourceList.as_view(),
         name='plugin-computeresource-list'),


    path('v1/pipelines/',
        pipeline_views.PipelineList.as_view(),
        name='pipeline-list'),

    path('v1/pipelines/search/',
        pipeline_views.PipelineListQuerySearch.as_view(),
        name='pipeline-list-query-search'),

    path('v1/pipelines/<int:pk>/',
        pipeline_views.PipelineDetail.as_view(),
        name='pipeline-detail'),

    path('v1/pipelines/<int:pk>/json/',
         pipeline_views.PipelineCustomJsonDetail.as_view(),
         name='pipeline-customjson-detail'),

    path('v1/pipelines/sourcefiles/',
         pipeline_views.PipelineSourceFileList.as_view(),
         name='pipelinesourcefile-list'),

    path('v1/pipelines/sourcefiles/search/',
         pipeline_views.PipelineSourceFileListQuerySearch.as_view(),
         name='pipelinesourcefile-list-query-search'),

    path('v1/pipelines/sourcefiles/<int:pk>/',
         pipeline_views.PipelineSourceFileDetail.as_view(),
         name='pipelinesourcefile-detail'),

    re_path(r'^v1/pipelines/sourcefiles/(?P<pk>[0-9]+)/.*$',
            pipeline_views.PipelineSourceFileResource.as_view(),
            name='pipelinesourcefile-resource'),

    path('v1/pipelines/<int:pk>/plugins/',
        pipeline_views.PipelinePluginList.as_view(), name='pipeline-plugin-list'),

    path('v1/pipelines/<int:pk>/pipings/',
        pipeline_views.PipelinePluginPipingList.as_view(),
        name='pipeline-pluginpiping-list'),

    path('v1/pipelines/<int:pk>/parameters/',
        pipeline_views.PipelineDefaultParameterList.as_view(),
        name='pipeline-defaultparameter-list'),

    path('v1/pipelines/pipings/<int:pk>/',
        pipeline_views.PluginPipingDetail.as_view(),
        name='pluginpiping-detail'),

    path('v1/pipelines/string-parameter/<int:pk>/',
        pipeline_views.DefaultPipingStrParameterDetail.as_view(),
        name='defaultpipingstrparameter-detail'),

    path('v1/pipelines/integer-parameter/<int:pk>/',
        pipeline_views.DefaultPipingIntParameterDetail.as_view(),
        name='defaultpipingintparameter-detail'),

    path('v1/pipelines/float-parameter/<int:pk>/',
        pipeline_views.DefaultPipingFloatParameterDetail.as_view(),
        name='defaultpipingfloatparameter-detail'),

    path('v1/pipelines/boolean-parameter/<int:pk>/',
        pipeline_views.DefaultPipingBoolParameterDetail.as_view(),
        name='defaultpipingboolparameter-detail'),


    path('v1/plugins/<int:pk>/instances/',
        plugininstance_views.PluginInstanceList.as_view(),
        name='plugininstance-list'),

    path('v1/plugins/instances/',
        plugininstance_views.AllPluginInstanceList.as_view(),
        name='allplugininstance-list'),

    path('v1/plugins/instances/search/',
        plugininstance_views.AllPluginInstanceListQuerySearch.as_view(),
        name='allplugininstance-list-query-search'),

    path('v1/plugins/instances/<int:pk>/',
        plugininstance_views.PluginInstanceDetail.as_view(),
        name='plugininstance-detail'),

    path('v1/plugins/instances/<int:pk>/splits/',
         plugininstance_views.PluginInstanceSplitList.as_view(),
         name='plugininstancesplit-list'),

    path('v1/plugins/instances/splits/<int:pk>/',
         plugininstance_views.PluginInstanceSplitDetail.as_view(),
         name='plugininstancesplit-detail'),

    path('v1/plugins/instances/<int:pk>/descendants/',
        plugininstance_views.PluginInstanceDescendantList.as_view(),
        name='plugininstance-descendant-list'),

    path('v1/plugins/instances/<int:pk>/parameters/',
        plugininstance_views.PluginInstanceParameterList.as_view(),
        name='plugininstance-parameter-list'),

    path('v1/plugins/string-parameter/<int:pk>/',
        plugininstance_views.StrParameterDetail.as_view(),
        name='strparameter-detail'),

    path('v1/plugins/integer-parameter/<int:pk>/',
        plugininstance_views.IntParameterDetail.as_view(),
        name='intparameter-detail'),

    path('v1/plugins/float-parameter/<int:pk>/',
        plugininstance_views.FloatParameterDetail.as_view(),
        name='floatparameter-detail'),

    path('v1/plugins/boolean-parameter/<int:pk>/',
        plugininstance_views.BoolParameterDetail.as_view(),
        name='boolparameter-detail'),

    path('v1/plugins/path-parameter/<int:pk>/',
        plugininstance_views.PathParameterDetail.as_view(),
        name='pathparameter-detail'),

    path('v1/plugins/unextpath-parameter/<int:pk>/',
         plugininstance_views.UnextpathParameterDetail.as_view(),
         name='unextpathparameter-detail'),


    path('v1/pipelines/<int:pk>/workflows/',
         workflow_views.WorkflowList.as_view(),
         name='workflow-list'),

    path('v1/pipelines/workflows/',
         workflow_views.AllWorkflowList.as_view(),
         name='allworkflow-list'),

    path('v1/pipelines/workflows/search/',
         workflow_views.AllWorkflowListQuerySearch.as_view(),
         name='allworkflow-list-query-search'),

    path('v1/pipelines/workflows/<int:pk>/',
         workflow_views.WorkflowDetail.as_view(),
         name='workflow-detail'),

    path('v1/pipelines/workflows/<int:pk>/plugininstances/',
         workflow_views.WorkflowPluginInstanceList.as_view(),
         name='workflow-plugininstance-list'),


    path('v1/userfiles/',
        userfile_views.UserFileList.as_view(),
        name='userfile-list'),

    path('v1/userfiles/search/',
        userfile_views.UserFileListQuerySearch.as_view(),
        name='userfile-list-query-search'),

    path('v1/userfiles/<int:pk>/',
        userfile_views.UserFileDetail.as_view(),
        name='userfile-detail'),

    re_path(r'^v1/userfiles/(?P<pk>[0-9]+)/.*$',
        userfile_views.UserFileResource.as_view(),
        name='userfile-resource'),


    path('v1/pacs/series/',
         pacsfile_views.PACSSeriesList.as_view(),
         name='pacsseries-list'),

    path('v1/pacs/series/search/',
         pacsfile_views.PACSSeriesListQuerySearch.as_view(),
         name='pacsseries-list-query-search'),

    path('v1/pacs/series/<int:pk>/',
         pacsfile_views.PACSSeriesDetail.as_view(),
         name='pacsseries-detail'),

    path('v1/pacs/files/',
        pacsfile_views.PACSFileList.as_view(),
        name='pacsfile-list'),

    path('v1/pacs/files/search/',
        pacsfile_views.PACSFileListQuerySearch.as_view(),
        name='pacsfile-list-query-search'),

    path('v1/pacs/files/<int:pk>/',
        pacsfile_views.PACSFileDetail.as_view(),
        name='pacsfile-detail'),

    re_path(r'^v1/pacs/files/(?P<pk>[0-9]+)/.*$',
        pacsfile_views.PACSFileResource.as_view(),
        name='pacsfile-resource'),


    path('v1/filebrowser/',
         filebrowser_views.FileBrowserFolderList.as_view(),
         name='chrisfolder-list'),

    path('v1/filebrowser/search/',
         filebrowser_views.FileBrowserFolderListQuerySearch.as_view(),
         name='chrisfolder-list-query-search'),

    path('v1/filebrowser/<int:pk>/',
         filebrowser_views.FileBrowserFolderDetail.as_view(),
         name='chrisfolder-detail'),

    path('v1/filebrowser/<int:pk>/children/',
         filebrowser_views.FileBrowserFolderChildList.as_view(),
         name='chrisfolder-child-list'),

    path('v1/filebrowser/<int:pk>/grouppermissions/',
         filebrowser_views.FileBrowserFolderGroupPermissionList.as_view(),
         name='foldergrouppermission-list'),

    path('v1/filebrowser/<int:pk>/grouppermissions/search/',
         filebrowser_views.FileBrowserFolderGroupPermissionListQuerySearch.as_view(),
         name='chrisfoldergrouppermission-list-query-search'),

    path('v1/filebrowser/grouppermissions/<int:pk>/',
         filebrowser_views.FileBrowserFolderGroupPermissionDetail.as_view(),
         name='foldergrouppermission-detail'),

    path('v1/filebrowser/<int:pk>/userpermissions/',
         filebrowser_views.FileBrowserFolderUserPermissionList.as_view(),
         name='folderuserpermission-list'),

    path('v1/filebrowser/<int:pk>/userpermissions/search/',
         filebrowser_views.FileBrowserFolderUserPermissionListQuerySearch.as_view(),
         name='folderuserpermission-list-query-search'),

    path('v1/filebrowser/userpermissions/<int:pk>/',
         filebrowser_views.FileBrowserFolderUserPermissionDetail.as_view(),
         name='folderuserpermission-detail'),

    path('v1/filebrowser/<int:pk>/files/',
         filebrowser_views.FileBrowserFolderFileList.as_view(),
         name='chrisfolder-file-list'),

    path('v1/filebrowser/files/<int:pk>/',
         filebrowser_views.FileBrowserFileDetail.as_view(),
         name='chrisfile-detail'),

    path('v1/filebrowser/files/<int:pk>/grouppermissions/',
         filebrowser_views.FileBrowserFileGroupPermissionList.as_view(),
         name='filegrouppermission-list'),

    path('v1/filebrowser/files/<int:pk>/grouppermissions/search/',
         filebrowser_views.FileBrowserFileGroupPermissionListQuerySearch.as_view(),
         name='filegrouppermission-list-query-search'),

    path('v1/filebrowser/files/grouppermissions/<int:pk>/',
         filebrowser_views.FileBrowserFileGroupPermissionDetail.as_view(),
         name='filegrouppermission-detail'),

    path('v1/filebrowser/files/<int:pk>/userpermissions/',
         filebrowser_views.FileBrowserFileUserPermissionList.as_view(),
         name='fileuserpermission-list'),

    path('v1/filebrowser/files/<int:pk>/userpermissions/search/',
         filebrowser_views.FileBrowserFileUserPermissionListQuerySearch.as_view(),
         name='fileuserpermission-list-query-search'),

    path('v1/filebrowser/files/userpermissions/<int:pk>/',
         filebrowser_views.FileBrowserFileUserPermissionDetail.as_view(),
         name='fileuserpermission-detail'),

    re_path(r'^v1/filebrowser/files/(?P<pk>[0-9]+)/.*$',
            filebrowser_views.FileBrowserFileResource.as_view(),
            name='chrisfile-resource'),

    path('v1/filebrowser/<int:pk>/linkfiles/',
         filebrowser_views.FileBrowserFolderLinkFileList.as_view(),
         name='chrisfolder-linkfile-list'),

    path('v1/filebrowser/linkfiles/<int:pk>/',
         filebrowser_views.FileBrowserLinkFileDetail.as_view(),
         name='chrislinkfile-detail'),

    path('v1/filebrowser/linkfiles/<int:pk>/grouppermissions/',
         filebrowser_views.FileBrowserLinkFileGroupPermissionList.as_view(),
         name='linkfilegrouppermission-list'),

    path('v1/filebrowser/linkfiles/<int:pk>/grouppermissions/search/',
         filebrowser_views.FileBrowserLinkFileGroupPermissionListQuerySearch.as_view(),
         name='linkfilegrouppermission-list-query-search'),

    path('v1/filebrowser/linkfiles/grouppermissions/<int:pk>/',
         filebrowser_views.FileBrowserLinkFileGroupPermissionDetail.as_view(),
         name='linkfilegrouppermission-detail'),

    path('v1/filebrowser/linkfiles/<int:pk>/userpermissions/',
         filebrowser_views.FileBrowserLinkFileUserPermissionList.as_view(),
         name='linkfileuserpermission-list'),

    path('v1/filebrowser/linkfiles/<int:pk>/userpermissions/search/',
         filebrowser_views.FileBrowserLinkFileUserPermissionListQuerySearch.as_view(),
         name='linkfileuserpermission-list-query-search'),

    path('v1/filebrowser/linkfiles/userpermissions/<int:pk>/',
         filebrowser_views.FileBrowserLinkFileUserPermissionDetail.as_view(),
         name='linkfileuserpermission-detail'),

    re_path(r'^v1/filebrowser/linkfiles/(?P<pk>[0-9]+)/.*$',
            filebrowser_views.FileBrowserLinkFileResource.as_view(),
            name='chrislinkfile-resource')

])

# Login and logout views for Djangos' browsable API
urlpatterns += [
    path('v1/auth/', include('rest_framework.urls',  namespace='rest_framework')),
]