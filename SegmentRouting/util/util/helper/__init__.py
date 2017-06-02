from util import SRDir,LOG
import os
import subprocess
from subprocess import Popen, PIPE

## DBG variable :
# * set DBG to True to locally test how the
#   controller operates without needing to
#   actual start a network, create name space etc.
#   This will actually prevent any terminal commands
#   to be run by the controller.
# NB: you could use this mode if you don't have the
#     proper Kernel with SR-IPv6 support but still want
#     to have an idea of how the controller works 
DBG=False
# ConfD out files
SR_OUT = '%s/daemon/out/sr.json' % SRDir
NET_OUT = '%s/daemon/out/network.json' %  SRDir

# Quagga related variables
QuaggaDIR = '/etc/quagga'
ZEBRABIN = '/usr/lib/quagga/zebra'
OSPF6DBIN = '/usr/lib/quagga/ospf6d'
# template file
ZebraTEMP = '%s/res/zebra.mako' % SRDir
ospf6dTEMP = '%s/res/ospf6d.mako' % SRDir
NetconfSRTEMP = '%s/res/sragent-template.mako' % SRDir
# default passwords
Password = 'zebra'

# config dir
ConfigDIR = '/tmp'
# change permission cmd
PermCMD = 'chown quagga.quaggavty %s/*.conf ; chmod 640 %s/*.conf' #
IPNETNSEXEC = 'ip netns exec %s bash -c \'%s\''

# start command
STARTZEBRA = '%s -d -f %s -A %s -P %d -i %s -z %s'
STARTOSPF6D = '%s -d -f %s -A %s -P %d -i %s -z %s'

# Kill cmd
KILL = 'kill -9 $(cat %s)'
RMNS = 'ip netns delete %s'

# default port
ZEBRAPORT = 2000
OSPF6dPORT = 2002

# sr6 add encap
ADDROUTE = 'ip -6 ro ad %s encap seg6 mode encap segs %s dev %s'
REMOVEROUTE = 'ip -6 ro del %s'


# setup  snmp cmd
STARTSNMP = '/usr/sbin/snmpd -Lsd -Lf /dev/null -p %s '
KILLSNMP = 'kill -TERM $(cat %s)'

# setup ssh
STARTSSHD = '/usr/sbin/sshd -o PidFile=%s'
SSH6CMD = 'ssh %s \"%s\"'
# confd sragent command
RMDIR = 'rm -R %s/'
MKDIR = 'mkdir %s'
SRagentDir = '%s/%s'
SRconfdagentDir = '%s/SRconfdagent' % SRDir
CPFile = 'cp %s/%s %s/'
SRagentFiles = ['commands-c.cli', 'commands-j.cli',
                'confd.conf', 'Makefile',
                'sragent.c', 'sragent.yang' ]
COMPILECONFD = 'make all -C %s'
STARTCONFD = 'make start_confd -C %s'
KILLCONFD = 'make stop -C %s'
DAEMONNAME = 'sragent_conf'
DAEMONIZESRAGENT = 'daemon -U %s/%s'

# netconf command
CONFDDIR = '%s/../confd' % SRDir
NETCONFSEND = '%s/bin/netconf-console --proto=ssh --port=2022 --host=%s %s'

# ip link
LINKDOWN = 'ip link set dev %s down'
LINKUP = 'ip link set dev %s up'

# Actions
ADD = 'add'
MODIFY = 'modify'
DELETE = 'delete'

# states
ADDED = 0
MODIFIED = 1
DELETED = 2
DELETING = 3
ADDING = 4

# transaction status
T_SUCCESS = True
T_ABORT   = False

def Flatten(L) :
    tmp = []
    for item in L:
        if type(item) == list :
            for subitem in item :
                if subitem not in tmp :
                    tmp.append(subitem)
        else:
            tmp.append(item)
    return tmp


def run_process(cmd, debug=DBG):
    """
        run the cmd
    """
    LOG.debug(cmd)
    if not debug :
        p = Popen(cmd, shell=True, stdout=PIPE)
        p.wait()
        return p.stdout.read()

def runOS(cmd, debug=DBG) :
    """
        run a os.system(cmd)
    """
    LOG.debug(cmd)
    if not debug :
        os.system(cmd)


def launch_zebra(zebraconf,zebrapid, zebraapi,loaddr, port,
                zebraBin=ZEBRABIN) :
    """
        return full cmd to start zebra
    """

    return STARTZEBRA % (zebraBin, zebraconf,loaddr, port, zebrapid, zebraapi)

def launch_ospf6d(ospf6dconf, ospf6dpid,zebraapi,loaddr, port,
                  ospf6dBin=OSPF6DBIN):
    """
        return the full cmd to start ospf6d
    """

    return STARTOSPF6D % (ospf6dBin, ospf6dconf,loaddr, port, ospf6dpid, zebraapi)

# helper function
def file_path(Dir, filename,name,ext ) :
    """
        return the path for the file
    """
    return '%s/%s_%s.%s' % (Dir,filename, name, ext)

def remove_from_list(List, item) :
    del List[List.index(item)]
