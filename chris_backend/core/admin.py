
from django.contrib import admin
from django.contrib.auth.models import Group

from .models import ChrisInstance


class ChrisInstanceAdmin(admin.ModelAdmin):
    readonly_fields = ['creation_date', 'uuid']
    list_display = ('name', 'uuid', 'job_id_prefix', 'creation_date')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.site_header = 'ChRIS Administration'
admin.site.site_title = 'ChRIS Admin'
admin.site.register(ChrisInstance, ChrisInstanceAdmin)
