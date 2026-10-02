"""Bound workbook bodies before CSRF's multipart parsing, including chunked uploads."""
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.http import HttpResponse

from .sop_imports import MAX_UPLOAD


class WorkbookUploadLimit(FileUploadHandler):
    def receive_data_chunk(self, raw_data, start):
        if start + len(raw_data) > MAX_UPLOAD:
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None


class WorkbookUploadLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path == "/admin-panel/import/workbook/":
            try:
                length = int(request.META.get("CONTENT_LENGTH") or 0)
            except ValueError:
                return HttpResponse("Invalid upload length.", status=400)
            if length > MAX_UPLOAD + 1024 * 1024:
                return HttpResponse("Workbook upload is too large.", status=413)
            request.upload_handlers.insert(0, WorkbookUploadLimit(request))
        return self.get_response(request)
