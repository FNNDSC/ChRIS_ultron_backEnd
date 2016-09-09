from pacs_echo import PACSEcho
from pacs_find import PACSFind
from pacs_move import PACSMove

class PACS(object):
    """docstring for PACS."""
    def __init__(self, arg={}):
        self.arg = arg

        if 'aet' in self.arg:
            self.aet = self.arg['aet']
        else:
            self.aet = 'CHRIS-ULTRON-AET'

        if 'aec' in self.arg:
            self.aec = self.arg['aec']
        else:
            self.aec = 'CHRIS-ULTRON-AEC'

        if 'server_ip' in self.arg:
            self.server_ip = self.arg['server_ip']
        else:
            self.server_ip = '192.168.1.110'

        if 'server_port' in self.arg:
            self.server_port = self.arg['server_port']
        else:
            self.server_port = '4241'

        self.query = ''
        self.command_suffix = ''
        self.commandSuffix()

        self.response = {
            'status': 'error',
            'data': {}
        }

    def commandSuffix(self):
        # required parameters
        self.command_suffix = ' -aec ' + self.aec
        self.command_suffix += ' -aet ' + self.aet
        self.command_suffix += ' ' + self.server_ip
        self.command_suffix += ' ' + self.server_port

    def echo(self, opt={}):
        echo = PACSEcho(self.command_suffix)
        return echo.run(opt)

    def find(self, opt={}):
        find = PACSFind(self.command_suffix)
        return find.run(opt)

    def move(self, opt={}):
        move = PACSMove(self.command_suffix)
        return move.run(opt)
