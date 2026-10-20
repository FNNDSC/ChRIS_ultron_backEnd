
from unittest import mock

from django.test import SimpleTestCase

from core.testrunner import TerminateConnectionsTestRunner


@mock.patch('django.test.runner.DiscoverRunner.teardown_databases')
@mock.patch('core.testrunner.connection')
class TerminateConnectionsTestRunnerTests(SimpleTestCase):
    """
    Test which sessions the test runner terminates before dropping the test database.
    """

    def test_terminates_nothing_when_no_test_database_was_created(self, connection,
                                                                 teardown):
        TerminateConnectionsTestRunner().teardown_databases([])

        connection.cursor.assert_not_called()
        teardown.assert_called_once_with([])

    def test_terminates_the_other_sessions_on_the_test_database(self, connection,
                                                               teardown):
        connection.settings_dict = {'NAME': 'test_chris_dev'}
        old_config = [(mock.Mock(), 'chris_dev', True)]

        TerminateConnectionsTestRunner().teardown_databases(old_config)

        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once_with(mock.ANY, ['test_chris_dev'])
        teardown.assert_called_once_with(old_config)
