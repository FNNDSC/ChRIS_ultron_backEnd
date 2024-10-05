
import logging
import jwt

from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication
from drf_spectacular.extensions import OpenApiAuthenticationExtension

from collectionjson import services
from .models import ChrisInstance, FileDownloadToken, FileDownloadTokenFilter
from .serializers import ChrisInstanceSerializer, FileDownloadTokenSerializer
from .permissions import IsOwnerOrChris


logger = logging.getLogger(__name__)


class ChrisInstanceDetail(generics.RetrieveAPIView):
    """
    A compute resource view.
    """
    http_method_names = ['get']
    serializer_class = ChrisInstanceSerializer
    queryset = ChrisInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        """
        Overriden to return the ChrisInstance singleton.
        """
        return ChrisInstance.load()


class FileDownloadTokenList(generics.ListCreateAPIView):
    """
    A view for the collection of user-specific file download tokens.
    """
    http_method_names = ['get', 'post']
    serializer_class = FileDownloadTokenSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        """
        Overriden to associate a jwt token and owner with the download token before
        first saving to the DB.
        """
        user = self.request.user
        dt = timezone.now() + timezone.timedelta(minutes=10)
        token = jwt.encode({'user': user.username, 'exp': dt}, settings.SECRET_KEY,
                           algorithm='HS256')
        serializer.save(token=token, owner=user)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a query list to the
        response.
        """
        response = super(FileDownloadTokenList, self).list(request, *args, **kwargs)

        # append query list
        query_list = [reverse('filedownloadtoken-list-query-search',
                              request=request)]
        response = services.append_collection_querylist(response, query_list)

        user = self.request.user
        links = {'owner': reverse('user-detail', request=request,
                                  kwargs={"pk": user.id})}
        return services.append_collection_links(response, links)

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the file download
        tokens owned by the currently authenticated user.
        """
        if getattr(self, "swagger_fake_view", False):
            return FileDownloadToken.objects.none()
        user = self.request.user
        # if the user is chris then return all the file download tokens in the system
        if user.username == 'chris':
            return FileDownloadToken.objects.all()
        return FileDownloadToken.objects.filter(owner=user)


class FileDownloadTokenListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of user-specific file download tokens resulting from a
    query search.
    """
    http_method_names = ['get']
    serializer_class = FileDownloadTokenSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = FileDownloadTokenFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the file download
        tokens owned by the currently authenticated user.
        """
        if getattr(self, "swagger_fake_view", False):
            return FileDownloadToken.objects.none()
        user = self.request.user
        # if the user is chris then return all the file download tokens in the system
        if user.username == 'chris':
            return FileDownloadToken.objects.all()
        return FileDownloadToken.objects.filter(owner=user)


class FileDownloadTokenDetail(generics.RetrieveAPIView):
    """
    A file download token view.
    """
    http_method_names = ['get']
    queryset = FileDownloadToken.objects.all()
    serializer_class = FileDownloadTokenSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)


class TokenAuthSupportQueryString(TokenAuthentication):
    """
    Extend the TokenAuthentication class to support querystring authentication
    in the form of "http://www.example.com/?download_token=<token_key>".
    """
    def authenticate(self, request):
        # Check if 'download_token' is in the request query params
        if 'download_token' in request.query_params:
            token = request.query_params['download_token']
            return authenticate_token(token), None
        return super(TokenAuthSupportQueryString, self).authenticate(request)


def authenticate_token(token: str) -> User:
    err_msg = f'Invalid file download token: {token}'
    try:
        info = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        err_msg = f'Expired file download token: {token}'
        logger.error(err_msg)
        raise exceptions.AuthenticationFailed(err_msg)
    except jwt.InvalidTokenError:
        logger.error(err_msg)
        raise exceptions.AuthenticationFailed(err_msg)

    try:
        user = User.objects.get(username=info['user'])
    except User.DoesNotExist:
        logger.error(err_msg)
        raise exceptions.AuthenticationFailed(err_msg)

    token_obj = FileDownloadToken.objects.filter(owner=user, token=token).first()
    if token_obj is None:
        raise exceptions.AuthenticationFailed(err_msg)

    token_obj.delete()  # one-time-use token, we could instead set revoked=true
    return user


class TokenAuthSupportQueryStringScheme(OpenApiAuthenticationExtension):
    target_class = TokenAuthSupportQueryString
    name = 'DownloadTokenInQueryString'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'download_token'
        }
