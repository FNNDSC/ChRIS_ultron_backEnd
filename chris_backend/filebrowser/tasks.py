
import logging

from celery import shared_task
from core.models import ChrisFolder


logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3})
def delete_folder(self, folder_id):
    try:
        folder = ChrisFolder.objects.get(id=folder_id)

        if not folder.is_pending_deletion():
            return # idempotent safety

        folder.delete()
    except ChrisFolder.DoesNotExist:
        pass
    except Exception as e:
        ChrisFolder.objects.filter(id=folder_id).update(  # atomic update
            deletion_status=ChrisFolder.DeletionStatus.FAILED,
            deletion_error=str(e)
        )
        raise
