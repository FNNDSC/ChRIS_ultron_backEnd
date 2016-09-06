from pacs_base import PACSBase

class PACSPing(PACSBase):
    """docstring for PACSPing."""
    def __init__(self, arg):
        super(PACSPing, self).__init__(arg)
        self.arg = arg
        self.executable = 'echoscu'

    def prepareQuery(self):
        self.query = ' --timeout 5' #5s timeout

    def run(self):
        # prepare the query parameters
        self.prepareQuery()
        # prepare and run the command
        response = super(PACSPing, self).run()
        # handle response
        self.handle(response)

    def handle(self, response):
        print('handle PACSPing')
        print(response)
        stdout = response.stdout.decode('ascii')
        stderr = response.stderr.decode('ascii')
        print(stdout)
        print(stderr)
