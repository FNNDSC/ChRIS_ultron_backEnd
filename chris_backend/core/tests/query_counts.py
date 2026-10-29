
from django.db import connection
from django.test.utils import CaptureQueriesContext


class QueryCountAssertionsMixin:
    """
    Assertions on the number of database queries a list view runs. They catch a view
    that fetches the related objects of every listed item with a query of their own
    (N+1). Mix into a TestCase whose client can GET the list.
    """

    def assertQueriesPerListItem(self, url, add_items, queries_per_item=0):
        """
        Assert that a GET of a list url runs queries_per_item more queries for every
        item that add_items() adds to the list (none by default). All the items must fit
        in one page. A first request fills any one-time cache. Return the response from
        after the items were added.
        """
        self.client.get(url)

        with CaptureQueriesContext(connection) as before:
            response = self.client.get(url)
        items_before = len(response.data['results'])

        add_items()

        with CaptureQueriesContext(connection) as after:
            response = self.client.get(url)
        added = len(response.data['results']) - items_before

        self.assertGreater(added, 0, 'add_items() added nothing to the list')
        queries = '\n'.join(query['sql'] for query in after.captured_queries)
        self.assertEqual(
            len(after) - len(before), queries_per_item * added,
            f'{len(before)} queries for {items_before} items but {len(after)} for '
            f'{items_before + added}, which ran:\n{queries}')
        return response
