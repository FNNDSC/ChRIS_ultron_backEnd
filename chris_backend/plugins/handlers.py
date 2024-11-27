from corsheaders.signals import check_request_enabled
import re

_ALLOWED = re.compile(r'/api/v1/plugins/(metas/)?(search/)?(\d+/)?')


def cors_allow_api_to_everyone(sender, request, **kwargs):
    return _ALLOWED.fullmatch(request.path)


check_request_enabled.connect(cors_allow_api_to_everyone)

