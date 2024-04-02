
import logging

from rest_framework import generics, permissions
from rest_framework.authentication import TokenAuthentication

from .models import ChrisInstance
from .serializers import ChrisInstanceSerializer


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


class TokenAuthSupportQueryString(TokenAuthentication):
    """
    Extend the TokenAuthentication class to support querystring authentication
    in the form of "http://www.example.com/?auth_token=<token_key>".
    """
    def authenticate(self, request):
        # Check if 'token' is in the request query params
        if 'token' in request.query_params:
            return self.authenticate_credentials(request.query_params.get('token'))
        return super(TokenAuthSupportQueryString, self).authenticate(request)
