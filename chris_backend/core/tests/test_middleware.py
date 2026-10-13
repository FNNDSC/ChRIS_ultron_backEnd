
import asyncio
import threading

from django.core.handlers.asgi import ASGIHandler
from django.db import connections
from django.http import JsonResponse
from django.test import TransactionTestCase, override_settings
from django.urls import path

from core.models import ChrisFolder
from core.utils import db_pool_stats


#: lets the holding view report that it holds a connection, then wait to be released
HOLD = {'entered': threading.Semaphore(0), 'released': threading.Event()}


def failing_view(request):
    # never evaluated here, so the DEBUG 500 page queries the database to print it
    folders = ChrisFolder.objects.all()  # noqa: F841
    raise RuntimeError('failing view')


def holding_view(request):
    ChrisFolder.objects.exists()
    HOLD['entered'].release()
    HOLD['released'].wait(10)
    return JsonResponse({'held': True})


def counting_view(request):
    return JsonResponse({'folders': ChrisFolder.objects.count()})


urlpatterns = [
    path('failing/', failing_view),
    path('holding/', holding_view),
    path('counting/', counting_view),
]


async def asgi_get(app, path, client=None, disconnected=None):
    """
    Send a GET request through the ASGI ``app`` and return the response status, or None
    if no response was started. After the request, ``receive()`` delivers what the test
    puts on the ``client`` queue (an ``http.disconnect`` drops the client), and sets the
    ``disconnected`` event once it has handed a disconnect to the app.
    """
    client = client or asyncio.Queue()
    sent_request = False
    messages = []

    async def receive():
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        message = await client.get()
        if message['type'] == 'http.disconnect' and disconnected is not None:
            disconnected.set()
        return message

    async def send(message):
        messages.append(message)

    scope = {
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
        'method': 'GET', 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
        'query_string': b'', 'root_path': '', 'server': ('testserver', 80),
        'headers': [(b'host', b'testserver'), (b'accept', b'application/json')],
    }
    await app(scope, receive, send)
    starts = [m for m in messages if m['type'] == 'http.response.start']
    return starts[0]['status'] if starts else None


async def concurrent_failing_requests(app, n):
    return await asyncio.wait_for(
        asyncio.gather(*(asgi_get(app, '/failing/') for _ in range(n))), 30)


async def dropped_holding_requests(app, holders):
    """
    Start ``holders`` requests that each hold a connection, plus one that has to wait
    for one, drop all their clients while they are stuck, then let them finish.
    """
    clients = [asyncio.Queue() for _ in range(holders + 1)]
    disconnects = [asyncio.Event() for _ in clients]
    requests = [asyncio.create_task(asgi_get(app, '/holding/', client, disconnected))
                for client, disconnected in zip(clients, disconnects)]
    try:
        for _ in range(holders):
            if not await asyncio.to_thread(HOLD['entered'].acquire, timeout=10):
                raise AssertionError('the holding requests did not get their connections')
        for client in clients:
            client.put_nowait({'type': 'http.disconnect'})
        await asyncio.wait_for(asyncio.gather(*(d.wait() for d in disconnects)), 10)
        await asyncio.sleep(0.1)  # let the handler cancel the requests
    finally:
        HOLD['released'].set()
    return await asyncio.wait_for(asyncio.gather(*requests), 30)


@override_settings(ROOT_URLCONF=__name__)
class ASGIConnectionPoolTests(TransactionTestCase):
    """
    Requests served by Django's ASGI handler through CUBE's middleware must give every
    connection they take from the psycopg pool back to it, however they end.

    The tests are synchronous and run the requests with ``asyncio.run()``, like an ASGI
    server: in an ``async def`` test the test runner's thread would be the parent sync
    thread of every request, and they would all run their sync code on it.
    """

    def setUp(self):
        # the test's own thread must not hold a connection while the requests run
        connections.close_all()
        stats = db_pool_stats()
        self.checked_out = stats['checked_out']
        self.requests_num = stats.get('requests_num', 0)
        HOLD['entered'] = threading.Semaphore(0)
        HOLD['released'] = threading.Event()

    def tearDown(self):
        HOLD['released'].set()
        # start the next test with a fresh pool, whatever this one left checked out
        connections.close_all()
        connections['default'].close_pool()

    @override_settings(DEBUG=True)
    def test_error_pages_return_their_connections(self):
        """
        Under DEBUG, ResponseMiddleware re-raises a view's exception and Django renders
        its 500 page, which queries the database to print the failing view's QuerySet.
        Unless that happens on the request's own thread, the connection never goes back
        to the pool (Django ticket #36027, see core.middleware.convert_exception_to_response).
        """
        app = ASGIHandler()
        n = db_pool_stats()['pool_max'] + 1

        with self.assertLogs('django.request', 'ERROR'):
            statuses = asyncio.run(concurrent_failing_requests(app, n))

        self.assertEqual(statuses, [500] * n)
        stats = db_pool_stats()
        # each 500 page did query the database, so the test proves something
        self.assertGreaterEqual(stats.get('requests_num', 0) - self.requests_num, n)
        self.assertEqual(stats['checked_out'], self.checked_out)
        self.assertEqual(asyncio.run(asgi_get(app, '/counting/')), 200)

    def test_dropped_clients_return_their_connections(self):
        """
        Clients that disconnect while their request holds a connection, or is still
        waiting for one, leave all the connections in the pool once the requests end.
        """
        app = ASGIHandler()
        holders = db_pool_stats()['pool_max']

        statuses = asyncio.run(dropped_holding_requests(app, holders))

        # the handler cancelled every dropped request: none of them started a response
        self.assertEqual(statuses, [None] * (holders + 1))
        self.assertEqual(db_pool_stats()['checked_out'], self.checked_out)
        self.assertEqual(asyncio.run(asgi_get(app, '/counting/')), 200)
