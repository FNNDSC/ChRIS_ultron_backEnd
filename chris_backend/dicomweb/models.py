from django.db import models


class PACSInstance(models.Model):
    """
    DICOM Instance-level metadata index for a single PACSFile.

    Created at ingest by ``dicomweb.tasks.index_pacs_instance``; consumed by
    the QIDO-RS read surface. Patient/Study/Series tags live on ``PACSSeries``
    (single source of truth); only Instance-level tags are stored here.
    """
    series = models.ForeignKey(
        'pacsfiles.PACSSeries',
        on_delete=models.CASCADE,
        related_name='instances',
    )
    pacs_file = models.OneToOneField(
        'pacsfiles.PACSFile',
        on_delete=models.CASCADE,
        related_name='dicom_instance',
    )

    SOPClassUID = models.CharField(max_length=100, db_index=True)
    SOPInstanceUID = models.CharField(max_length=100, db_index=True)
    InstanceNumber = models.IntegerField(blank=True, null=True)
    Rows = models.IntegerField(blank=True, null=True)
    Columns = models.IntegerField(blank=True, null=True)
    BitsAllocated = models.IntegerField(blank=True, null=True)
    NumberOfFrames = models.IntegerField(blank=True, null=True)
    TransferSyntaxUID = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('series', 'SOPInstanceUID')
        ordering = ('series', 'InstanceNumber', 'SOPInstanceUID')

    def __str__(self):
        return self.SOPInstanceUID
