
from django.contrib import admin
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token


admin.site.site_header = 'ChRIS Administration'
admin.site.site_title = 'ChRIS Admin'
admin.site.site_url = '/'
admin.site.unregister(Group)
admin.site.unregister(Token)
