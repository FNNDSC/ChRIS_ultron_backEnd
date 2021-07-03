#!/usr/bin/env python

import time
import sys
import psycopg2
from argparse import ArgumentParser

# django needs to be loaded
import django
django.setup()

from django.core.management import call_command

from core.models import ChrisInstance


parser = ArgumentParser(description="Check database service connection")
parser.add_argument('-u', '--user', help="Database user name")
parser.add_argument('-p', '--password', help="Database user password")
parser.add_argument('-d', '--database', help="Database name")
parser.add_argument('--host', help="Database host")
parser.add_argument('--max-attempts', type=int, dest='attempts',
                    help="Maximum number of connection attempts")
parser.add_argument('--noinput', action='store_true',
                    help="Perform migrations in non-interactive mode")


# Parse the arguments and perform the appropriate action
args = parser.parse_args()

host = args.host if args.host else 'localhost'
max_tries = args.attempts if args.attempts else 30
db = None
while max_tries > 0 and db is None:
    try:
        db = psycopg2.connect(host=host, user=args.user, password=args.password,
                              dbname=args.database)
    except Exception:
        time.sleep(5)
        max_tries -= 1

if db is None:
    print('Could not connect to database service!')
    sys.exit(1)
else:
    print('Database service ready to accept connections!')
    if args.noinput:
        call_command("migrate", interactive=False)
    else:
        call_command("migrate", interactive=True)
    ChrisInstance.load()
