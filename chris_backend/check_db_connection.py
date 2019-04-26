#!/usr/bin/env python

import time
import MySQLdb
from argparse import ArgumentParser


parser = ArgumentParser(description="Check database service connection")
parser.add_argument('-u', '--user', help="Database user name")
parser.add_argument('-p', '--password', help="Database user password")
parser.add_argument('--host', help="Database host")
parser.add_argument('--max-attempts', type=int, dest='attempts',
                    help="Maximum number of connection attempts")


# Parse the arguments and perform the appropriate action
args = parser.parse_args()

host = args.host if args.host else 'localhost'
max_tries = args.attempts if args.attempts else 20
db = None
while max_tries > 0 and db is None:
    try:
        db = MySQLdb.connect(user=args.user,
                     passwd=args.password,
                     host=host)
    except Exception:
        time.sleep(2)
        max_tries -= 1

if db is None:
    print('Could not connect to database service!')
else:
    print('Database service ready to accept connections!')


