#!/usr/bin/env python3

import  logging
logging.disable(logging.CRITICAL)

import  os
import  sys
import  json
import  socket
import  requests

import  pudb

import  pfmisc

# pfstorage local dependencies
from    pfmisc._colors      import  Colors
from    pfmisc.debug        import  debug
from    pfmisc.C_snode      import  *
from    pfstate             import  S

from    argparse            import RawTextHelpFormatter
from    argparse            import ArgumentParser


str_desc        = """

    NAME

        plugin_search.py

    PREREQUISITES

        The python `pfmisc` and `pfstate` modules:

            pip install -U pfmisc pfstate

    SYNOPSIS

        plugin_search.py        --for <someField(s)>                    \\
                                --using <someTemplateDesc>              \\
                                [--version]                             \\
                                [--man]                                 \\
                                [--jsonReturn]                          \\
                                [--syslogPrepend]                       \\
                                [--verbosity <level>]

    ARGS

        --for <someField(s)>
        A comma separated list of fields to return from the plugin search.
        Results are typically printed in a "table", with each row containing
        the value for each of the `for` fields.

        Typical examples:

            --for name
            --for name,id

        --using <someTemplateDesc>
        The search condition/pattern to apply. This is typically some
        value relevant to the plugin description as referenced with the
        CUBE API.

        The <someTemplateDesc> can be a compound string that is comma
        separated. For instance 'type=ds,name=pfdo' will search for all
        plugins that have 'pfdo' in their name and 'ds' as their type.

        Typical examples:

            --using name=pl-fshack
            --using name=dicom,type=ds

        [--version]
        Print the version and exit.

        [--jsonReturn]
        If specified, print the full JSON return from the API call and
        various class methods that apply processing to the API call.

        [--syslogPrepend]
        If specified, prepend pseudo (colorized) syslog info to output
        print calls.

        [--verbosity <level>]
        Apply a verbosity to the output.


    DESCRIPTION

        `plugin_search.py` provides for a simple CLI mechanism to search
        a CUBE instance plugin space for various detail. Given, for example,
        a plugin name, return the plugin ID, or given a plugin type, return
        all names.

        The primary purpose of this script is a helper component in creating
        autonomous feeds to a ChRIS instance from some stand-alone script,
        although it is quite well suited as a CLI mechanism to query for
        information on various plugins in a CUBE instantiation.

    EXAMPLES

    * List by name all the DS plugins in a CUBE instance:

        $ python plugin_search.py --for name --using type=ds
        (type=ds)       name    pl-pfdo_med2img
        (type=ds)       name    pl-pfdo_mgz2img
        (type=ds)       name    pl-mgz2lut_report
        (type=ds)       name    pl-z2labelmap
        (type=ds)       name    pl-freesurfer_pp
        (type=ds)       name    pl-fastsurfer_inference
        (type=ds)       name    pl-fshack
        (type=ds)       name    pl-mpcs
        (type=ds)       name    pl-pfdicom_tagsub
        (type=ds)       name    pl-pfdicom_tagextract

    * List by name all DS plugins that also have 'dicom' in their name:

        $ python plugin_search.py --for name --using type=ds,name=dicom
        (type=ds,name=dicom)    name    pl-pfdicom_tagsub
        (type=ds,name=dicom)    name    pl-pfdicom_tagextract

    * Find the ID of the `pl-fshack` plugin:

        $ python plugin_search.py --for id --using name=pl-fshack
        (name=pl-fshack)        id      10

    * List all the plugins (assuming they all start with `pl`) by
      name, id, and plugin type:

        $ python plugin_search.py --for name,id,type --using name=pl
        (name=pl)      name pl-pfdo_med2img                  id 17     type ds
        (name=pl)      name pl-pfdo_mgz2img                  id 16     type ds
        (name=pl)      name pl-mgz2lut_report                id 15     type ds
        (name=pl)      name pl-z2labelmap                    id 13     type ds
        (name=pl)      name pl-freesurfer_pp                 id 12     type ds
        (name=pl)      name pl-fastsurfer_inference          id 11     type ds
        (name=pl)      name pl-fshack                        id 10     type ds
        (name=pl)      name pl-mpcs                          id 9      type ds
        (name=pl)      name pl-pfdicom_tagsub                id 8      type ds
        (name=pl)      name pl-pfdicom_tagextract            id 7      type ds
        (name=pl)      name pl-s3push                        id 6      type ds
        (name=pl)      name pl-dsdircopy                     id 5      type ds
        (name=pl)      name pl-s3retrieve                    id 3      type ds
        (name=pl)      name pl-simpledsapp                   id 2      type ds
        (name=pl)      name pl-mri10yr06mo01da_normal        id 14     type fs
        (name=pl)      name pl-dircopy                       id 4      type fs
        (name=pl)      name pl-simplefsapp                   id 1      type fs

"""

