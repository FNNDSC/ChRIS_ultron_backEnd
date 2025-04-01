
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

from .models import UserProxy


class UserProxyAdmin(admin.ModelAdmin):
    readonly_fields = []

    def add_view(self, request, form_url='', extra_context=None):
        """
        Overriden to make the username field read-write on the add view.
        """
        if 'username' in UserProxyAdmin.readonly_fields:
            UserProxyAdmin.readonly_fields.remove('username')

        return admin.ModelAdmin.add_view(self, request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Overriden to make the username field read-only on the change view.
        """
        if 'username' not in UserProxyAdmin.readonly_fields:
            UserProxyAdmin.readonly_fields.append('username')

        return admin.ModelAdmin.change_view(self, request, object_id, form_url,
                                            extra_context)

    def save_model(self, request, obj, form, change):
        """
        Overriden to take care of the password hashing and setup groups and home folder.
        """
        if 'password' in form.changed_data:
            obj.password = make_password(obj.password)

        super().save_model(request, obj, form, change)


admin.site.unregister(User)
admin.site.register(UserProxy, UserProxyAdmin)
