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
        ping_response = super(PACSPing, self).run()
        # handle response
        return self.handle(ping_response)

    def handle(self, ping_response):
        print('handle PACSPing')
        print(ping_response)
        std = ping_response.stdout.decode('ascii')
        print(std)
        if std != '':
            self.response['status'] = 'error';
            self.response['data'] = std;
        else:
            self.response['status'] = 'success';

        return self.response
