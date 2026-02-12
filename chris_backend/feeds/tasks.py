
import logging

from celery import shared_task
from .models import Feed


logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3})
def delete_feed(self, feed_id):
    try:
        feed = Feed.objects.get(id=feed_id)

        if not feed.is_pending_deletion():
            return # idempotent safety

        feed.delete()
    except Feed.DoesNotExist:
        pass
    except Exception as e:
        Feed.objects.filter(id=feed_id).update(  # atomic update
            deletion_status=Feed.DeletionStatus.FAILED,
            deletion_error=str(e)
        )
        raise
