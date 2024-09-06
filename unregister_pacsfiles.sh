#!/usr/bin/env bash

docker compose -f docker-compose_dev.yml exec chris_dev pip install tqdm
docker compose -f docker-compose_dev.yml exec chris_dev python manage.py shell -c '
from tqdm import tqdm
from pacsfiles.models import PACSSeries, PACSFile

with tqdm(PACSFile.objects.all()) as pbar:
    for pacs_file in pbar:
        _ = pacs_file.delete()

with tqdm(PACSSeries) as pbar:
    for pacs_series in pbar:
        _ = pacs_series.delete()
'