# Determine the hostIP
str_defIP   = [l for l in (
                [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2]
                if not ip.startswith("127.")][:1],
                    [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close())
                for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]


str_version     = "1.0.0"
str_name        = "plugin_search.py"
parser          = ArgumentParser(
                    description     = str_desc,
                    formatter_class = RawTextHelpFormatter
)

parser.add_argument(
    '--version',
    help    = 'if specified, print verion',
    action  = 'store_true',
    dest    = 'b_version',
    default = False,
)
parser.add_argument(
    '--man', '-x',
    help    = 'if specified, show help and exit',
    action  = 'store_true',
    dest    = 'b_man',
    default = False,
)
parser.add_argument(
    '--syslogPrepend',
    help    = 'if specified, prepend syslog info to output',
    action  = 'store_true',
    dest    = 'b_syslog',
    default = False,
)
parser.add_argument(
    '--jsonReturn',
    help    = 'if specified, return results as JSON',
    action  = 'store_true',
    dest    = 'b_json',
    default = False,
)
parser.add_argument(
    '--for',
    help    = 'property for which to search',
    action  = 'store',
    dest    = 'str_for',
    default = '',
)
parser.add_argument(
    '--using',
    help    = 'search template in <key>=<value>[,..] form',
    action  = 'store',
    dest    = 'str_using',
    default = '',
)
parser.add_argument(
    '--verbosity',
    help    = 'the system verbosity',
    action  = 'store',
    dest    = 'verbosity',
    default = 1,
)

args        = parser.parse_args()

class D(S):
    """
    A derived 'pfstate' class that keeps system state.

    See https://github.com/FNNDSC/pfstate for more information.
    """

    def __init__(self, *args, **kwargs):
        """
        An object to hold some generic/global-ish system state, in C_snode
        trees.
        """
        self.state_create(
        {
            "CUBE":
            {
                "protocol": "http",
                "port":     "8000",
                "address":  "%HOSTIP",
                "user":     "chris",
                "password": "chris1234",
            },
            "self":
            {
                'httpProxy':
                {
                    'use':          False,
                    'httpSpec':     ''
                }
            }
        },
        *args, **kwargs)

