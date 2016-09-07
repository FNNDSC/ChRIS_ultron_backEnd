import subprocess

class PACSBase(object):
    """docstring for PACSBase."""
    def __init__(self, arg):
        self.arg = arg

        if 'aet' in self.arg:
            self.aet = self.arg.aet
        else:
            self.aet = 'CHRIS-ULTRON-AET'

        if 'aec' in self.arg:
            self.aec = self.arg.aec
        else:
            self.aec = 'CHRIS-ULTRON-AEC'

        if 'server_ip' in self.arg:
            self.server_ip = self.arg.server_ip
        else:
            self.server_ip = '192.168.1.110'

        if 'server_port' in self.arg:
            self.server_port = self.arg.server_port
        else:
            self.server_port = '4242'

        if 'executable' in self.arg:
            self.executable = self.arg.executable
        else:
            self.executable = 'echoscu'

        self.query = ''
        self.command = ''
        self.response = {
            'status': 'error',
            'data': {}
        }

    def prepareCommand(self):
        # executable
        self.command = self.executable
        # query parameters
        self.command += ' ' + self.query
        # required parameters
        self.command += ' -aec ' + self.aec
        self.command += ' -aet ' + self.aet
        self.command += ' ' + self.server_ip
        self.command += ' ' + self.server_port


    def run(self):
        # prepare the command
        self.prepareCommand()
        # run the comnmand
        print(self.command)
        print(subprocess.PIPE)
        test = subprocess.run(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        return test
