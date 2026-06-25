from django.db import models


class PACSStudy(models.Model):
    """
    Study-level entity for the DICOM hierarchy (Patient → Study → Series → Instance).

    Created or reused by ``PACSSeriesSerializer.create`` on every series ingest.
    Patient tags are denormalized from the first series. Counter fields are
    maintained by the signal receivers in ``dicomweb.signals`` (wired up in
    ``dicomweb.apps``) using F() expressions.
    """
    creation_date = models.DateTimeField(auto_now_add=True)
    pacs = models.ForeignKey(
        'pacsfiles.PACS',
        on_delete=models.CASCADE,
        related_name='studies',
    )
    StudyInstanceUID = models.CharField(max_length=100, db_index=True)
    StudyDate = models.DateField(null=True, blank=True, db_index=True)
    StudyTime = models.TimeField(null=True, blank=True)
    AccessionNumber = models.CharField(max_length=100, blank=True, db_index=True)
    StudyDescription = models.CharField(max_length=400, blank=True)
    # Patient tags — denormalized from first series
    # PatientName matches PACSSeries and is served by a pg_trgm GIN index
    PatientName = models.CharField(max_length=150, blank=True)
    PatientID = models.CharField(max_length=100, blank=True, db_index=True)
    PatientBirthDate = models.DateField(null=True, blank=True)
    PatientSex = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female'),
                                                         ('O', 'Other')], blank=True)
    # Maintained counters (updated via F() to avoid race conditions)
    NumberOfStudyRelatedSeries = models.PositiveIntegerField(default=0)
    NumberOfStudyRelatedInstances = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('pacs', 'PatientID',)
        unique_together = ('pacs', 'StudyInstanceUID',)
        indexes = [
            models.Index(fields=['pacs', 'StudyDate'], name='pacsstudy_pacs_date_idx'),
        ]

    def __str__(self):
        return self.StudyInstanceUID


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

    SOPClassUID = models.CharField(max_length=100, blank=True, db_index=True)
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
