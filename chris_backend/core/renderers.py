
from rest_framework.renderers import BaseRenderer


class BinaryFileRenderer(BaseRenderer):
    media_type = '*/*'
    charset = None
    render_style = 'binary'
    format = 'binary'

    def render(self, data, media_type=None, renderer_context=None):
        return data    
