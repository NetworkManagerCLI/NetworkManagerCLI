from util import LOG
from nanonet.node import *
from nanonet.net import *
import ipaddress
from mako.template import Template
from util.helper import *

class ConfigDict(dict):
    """
    A dictionary whose attributes are its keys
    """

    def __init__(self, **kwargs):
        super(ConfigDict, self).__init__()
        for key, val in kwargs.iteritems():
            self[key] = val

    def __getattr__(self, item):
        # so that self.item == self[item]
        try:
            # But preserve i.e. methods
            return super(ConfigDict, self).__getattr__(item)
        except:
            try:
                return self[item]
            except KeyError:
                return None

    def __setattr__(self, key, value):
        # so that self.key = value <==> self[key] = key
        self[key] = value


def render(filename, node, dest) :
    """
        Render file based on Mako template
    """
    text = Template(filename=filename).render(node=node)
    with open(dest, 'w') as f:
        f.write(text)
        f.close()



class QuaggaRouter(ConfigDict):
    """
        Obj representing a Quagga router
    """
    ID = 0
    def __init__(self, node) :
        """
            :param node : a Node from Nanonet
        """
        self.node = node

        self.zebraconf = file_path(ConfigDIR, 'zebra',self.node.name,'conf')
        self.zebraapi = file_path(QuaggaDIR, 'zebra',self.node.name,'api')
        self.zebrapid = file_path(QuaggaDIR, 'zebra',self.node.name,'pid')

        self.ospf6dconf = file_path(ConfigDIR, 'ospf6d',self.node.name,'conf')
        self.ospf6dpid = file_path(QuaggaDIR, 'ospf6d',self.node.name,'pid')

        self.snmppid = file_path(ConfigDIR, 'snmpd', self.node.name,'pid')

        self.sshdpid = file_path(ConfigDIR, 'sshd', self.node.name, 'pid')

        self.sragentdir = SRagentDir % (ConfigDIR, self.node.name)

        self.hostname = self.node.name
        self.password = Password
        self.ospf = ConfigDict()
        self.zebra = ConfigDict()
        self.ospf.interfaces = []

        self.ospf.logfile = file_path(ConfigDIR, 'ospf6d',self.node.name,'log')
        self.zebra.logfile = file_path(ConfigDIR, 'zebra',self.node.name,'log')

        # TODO assign router id here
        if not self.node.router_id :
            self.ospf.router_id = '0.0.0.%d' % QuaggaRouter.ID
            QuaggaRouter.ID += 1
        else :
            self.ospf.router_id = self.node.router_id


        self.setup_interface()
        self.setup_router_ospf6()

    def setup_interface(self) :
        """
            generate config for interface
        """
        self.ospf.interfaces = []
        for itf in self.node.intfs_name.keys() :
            intf = ConfigDict()
            intf.name = self.node.intfs_name[itf].name
            intf.ospf= ConfigDict()
            intf.ospf.cost = self.node.intfs_name[itf].cost
            intf.ospf.dead_int = self.node.intfs_name[itf].dead_interval
            intf.ospf.hello_int = self.node.intfs_name[itf].hello_interval
            intf.ospf.priority = 10
            intf.area = self.node.intfs_name[itf].area
            ipv6_intf = ipaddress.ip_interface(unicode(self.node.intfs_name[itf].addr))
            intf.network = str(ipv6_intf.network)
            self.ospf.interfaces.append(intf)


    def cmd(self, Cmd) :
        """
            run Cmd on the namespace
        """
        runOS(IPNETNSEXEC % (self.hostname, Cmd))
    def cmd_process(self, cmd) :
        """
            run Cmd in namespace and wait for terminaison
        """
        run_process(IPNETNSEXEC % (self.hostname, cmd))

    def setup_router_ospf6(self) :
        """
            generate config for router ospf6
        """
        self.ospf.redistribute = ConfigDict(connected=None, static=None)

    def build_zebra(self) :
        """
            generate zebra configs file
        """
        render(ZebraTEMP,
         self, self.zebraconf)

    def build_ospf6d(self) :
        """
            generate ospf6d configs file
        """
        render(ospf6dTEMP,
         self, self.ospf6dconf)

    def setup_permission(self) :
        """
            change permission on config files
        """
        cmd = IPNETNSEXEC % ( self.hostname, PermCMD % (ConfigDIR, ConfigDIR))
        runOS(cmd)

    def start_zebra(self, port=ZEBRAPORT) :
        """
            start the zebra daemon
        """
        self.setup_permission()
        cmd = IPNETNSEXEC % (self.hostname, launch_zebra(self.zebraconf,self.zebrapid,
                            self.zebraapi,self.node.addr.split('/')[0], port))
        runOS(cmd)

    def start_ospf6d(self, port=OSPF6dPORT) :
        """
            start the ospf6d daemon
        """
        cmd = IPNETNSEXEC % (self.hostname ,launch_ospf6d(self.ospf6dconf,self.ospf6dpid,
                            self.zebraapi,self.node.addr.split('/')[0], port))
        runOS(cmd)

    def kill_zebra(self) :
        """
            stop zebra
        """
        cmd = IPNETNSEXEC % (self.hostname, KILL % self.zebrapid)
        runOS(cmd)

    def kill_ospf6d(self) :
        """
            stop ospf6d
        """
        cmd = IPNETNSEXEC % (self.hostname, KILL % self.ospf6dpid)
        runOS(cmd)

    def start_snmp(self) :
        """
            start snmp agent on this node
        """
        cmd = IPNETNSEXEC % (self.hostname, STARTSNMP % (self.snmppid))
        runOS(cmd)

    def kill_snmp(self) :
        """
            kill snmp agent on this node
        """
        cmd = IPNETNSEXEC % (self.hostname, KILLSNMP % (self.snmppid))
        runOS(cmd)

    def start_sshd(self) :
        """
            start ssh daemon on this node
        """
        cmd = STARTSSHD % self.sshdpid
        self.cmd(cmd)

    def kill_sshd(self) :
        """
            kill sshd on this node
        """
        cmd = KILL %  self.sshdpid
        self.cmd(cmd)

    def build_confd_agent(self):
        """
            Build directory for confd agent +
            compile confd agent
        """
        # build directory
        cmd = MKDIR %  self.sragentdir
        self.cmd(cmd)
        # copy files to directory to sragentdir
        for f in SRagentFiles :
            self.cmd(CPFile % (SRconfdagentDir, f, self.sragentdir))
        # compile confd sragent
        self.cmd_process(COMPILECONFD % self.sragentdir)
        # start confD
        self.cmd_process(STARTCONFD % self.sragentdir)
        # start sragent
        self.cmd_process(DAEMONIZESRAGENT % (self.sragentdir,DAEMONNAME))

    def kill_confd_agent(self) :
        """
            kill the confd agent and ConfD on this host
        """
        # stoping confd and sragent
        self.cmd_process(KILLCONFD % self.sragentdir)
        # removing directory for this node
        self.cmd_process(RMDIR % self.sragentdir)
