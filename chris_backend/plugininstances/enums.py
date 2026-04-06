STATUS_CHOICES = [("created", "Default initial"),
                  ("waiting", "Waiting to be scheduled"),
                  ("copying", "Copying files to compute env"),  # when supported
                  ("scheduled", "Scheduled on worker"),
                  ("started", "Started on compute env"),
                  ("uploading", "Uploading files from compute env"),  # when supported
                  ("registeringFiles", "Registering output files"),
                  ("finishedSuccessfully", "Finished successfully"),
                  ("finishedWithError", "Finished with error"),
                  ("cancelled", "Cancelled")]

ACTIVE_STATUSES = ['created', 'waiting', 'copying', 'scheduled', 'started', 'uploading',
                   'registeringFiles']

INACTIVE_STATUSES = ['finishedSuccessfully', 'finishedWithError', 'cancelled']

REMOTE_CLEANUP_STATUS_CHOICES = [
    ('notStarted', 'Not started'),
    ('deletingData', 'Deleting remote data'),
    ('deletingContainers', 'Deleting remote containers'),
    ('complete', 'Cleanup complete'),
    ('failed', 'Cleanup failed'),
]

