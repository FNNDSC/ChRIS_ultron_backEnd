
import json
import threading
import time
from unittest import mock

from django.db import connection, connections
from django.test import TransactionTestCase

from core.utils import db_pool_stats, start_db_pool_stats_logger


def stop_logger(stop):
    """
    Stop a ``start_db_pool_stats_logger`` thread and wait for it to end.
    """
    stop.set()
    for thread in threading.enumerate():
        if thread.name == 'db-pool-stats':
            thread.join(5)


class DbPoolStatsTests(TransactionTestCase):
    """
    Test the database connection pool counters and their logger.
    """

    def setUp(self):
        connections.close_all()

    def test_db_pool_stats_counts_a_held_connection(self):
        before = db_pool_stats()
        connection.ensure_connection()
        held = db_pool_stats()
        connection.close()
        after = db_pool_stats()

        self.assertEqual(held['checked_out'], before['checked_out'] + 1)
        self.assertEqual(after['checked_out'], before['checked_out'])
        self.assertEqual(held['pool_max'],
                         connection.settings_dict['OPTIONS']['pool']['max_size'])

    def test_db_pool_stats_of_a_pool_not_opened_yet(self):
        connections['default'].close_pool()  # the next access creates a closed pool

        stats = db_pool_stats()

        self.assertEqual(stats['checked_out'], 0)
        self.assertEqual(stats['pool_size'],
                         connection.settings_dict['OPTIONS']['pool']['min_size'])

    def test_start_db_pool_stats_logger_does_nothing_without_interval(self):
        self.assertIsNone(start_db_pool_stats_logger(0))

    def test_start_db_pool_stats_logger_logs_json_lines(self):
        with self.assertLogs('core.utils', 'INFO') as logs:
            stop = start_db_pool_stats_logger(0.01)
            try:
                deadline = time.monotonic() + 5
                while not logs.records and time.monotonic() < deadline:
                    time.sleep(0.01)
            finally:
                stop_logger(stop)

        name, _, payload = logs.records[0].getMessage().partition(' ')
        stats = json.loads(payload)
        self.assertEqual(name, 'db_pool_stats')
        self.assertEqual(stats['alias'], 'default')
        self.assertIn('checked_out', stats)
        self.assertIn('pid', stats)

    def test_start_db_pool_stats_logger_survives_a_failing_read(self):
        with mock.patch('core.utils.db_pool_stats', side_effect=RuntimeError('no pool')):
            with self.assertLogs('core.utils', 'WARNING') as logs:
                stop = start_db_pool_stats_logger(0.01)
                try:
                    deadline = time.monotonic() + 5
                    while len(logs.records) < 2 and time.monotonic() < deadline:
                        time.sleep(0.01)
                finally:
                    stop_logger(stop)

        # it kept going after the first failure
        self.assertGreaterEqual(len(logs.records), 2)
        self.assertIn('no pool', logs.records[0].getMessage())
