import subprocess

class PACSEcho():
    """docstring for PACSEcho."""
    def __init__(self,command_suffix):
        self.executable = 'echoscu'
        self.command_suffix = command_suffix

    def command(self, opt=None):
        command = ' --timeout 5' #5s timeout

        return self.executable + ' ' + command + ' ' + self.command_suffix

    def run(self, options=None):
        print('run PACSEcho')

        response = subprocess.run(self.command(options), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        result = self.handle(response)
        return result

    def handle(self, echo_response):
        std = echo_response.stdout.decode('ascii')
        response = {
            'status': 'success',
            'data': ''
        }
        if std != '':
            response['status'] = 'error';
            response['data'] = std;

        return response
