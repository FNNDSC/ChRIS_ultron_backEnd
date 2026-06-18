import json

from rest_framework.renderers import BaseRenderer, JSONRenderer


class DicomJsonRenderer(BaseRenderer):
    """
    Renders QIDO-RS / WADO-RS responses as DICOM JSON Model arrays (PS3.18 §F).

    The response data must already be a list of DICOM JSON dataset dicts
    (as produced by ``dicomweb.dicomjson.dataset()``).
    """
    media_type = 'application/dicom+json'
    format = 'dicom+json'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data, ensure_ascii=False).encode('utf-8')


class ApplicationJsonDicomRenderer(JSONRenderer):
    """
    Alias renderer: same DICOM JSON shape, Content-Type: application/json.
    Useful for curl/debugging without setting Accept headers explicitly.
    """
    media_type = 'application/json'
    format = 'json'