class PluginSearch(object):
    """
    A class that interacts with CUBE via the collection+json API
    and is specialized to perform searches on the plugin space.
    """

    def S(self, *args):
        """
        set/get components of the state object
        """
        if len(args) == 1:
            return self.state.T.cat(args[0])
        else:
            self.state.T.touch(args[0], args[1])

    def __init__(self, *args, **kwargs):
        """
        Class constructor.
        """
        self.d_args     = vars(*args)
        self.state      = D(
            version     = str_version,
            name        = str_name,
            desc        = str_desc,
            args        = vars(*args)
        )
        self.dp         = pfmisc.debug(
            verbosity   = int(self.d_args['verbosity']),
            within      = str_name,
            syslog      = self.d_args['b_syslog']
        )
        # Check the IP in the state structure and optionally update
        IP = self.S('/CUBE/address')
        if IP == "%HOSTIP":
            self.S('/CUBE/address', str_defIP)

    def search_templatize(self):
        """
        Parse the CLI '--using <template>' and return a dictionary
        of parameters to search.

        The <template> value is of form:

            name_exact=<name>,version=<version>,[<key>=<value>,...]

        and is returned as

            {
                'name_exact':   <name>,
                'version':      <version>[,
                <key>:          <value>]
            }

        """
        b_status    : bool      = False
        d_params    : dict      = {}
        str_message : str       = ''
        paramCount  : int       = 0

        if 'str_using' in self.d_args.keys():
            if len(self.d_args['str_using']):
                l_using     = self.d_args['str_using'].split(',')
                for param in l_using:
                    l_keyVal    = param.split('=')
                    d_params[l_keyVal[0]]   = l_keyVal[1]
                    paramCount += 1
                    b_status    = True
                str_message = '%d parameters templatized' % paramCount
            else:
                str_message = "'--using' value is zero length"
        else:
            str_message     = "'--using' not in CLI args"

        return {
            'status':   b_status,
            'message':  str_message,
            'params':   d_params
        }

    def search_CUBEAPIcall(self):
        """

        This method implements the actual search logic.

        """
        d_resp              : dict  = {}
        d_templatize        : dict  = self.search_templatize()
        b_status            : bool  = False

        if d_templatize['status']:
            d_params    = d_templatize['params']
            d_headers           : dict = {
                'Accept':   'application/vnd.collection+json'
            }
            d_resp              : dict = {}
            str_dataServiceAddr : str  = "%s://%s:%s" % (
                                    self.S('/CUBE/protocol'),
                                    self.S('/CUBE/address'),
                                    self.S('/CUBE/port')
                                )
            str_dataServiceURL  : str  = 'api/v1/plugins/search/?limit=100'
            str_user            : str  = self.S('/CUBE/user')
            str_passwd          : str  = self.S('/CUBE/password')
            str_URL             : str  = '%s/%s' % (
                                    str_dataServiceAddr,
                                    str_dataServiceURL
                                )
            try:
                resp = requests.get(
                                    str_URL,
                                    params  = d_params,
                                    auth    = (str_user, str_passwd),
                                    timeout = 30,
                                    headers = d_headers
                        )
                b_status    = True
            except (requests.exceptions.Timeout,
                    requests.exceptions.RequestException) as e:
                logging.error(str(e))
                raise
            d_resp = resp.json()
        return {
            'status':   b_status,
            'response': d_resp
        }

    def search_desiredReturnFind(self, d_search):
        """
        For a given search response from CUBE, return the
        specific value sought.
        """
        b_status        :   bool    = False
        l_thistarget    :   list    = []
        l_target        :   list    = []

        if d_search['status']:
            if d_search['response']['collection']['total']:
                for d_hit in d_search['response']['collection']['items']:
                    l_data  :   list = d_hit['data']
                    l_thistarget     = []
                    for str_desired in self.d_args['str_for'].split(','):
                        l_hit   :   list = list(
                                    filter(
                                        lambda info: info['name'] == str_desired, l_data
                                        )
                                    )
                        if len(l_hit):
                            l_thistarget.append(l_hit[0])
                            b_status    = True
                    l_target.append(l_thistarget)

        return {
            'status':   b_status,
            'search':   d_search,
            'target':   l_target
        }

    def do(self):
        """
        Main entry point to this class.
        """
        d_result    = self.search_desiredReturnFind(self.search_CUBEAPIcall())
        return d_result

def main(*args):
    """
    The main method of the script, when called directly from the CLI
    """
    retCode     : int   = 1
    search      = PluginSearch(args[0])
    d_result    = search.do()

    if search.d_args['b_man']:
        print(str_desc)
        sys.exit(0)

    if search.d_args['b_version']:
        print(str_version)
        sys.exit(0)

    if search.d_args['b_json']:
        search.dp.qprint(json.dumps(d_result, indent = 4))
        if len(d_result['target']):
            retCode = 0
    else:
        for target in d_result['target']:
            search.dp.qprint('(%s)' % search.d_args['str_using'], end='')
            for hit in target:
                search.dp.qprint('%10s %-30s' % (hit['name'], hit['value']), end='', syslog=False)
            search.dp.qprint('')
            retCode = 0

    sys.exit(retCode)

if __name__ == "__main__":
    main(args)
