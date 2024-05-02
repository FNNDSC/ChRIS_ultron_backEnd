
from django.contrib.auth.models import User, Group
from rest_framework import generics, permissions, serializers
from rest_framework.reverse import reverse
from rest_framework.response import Response

from collectionjson import services

from .models import GroupFilter
from .serializers import UserSerializer, GroupSerializer, GroupUserSerializer
from .permissions import IsUserOrChrisOrReadOnly, IsAdminOrReadOnly


class UserCreate(generics.ListCreateAPIView):
    http_method_names = ['get', 'post']
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json write template.
        """
        response = services.get_list_response(self, [])
        template_data = {"username": "", "password": "", "email": ""}
        return services.append_collection_template(response, template_data)


class UserGroupList(generics.ListAPIView):
    """
    A view for a user-specific collection of groups.
    """
    http_method_names = ['get']
    queryset = User.objects.all()
    serializer_class = GroupSerializer
    permission_classes = (permissions.IsAuthenticated, )

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the groups for the queried user.
        Document-level link relations are also added to the response.
        """
        queryset = self.get_groups_queryset()
        response = services.get_list_response(self, queryset)
        user = self.get_object()
        links = {'user': reverse('user-detail', request=request,
                                   kwargs={"pk": user.id})}
        return services.append_collection_links(response, links)

    def get_groups_queryset(self):
        """
        Custom method to get the actual groups queryset for the user.
        """
        user = self.get_object()
        return user.groups.all()


class UserDetail(generics.RetrieveUpdateAPIView):
    http_method_names = ['get', 'put']
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated, IsUserOrChrisOrReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = Response(serializer.data)
        template_data = {"password": "", "email": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to add required username before serializer validation.
        """
        user = self.get_object()
        request.data['username'] = user.username
        return super(UserDetail, self).update(request, *args, **kwargs)

    def perform_update(self, serializer):
        """
        Overriden to update user's password and email when requested by a PUT request.
        """
        serializer.save(email=serializer.validated_data.get("email"))
        user = self.get_object()
        password = serializer.validated_data.get("password")
        user.set_password(password)
        user.save()

class GroupList(generics.ListCreateAPIView):
    """
    A view for the collection of groups that can be used by ChRIS admins to add a new
    group through a REST API (alternative to the HTML-based admin site).
    """
    http_method_names = ['get', 'post']
    serializer_class = GroupSerializer
    queryset = Group.objects.all()
    permission_classes = (permissions.IsAdminUser,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template to the response.
        """
        response = super(GroupList, self).list(request, *args, **kwargs)

        # append query list
        query_list = [reverse('group-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)

        # append write template
        template_data = {'name': ''}
        return services.append_collection_template(response, template_data)


class GroupListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of groups resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = GroupSerializer
    queryset = Group.objects.all()
    permission_classes = (permissions.IsAdminUser,)
    filterset_class = GroupFilter


class GroupDetail(generics.RetrieveDestroyAPIView):
    """
    A view for a group that can be used by ChRIS admins to delete the
    group through a REST API.
    """
    http_method_names = ['get', 'delete']
    serializer_class = GroupSerializer
    queryset = Group.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsAdminOrReadOnly)


class GroupUserList(generics.ListCreateAPIView):
    """
    A view for a group-specific collection of users.
    """
    http_method_names = ['get', 'post']
    queryset = Group.objects.all()
    serializer_class = GroupUserSerializer
    permission_classes = (permissions.IsAdminUser, )

    def perform_create(self, serializer):
        """
        Overriden to associate an owner with the tag before first saving to the DB.
        """
        user = serializer.validated_data.pop('username')
        group = self.get_object()
        if group.user_set.filter(username=user.username).exists():
            raise serializers.ValidationError(
                {'non_field_errors': [f"User '{user.username}' already in group '"
                                      f"{group.name}'."]})
        serializer.save(user=user, group=group)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the users for the queried group.
        Document-level link relations and a collection+json template are also added
        to the response.
        """
        queryset = self.get_users_queryset()
        response = services.get_list_response(self, queryset)
        group = self.get_object()
        links = {'group': reverse('group-detail', request=request,
                                   kwargs={"pk": group.id})}
        response = services.append_collection_links(response, links)
        template_data = {"username": ""}
        return services.append_collection_template(response, template_data)

    def get_users_queryset(self):
        """
        Custom method to get the actual users queryset for the group.
        """
        group = self.get_object()
        return User.groups.through.objects.filter(group=group)


class GroupUserDetail(generics.RetrieveDestroyAPIView):
    """
    A view for a group-user relationship that can be used by ChRIS admins to delete
    a user from a group through a REST API.
    """
    http_method_names = ['get', 'delete']
    serializer_class = GroupUserSerializer
    queryset = User.groups.through.objects.all()
    permission_classes = (permissions.IsAdminUser,)
