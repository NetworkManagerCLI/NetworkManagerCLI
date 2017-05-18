# Network Manager
import socket
import sys
import json

import argparse
import os

import fibbingnode.misc.mininetlib as _lib
from fibbingnode.misc.mininetlib.cli import FibbingCLI
from fibbingnode.misc.mininetlib.ipnet import IPNet
from fibbingnode.misc.mininetlib.iptopo import IPTopo
from fibbingnode.algorithms.southbound_interface import SouthboundManager
from fibbingnode.algorithms.ospf_simple import OSPFSimple
from fibbingnode import CFG
from fibbingnode.misc.mininetlib import  PRIVATE_IP_KEY, CFG_KEY
from fibbingnode.misc.mininetlib import  otherIntf, L3Router

from mininet.util import custom
from mininet.link import TCIntf

from util.network.customipnet import CustomIPNet, TopologyDB
from util.network.topo import CustomTopo

# package un util/util
from util import *


from util.lib import *
from util import LOG
from util import pathtoREScfg
from util.network.southboundextended import SouthBoundExtended, MultipleSouthboundManager

import time
import threading
import SocketServer
import datetime
from cmd import Cmd
import sys
import time
import subprocess
from ipaddress import ip_interface
import re
import random
import matplotlib.pyplot as Dplt
import networkx as Gnx

from termcolor import colored

# Global variables
d_req = None
d = None
newconfig = False
firstconfig = False
has_req = False
new_req = False

E = threading.Event()
# -----------------------------------------------------
#           Handlers for ConfD Agent
# ------------------------------------------------------
class MyTCPHandler_controller(SocketServer.BaseRequestHandler):
    """
    Server that will handle the new requirements sent by the
    ConfDAgent daemon, when it detects a requirement change
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        self.data = self.request.recv(PACKETSIZE).strip()
        LOG.info("{} connected".format(self.client_address[0]))
        tmp = False
        OK = True

        try :
            tmp = json.loads(self.data)
        except ValueError:
            try :
                with open(Fib_OUT, 'r') as sr_out :
                    tmp = json.load(sr_out)
            except Exception :
                OK = False
                LOG.error('JSON failed to parse the configurations')

        if OK :
            # just send back an ACK
            self.request.sendall(ACK)
        else :
            # just send back an ACK
            self.request.sendall('ERROR')

        if d:
            if not checkRequirementConfig(d, tmp) :
                LOG.info('SUCCESS : configurations pass check')
                global d_req
                d_req = tmp
                global has_req
                if not has_req :
                    has_req = True

                global new_req
                new_req = True

                global E
                E.set()
            else :
                LOG.error('Config error')
        else:
            LOG.error('No network config received')
            LOG.info('First commit network configuration, and then commit the requiment configuration')


class MyTCPHandler_network(SocketServer.BaseRequestHandler):
    """
    Server that will handle the new configurations sent by the
    ConfDAgent daemon, when it detects a configuration change
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        self.data = self.request.recv(PACKETSIZE).strip()
        connected="{} connected".format(self.client_address[0])
        received= "{} received :".format(self.data)
        LOG.info(connected)
        # LOG.info(received)
        LOG.info('received new configurations')
        # parse the config
        tmp = False
        OK = True
        try :
            tmp = json.loads(self.data)
        except ValueError:
            try :
                with open(NET_OUT, 'r') as net_out :
                    tmp = json.load(net_out)
            except Exception :
                OK = False
                LOG.error('JSON failed to parse the configurations')


        if OK :
            # just send back an ACK
            self.request.sendall(ACK)
        else :
            # just send back an ACK
            self.request.sendall('ERROR')

        if OK :
            if not checkNetworkConfig(tmp) :
                LOG.info('SUCCESS : configurations pass check')
                global d
                d=tmp
                global newconfig
                newconfig = True
                global firstconfig
                if not firstconfig :
                    firstconfig = True
                global E
                E.set()
            else :
                LOG.error('Config error')

# -----------------------------------------------------
#           Network Manager Core
# structure:
#    * API functions: functions that can be modified
#                     to support others kind of protocol
#    * CLI callback functions: functions called by the
#                             NetworkManagerCLI
#    * lib functions: others functions
# ------------------------------------------------------
class NetworkManagerCore(object):
    def __init__(self,checker=False) :
        self.checker = checker
        self.network = False
        self.running = False
        self.firstconfig = False
        self.waitingTime = 20
        self.isdata = False
        self.manager = False
        self.controllerrunning = False
        self.isrequirement = False
        self.requirements = False
        self.db = False
        self.cache = {}
        self.timerEvent = threading.Event()
        self.lock = threading.Lock()
        self.SchedulePeriod = 60 # sec
        self.scheduled_req = []
        self.auto_schedule = False
        self.snmpCtrl = False
        self.ip_name_mapping = False
        self.router_dest_mapping = False
        self.intf_index = {}

        self.network_server = SocketServer.TCPServer((LOCALHOST, NETWORK_port), MyTCPHandler_network)
        self.trigger_thread = threading.Thread(target=self.network_server.serve_forever)
        self.trigger_thread.daemon = True
        LOG.info('Starting the confd network listener daemon  thread ...')
        self.trigger_thread.start()

        self.controller_server = SocketServer.TCPServer((LOCALHOST, CONTROLLER_port), MyTCPHandler_controller)
        self.controller_thread = threading.Thread(target=self.controller_server.serve_forever)
        self.controller_thread.daemon = True
        LOG.info('Starting the confd controller daemon  thread ...')
        self.controller_thread.start()

    # ---------------------------------------------------
    #               API functions
    # ---------------------------------------------------

    def check_single_requirement(self, key) :
        """
            @API
            check that the requirement is correctly
            applied to the network
        """
        try:
            Req = self.cache[key].req
            LOG.debug(str(Req))
            src_traceroute = Req[0]
            # if first router is connected to destination
            if self.router_dest_mapping.get(Req[0]) :
                src_traceroute = self.router_dest_mapping[Req[0]]
            dest_traceroute = self.cache[key].dest
            tr_out  = self.check_traceroute(src_traceroute, dest_traceroute)
            LOG.debug(str(tr_out))
            tr_ip = self.parse_traceroute(tr_out)

            LOG.debug(str(tr_ip))
            if len(tr_ip) == len(Req) +1 :
                if str(self.ip_name_mapping[tr_ip[-1]]) == str(dest_traceroute):
                    index = 0
                    for ip in tr_ip[:-1] :
                        if str(self.ip_name_mapping[ip]) == str(Req[index]) :
                            index += 1
                        else :
                            LOG.debug('IP not matching any router in the path')
                            return False
                else :
                    LOG.debug('not correct destination')
                    return False
            if self.router_dest_mapping.get(Req[0]) :
                if len(tr_ip) == len(Req) +2 :
                    if str(self.ip_name_mapping[tr_ip[-1]]) == str(dest_traceroute):
                        index = 0
                        if str(self.ip_name_mapping[tr_ip[0]]) == str(src_traceroute):
                            for ip in tr_ip[1:-1] :
                                if str(self.ip_name_mapping[ip]) == str(Req[index]) :
                                    index += 1
                                else :
                                    LOG.debug('IP not matching any router in the path')
                                    return False
                    else :
                        LOG.debug('not correct destination')
                        return False

                else :
                    LOG.debug('Not enough ips in traceroute')
                    return False


            return True
        except Exception as e:
            LOG.critical('Error '+str(e))
            return False

    def check_link_status(self,from_R,to_R) :
        """
            @API
            check that the link
            from_R -> to_R is still up
            return False if it is up
            return True if it is down
        """
        try :
            if from_R in self.network and to_R in self.network :

                node1 =  self.network[from_R]
                node2 = self.network[to_R]

                intfName = self.get_intf_by_router(from_R,to_R)

                if intfName :
                    self.setup_snmp_manager()
                    node2 = self.network[self.snmpCtrl]
                    walkcmd = SNMPWALK+str(node1.IP())
                    descr = node2.cmd(walkcmd+" ifDescr")
                    LOG.debug('\n'+descr+'\n')

                    lines = descr.split('\n')
                    index = self.intf_index.get(intfName)
                    if not index :
                        index = -1
                        for line in lines :
                            sp_line = line.split()
                            if sp_line and str(sp_line[-1]) == str(intfName) :
                                index = int(sp_line[0].split('.')[-1])
                        LOG.debug('index for '+str(intfName)+' is '+str(index))
                        if index != -1:
                            self.intf_index[intfName] = index

                    if index != -1 :
                        ifOperStatus = self.get_link_status(index, node2,node1.IP())
                        if not ifOperStatus :
                            LOG.debug('SNMP request failed to get an answer')
                            return False
                        else :
                            if ifOperStatus == 'down(2)' :
                                return True
                            elif ifOperStatus == 'up(1)' :
                                return False

            return False
        except Exception as e :
            LOG.critical('Error : '+ str(e))
            return False

    def check_bw_status(self,from_R,to_R,bw_perc) :
        """
            check that the bandwidth for the link
            from_R -> to_R does not exceed bw_perc
            return False if bw does not exceed bw_perc
            return True if bw exceeds bw_perc
        """
        try :
            if from_R in self.network and to_R in self.network :
                node1 =  self.network[from_R]
                node2 = self.network[to_R]

                intfName = self.get_intf_by_router(from_R,to_R)

                if intfName :
                    self.setup_snmp_manager()
                    node2 = self.network[self.snmpCtrl]
                    walkcmd = SNMPWALK+str(node1.IP())
                    descr = node2.cmd(walkcmd+" ifDescr")
                    LOG.debug('\n'+descr+'\n')

                    lines = descr.split('\n')
                    index = self.intf_index.get(intfName)
                    if not index :
                        index = -1
                        for line in lines :
                            sp_line = line.split()
                            if sp_line and str(sp_line[-1]) == str(intfName) :
                                index = int(sp_line[0].split('.')[-1])
                        LOG.debug('index for '+str(intfName)+' is '+str(index))

                        if index != -1:
                            self.intf_index[intfName] = index

                    if index != -1 :
                        upTime1, ifOutOctets1 =  self.get_intf_stats(index, node2,node1.IP())
                        time1 = time.time()
                        if upTime1 and ifOutOctets1 :
                            time.sleep(20)
                            upTime2, ifOutOctets2 =  self.get_intf_stats(index, node2,node1.IP())
                            if upTime2 and ifOutOctets2 :
                                bw = self.get_bw(from_R,to_R)
                                delta_t = time.time() - time1
                                LOG.debug('delta_t : '+ str(delta_t))
                                Dtime = self.diff_time(upTime1,upTime2)
                                LOG.debug('sys time diff :'+str(Dtime) )
                                if Dtime :
                                    band = self.bandwidth(ifOutOctets1,ifOutOctets2,bw*1000.0, Dtime)
                                    if band :
                                        LOG.info('bandwidth : '+ str(band))

                                        if band > bw_perc :
                                            return True
            return False
        except Exception as e :
            LOG.critical('Error : '+ str(e))
            return False


    def process_flags(self, key) :
        """
            @API
            process the requirement with name=key,
            according to its flags
            return True if the fibbing controller needs
            to refresh the topology
        """
        REFRESH = False
        if self.cache[key].flags[F_OK] :
            return False
        if not self.cache[key].flags[F_present] :
            if self.cache[key].status == UP :
                self.cache[key].set_flag(F_stop)
            elif self.cache[key].status == DOWN :
                self.cache[key].set_flag(F_delete)
            elif self.cache[key].status == SCHED :
                if self.cache[key].runningstatus == UP :
                    self.cache[key].set_flag(F_stop)
                elif self.cache[key].runningstatus == DOWN :
                    self.cache[key].set_flag(F_delete)

        if self.cache[key].flags[F_stop] :
            REQ = self.cache[key]
            prefix = self.db.subnet(REQ.router, REQ.dest)
            self.manager.remove_requirement(key,prefix)
            if self.cache[key].status == SCHED :
                remove_from_list(self.scheduled_req,key)
            LOG.debug('Stoping requirement ' + str(self.cache[key].name) + ' '+ str(key))
            REFRESH = True
            del self.cache[key]
            return REFRESH

        if self.cache[key].flags[F_halt] :
            REQ = self.cache[key]
            prefix = self.db.subnet(REQ.router, REQ.dest)
            self.manager.remove_requirement(key,prefix)
            REFRESH = True
            if self.cache[key].status == SCHED :
                if self.cache[key].runningstatus ==UP :
                    self.cache[key].set_runningstatus(DOWN)
            LOG.debug('halt :'+str(self.cache[key].req)+ ' ==> '+ str(key))

        if self.cache[key].flags[F_delete] :
            value =self.cache[key]
            LOG.debug('delete :'+ str(self.cache[key].req)+ ' ==> '+ str(key))
            if self.cache[key].status == SCHED :
                remove_from_list(self.scheduled_req,key)
            del self.cache[key]
            return REFRESH

        if self.cache[key].flags[F_replace] :
            newREQ = self.cache[key].newRequirement
            if self.cache[key].status == SCHED and newREQ.status != SCHED:
                remove_from_list(self.scheduled_req,key)
            self.cache[key] = newREQ
            if self.cache[key].status == SCHED :
                self.scheduled_req.append(key)
            LOG.debug('replace :'+ str(self.cache[key].req)+ ' '+ str(key))

        if self.cache[key].flags[F_Add] :
            REQ = self.cache[key]
            rs = REQ.router
            ds = REQ.dest
            R = REQ.req
            prefix=self.db.subnet(rs, ds)
            path=[self.db.routerid(r) for r in R]
            self.manager.add_requirement(key,prefix,path )
            REFRESH = True
            if self.cache[key].status == SCHED :
                if self.cache[key].runningstatus == DOWN :
                    self.cache[key].set_runningstatus(UP)
            LOG.debug('Adding :' +str(self.cache[key].req)+ ' ==> '+ str(key))

        # if key still in cache
        if self.cache.get(key) :
            self.cache.get(key).reset_all_flags()

        return REFRESH

    def process_requirement(self) :
        """
            @API
            go through the stored requirements,
            * check the requirement configuration
            * does path expantion if * in path
            * compare new requirements with stored ones
              and set the corresponding Flags
              (F_stop, F_delete,F_halt,F_replace,F_present)
              if changes are detected
        """
        self.lock.acquire()
        conf = self.requirements['config']
        link =  conf["link"]


        tmp_keys = self.cache.keys()
        REFRESH = False

        for x in link :
            if x.get('name') not in self.cache or\
            x.get('change'):
                rs = x.get('requirement')[-1]
                ds = str(x.get('dest'))
                R = []
                for r in x.get('requirement') :
                    R.append(str(r))

                Req = []
                if '*' not in R :
                    Req =  R
                elif is_ok_path_req(R) :
                    try :
                        simple_R = complete_path(self.data, R, str(rs))
                    except Exception as e :
                        LOG.critical('Error occured during path expantion :'+str(e))
                        continue
                    if simple_R :
                        Req = simple_R


                # new requirements
                if not self.cache.get(str(x.get('name'))) :
                    if str(x.get('status')) == str(UP) :
                        newRequirement = Requirement(str(x.get('name')), ds, rs, Req, str(x.get('status')))
                        newRequirement.set_flag(F_Add)
                        newRequirement.set_flag(F_present)
                        self.cache[ str(x.get('name'))] = newRequirement
                        LOG.debug('Storing new requirements '+  str(x.get('name')))

                    elif str(x.get('status')) == str(SCHED) :
                        LOG.debug('Schedule requirement : '+ str(x.get('status')))
                        newRequirement = Requirement(str(x.get('name')), ds, rs, Req, str(x.get('status')))
                        schedinfo = x.get('scheduled')
                        if schedinfo.get('type') == TIME :
                            start_h_str = str(schedinfo.get('start-hour'))
                            end_h_str = str(schedinfo.get('end-hour'))
                            startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                            endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                            newRequirement.set_start_hour(startTuple, start_h_str)
                            newRequirement.set_end_hour(endTuple, end_h_str)
                            days = schedinfo.get('days')
                            newRequirement.set_weekday(days)
                            newRequirement.set_type(TIME)

                        if schedinfo.get('type') == BAND or schedinfo.get('type') == BACK:
                            link_bw  = schedinfo.get('link')
                            newRequirement.set_bw_perc(int(link_bw.get('bw-perc')))
                            newRequirement.set_link(link_bw.get('from'), link_bw.get('to'))
                            start_h_str = str(schedinfo.get('start-hour'))
                            end_h_str = str(schedinfo.get('end-hour'))
                            startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                            endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                            newRequirement.set_start_hour(startTuple, start_h_str)
                            newRequirement.set_end_hour(endTuple, end_h_str)
                            days = schedinfo.get('days')
                            newRequirement.set_weekday(days)
                            newRequirement.set_type(schedinfo.get('type'))

                        newRequirement.set_flag(F_OK)
                        newRequirement.set_flag(F_present)
                        self.cache[ str(x.get('name'))] = newRequirement
                        LOG.debug('Storing new requirements '+  str(x.get('name')))
                        self.scheduled_req.append(str(x.get('name')))

                else :
                    self.cache.get(str(x.get('name'))).reset_all_flags()
                    # the requirement is already stored
                    if str(x.get('status')) == str(DOWN) :
                        if self.cache.get(str(x.get('name'))).status == SCHED :
                            if self.cache.get(str(x.get('name'))).runningstatus == UP :
                                self.cache.get(str(x.get('name'))).set_flag(F_stop)
                                self.cache.get(str(x.get('name'))).set_flag(F_present)
                                LOG.debug('Seting Flag stop ')
                            elif self.cache.get(str(x.get('name'))).runningstatus == DOWN :
                                self.cache.get(str(x.get('name'))).set_flag(F_delete)
                                self.cache.get(str(x.get('name'))).set_flag(F_present)
                                LOG.debug('Seting Flag Delete ')
                        else :
                            self.cache.get(str(x.get('name'))).set_flag(F_stop)
                            self.cache.get(str(x.get('name'))).set_flag(F_present)
                            LOG.debug('Seting Flag stop ')
                    else :
                        newRequirement =  Requirement(str(x.get('name')), ds, rs, Req,str(x.get('status')))
                        if self.cache.get(str(x.get('name'))).to_string() !=  newRequirement.to_string() :
                            if self.cache.get(str(x.get('name'))).status == UP and newRequirement.status== UP :
                                self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                self.cache.get(str(x.get('name'))).set_flag(F_replace)

                                newRequirement.set_flag(F_present)
                                newRequirement.set_flag(F_Add)
                                self.cache.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                self.cache.get(str(x.get('name'))).set_flag(F_present)
                                LOG.debug(' Diff req UP UP ')

                            elif self.cache.get(str(x.get('name'))).status == UP and newRequirement.status== SCHED :
                                self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                self.cache.get(str(x.get('name'))).set_flag(F_replace)

                                schedinfo = x.get('scheduled')
                                if schedinfo.get('type') == TIME :
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    newRequirement.set_start_hour(startTuple, start_h_str)
                                    newRequirement.set_end_hour(endTuple, end_h_str)
                                    days = schedinfo.get('days')
                                    newRequirement.set_weekday(days)
                                    newRequirement.set_type(TIME)

                                if schedinfo.get('type') == BAND or schedinfo.get('type') == BACK:
                                    link_bw  = schedinfo.get('link')
                                    newRequirement.set_bw_perc(int(link_bw.get('bw-perc')))
                                    newRequirement.set_link(link_bw.get('from'), link_bw.get('to'))
                                    days = schedinfo.get('days')
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    newRequirement.set_start_hour(startTuple, start_h_str)
                                    newRequirement.set_end_hour(endTuple, end_h_str)
                                    newRequirement.set_weekday(days)
                                    newRequirement.set_type(schedinfo.get('type'))


                                newRequirement.set_flag(F_OK)
                                newRequirement.set_flag(F_present)
                                self.cache.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                self.cache.get(str(x.get('name'))).set_flag(F_present)
                                LOG.debug(' Diff req UP SCHED ')

                            elif self.cache.get(str(x.get('name'))).status == SCHED and newRequirement.status== UP :
                                LOG.debug(' Diff req SCHED UP ')
                                if self.cache.get(str(x.get('name'))).runningstatus == UP :
                                    self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                    self.cache.get(str(x.get('name'))).set_flag(F_replace)
                                    newRequirement.set_flag(F_present)
                                    newRequirement.set_flag(F_Add)
                                    self.cache.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                    self.cache.get(str(x.get('name'))).set_flag(F_present)

                                elif self.cache.get(str(x.get('name'))).runningstatus == DOWN :
                                    self.cache.get(str(x.get('name'))).set_flag(F_replace)
                                    newRequirement.set_flag(F_present)
                                    newRequirement.set_flag(F_Add)
                                    self.cache.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                    self.cache.get(str(x.get('name'))).set_flag(F_present)

                            elif self.cache.get(str(x.get('name'))).status == SCHED and newRequirement.status== SCHED :
                                LOG.debug(' Diff req SCHED SHED ')
                                if self.cache.get(str(x.get('name'))).runningstatus == UP :
                                    self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                    self.cache.get(str(x.get('name'))).set_flag(F_replace)
                                    schedinfo = x.get('scheduled')
                                    if schedinfo.get('type') == TIME :
                                        start_h_str = str(schedinfo.get('start-hour'))
                                        end_h_str = str(schedinfo.get('end-hour'))
                                        startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                        endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                        newRequirement.set_start_hour(startTuple, start_h_str)
                                        newRequirement.set_end_hour(endTuple, end_h_str)
                                        days = schedinfo.get('days')
                                        newRequirement.set_weekday(days)
                                        newRequirement.set_type(TIME)

                                    if schedinfo.get('type') == BAND or schedinfo.get('type') == BACK:
                                        link_bw  = schedinfo.get('link')
                                        newRequirement.set_bw_perc(int(link_bw.get('bw-perc')))
                                        newRequirement.set_link(link_bw.get('from'), link_bw.get('to'))
                                        days = schedinfo.get('days')
                                        start_h_str = str(schedinfo.get('start-hour'))
                                        end_h_str = str(schedinfo.get('end-hour'))
                                        startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                        endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                        newRequirement.set_start_hour(startTuple, start_h_str)
                                        newRequirement.set_end_hour(endTuple, end_h_str)
                                        newRequirement.set_weekday(days)
                                        newRequirement.set_type(schedinfo.get('type'))

                                    newRequirement.set_flag(F_present)
                                    self.cache.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                    self.cache.get(str(x.get('name'))).set_flag(F_present)

                                elif self.cache.get(str(x.get('name'))).runningstatus == DOWN :
                                    self.cache.get(str(x.get('name'))).set_flag(F_replace)

                                    schedinfo = x.get('scheduled')
                                    if schedinfo.get('type') == TIME :
                                        start_h_str = str(schedinfo.get('start-hour'))
                                        end_h_str = str(schedinfo.get('end-hour'))
                                        startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                        endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                        newRequirement.set_start_hour(startTuple, start_h_str)
                                        newRequirement.set_end_hour(endTuple, end_h_str)
                                        days = schedinfo.get('days')
                                        newRequirement.set_weekday(days)
                                        newRequirement.set_type(TIME)

                                    if schedinfo.get('type') == BAND or schedinfo.get('type') == BACK :
                                        link_bw  = schedinfo.get('link')
                                        newRequirement.set_bw_perc(int(link_bw.get('bw-perc')))
                                        newRequirement.set_link(link_bw.get('from'), link_bw.get('to'))
                                        days = schedinfo.get('days')
                                        start_h_str = str(schedinfo.get('start-hour'))
                                        end_h_str = str(schedinfo.get('end-hour'))
                                        startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                        endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                        newRequirement.set_start_hour(startTuple, start_h_str)
                                        newRequirement.set_end_hour(endTuple, end_h_str)
                                        newRequirement.set_weekday(days)
                                        newRequirement.set_type(schedinfo.get('type'))

                                    newRequirement.reset_all_flags()
                                    newRequirement.set_flag(F_present)
                                    newRequirement.set_flag(F_OK)
                                    self.cache.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                    self.cache.get(str(x.get('name'))).set_flag(F_present)
                                    LOG.debug(' Diff req SCHED SHED ')


                        else :
                            # no modifications within the requirement
                            if self.cache.get(str(x.get('name'))).status == UP and newRequirement.status== UP :
                                self.cache.get(str(x.get('name'))).set_flag(F_OK)
                                self.cache.get(str(x.get('name'))).set_flag(F_present)

                            elif self.cache.get(str(x.get('name'))).status == SCHED and newRequirement.status== SCHED :
                                schedinfo = x.get('scheduled')
                                if schedinfo.get('type') == TIME and \
                                self.cache.get(str(x.get('name'))).scheduleType == TIME:
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    newRequirement.set_start_hour(startTuple, start_h_str)
                                    newRequirement.set_end_hour(endTuple, end_h_str)
                                    days = schedinfo.get('days')
                                    newRequirement.set_weekday(days)
                                    newRequirement.set_type(TIME)

                                    if self.cache.get(str(x.get('name'))).sched_to_string() != newRequirement.sched_to_string() :
                                        self.cache.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                        self.cache.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                        self.cache.get(str(x.get('name'))).set_weekday(days)
                                        if self.cache.get(str(x.get('name'))).runningstatus == UP :
                                            self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                        self.cache.get(str(x.get('name'))).set_flag(F_present)

                                    else :
                                        self.cache.get(str(x.get('name'))).set_flag(F_OK)
                                        self.cache.get(str(x.get('name'))).set_flag(F_present)

                                elif (schedinfo.get('type') == BAND or schedinfo.get('type') == BACK) and \
                                (self.cache.get(str(x.get('name'))).scheduleType == BAND or \
                                 self.cache.get(str(x.get('name'))).scheduleType == BACK):
                                    link_bw  = schedinfo.get('link')
                                    newRequirement.set_bw_perc(int(link_bw.get('bw-perc')))
                                    newRequirement.set_link(link_bw.get('from'), link_bw.get('to'))
                                    days = schedinfo.get('days')
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    newRequirement.set_start_hour(startTuple, start_h_str)
                                    newRequirement.set_end_hour(endTuple, end_h_str)
                                    newRequirement.set_weekday(days)
                                    newRequirement.set_type(schedinfo.get('type'))

                                    if self.cache.get(str(x.get('name'))).bw_to_string() != newRequirement.bw_to_string() :
                                        self.cache.get(str(x.get('name'))).set_bw_perc(int(link_bw.get('bw-perc')))
                                        self.cache.get(str(x.get('name'))).set_link(link_bw.get('from'), link_bw.get('to'))
                                        self.cache.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                        self.cache.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                        self.cache.get(str(x.get('name'))).set_weekday(days)
                                        self.cache.get(str(x.get('name'))).set_type(schedinfo.get('type'))
                                        if self.cache.get(str(x.get('name'))).runningstatus == UP :
                                            self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                        self.cache.get(str(x.get('name'))).set_flag(F_present)

                                    else :
                                        self.cache.get(str(x.get('name'))).set_flag(F_OK)
                                        self.cache.get(str(x.get('name'))).set_flag(F_present)

                                elif (schedinfo.get('type') == BAND  or schedinfo.get('type') == BACK) and \
                                     self.cache.get(str(x.get('name'))).scheduleType == TIME:
                                    link_bw  = schedinfo.get('link')
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    days = schedinfo.get('days')
                                    self.cache.get(str(x.get('name'))).set_bw_perc(int(link_bw.get('bw-perc')))
                                    self.cache.get(str(x.get('name'))).set_link(link_bw.get('from'), link_bw.get('to'))
                                    self.cache.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                    self.cache.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                    self.cache.get(str(x.get('name'))).set_weekday(days)
                                    self.cache.get(str(x.get('name'))).set_type(schedinfo.get('type'))
                                    if self.cache.get(str(x.get('name'))).runningstatus == UP :
                                        self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                    self.cache.get(str(x.get('name'))).set_flag(F_present)

                                elif schedinfo.get('type') == TIME and \
                                (self.cache.get(str(x.get('name'))).scheduleType == BAND or\
                                 self.cache.get(str(x.get('name'))).scheduleType == BACK):
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    days = schedinfo.get('days')
                                    self.cache.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                    self.cache.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                    self.cache.get(str(x.get('name'))).set_weekday(days)
                                    self.cache.get(str(x.get('name'))).set_type(TIME)
                                    if self.cache.get(str(x.get('name'))).runningstatus == UP :
                                        self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                    self.cache.get(str(x.get('name'))).set_flag(F_present)

                            elif self.cache.get(str(x.get('name'))).status == UP and newRequirement.status== SCHED :

                                schedinfo = x.get('scheduled')
                                if schedinfo.get('type') == TIME :
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    days = schedinfo.get('days')
                                    self.cache.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                    self.cache.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                    self.cache.get(str(x.get('name'))).set_weekday(days)
                                    self.cache.get(str(x.get('name'))).set_type(TIME)
                                    self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                    self.cache.get(str(x.get('name'))).set_flag(F_present)
                                    self.cache.get(str(x.get('name'))).set_status(SCHED)

                                if schedinfo.get('type') == BAND or schedinfo.get('type') == BACK:
                                    link_bw  = schedinfo.get('link')
                                    days = schedinfo.get('days')
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    self.cache.get(str(x.get('name'))).set_bw_perc(int(link_bw.get('bw-perc')))
                                    self.cache.get(str(x.get('name'))).set_link(link_bw.get('from'), link_bw.get('to'))
                                    self.cache.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                    self.cache.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                    self.cache.get(str(x.get('name'))).set_weekday(days)
                                    self.cache.get(str(x.get('name'))).set_type(schedinfo.get('type'))
                                    self.cache.get(str(x.get('name'))).set_flag(F_halt)
                                    self.cache.get(str(x.get('name'))).set_flag(F_present)
                                    self.cache.get(str(x.get('name'))).set_status(SCHED)

                                self.scheduled_req.append(str(x.get('name')))

                            elif self.cache.get(str(x.get('name'))).status == SCHED and newRequirement.status== UP :
                                if self.cache.get(str(x.get('name'))).runningstatus == UP :
                                    self.cache.get(str(x.get('name'))).set_flag(F_OK)
                                elif self.cache.get(str(x.get('name'))).runningstatus == DOWN :
                                    self.cache.get(str(x.get('name'))).set_flag(F_Add)

                                self.cache.get(str(x.get('name'))).set_status(UP)
                                self.cache.get(str(x.get('name'))).set_flag(F_present)
                                remove_from_list(self.scheduled_req, str(x.get('name')))


                # Processing the requirement after having seting the flags
                if self.process_flags(x.get('name')) :
                    REFRESH = True

                if str(x.get('name'))in tmp_keys :
                    LOG.debug('Del %s, processed' % x.get('name'))
                    del tmp_keys[tmp_keys.index(str(x.get('name')))]
            else :
                # if not new requirement or
                # has not changed
                self.cache.get(x.get('name')).reset_all_flags()
                LOG.debug('No change for %s' % x.get('name'))
                self.cache.get(x.get('name')).set_flag(F_present)
                if str(x.get('name')) in tmp_keys :
                    LOG.debug('Del %s, processed' % x.get('name'))
                    del tmp_keys[tmp_keys.index(str(x.get('name')))]

        # All remaining keys are obsolete requirements
        # thus needing to be removed
        LOG.debug('%s keys left unprocessed' % str(tmp_keys))
        for key in tmp_keys :
            self.cache[key].reset_all_flags()
            if self.process_flags(key) :
                REFRESH = True

        self.lock.release()
        return REFRESH

    # ----------------------------------------------------
    #      CLI callback functions
    # ----------------------------------------------------
    def _print_dag_for(self, line) :
        """
            Print the DAG of all path requirement
            for the given destination
            usage: print_dag_for <destination hosts>
        """
        try :
            if line in self.network :
                self.plot_dag(line)
            else:
                LOG.error('%s is not known' % line)

        except Exception as e :
            LOG.critical("Error : "+str(e))

    def _ip(self, line):
        """
            usage:
               ip <ipadress>
            return name of the node corresponding to
            the ipaddress
        """
        try :
            LOG.info('ip %s' % line)
            if self.running :
                if line not in self.ip_name_mapping :
                    LOG.error('IP not knonw')
                else:
                    LOG.info('Router associated with %s is %s' % (line, self.ip_name_mapping[line]))
            else:
                LOG.error("network must be running")
        except Exception as e :
            LOG.critical("Error : "+str(e))

    def _set_time_granularity(self, line) :
        """
            * INPUT :  a integer value of time in sec for
              the period at which the application will check
              the scheduled requirements
        """
        try :
            if line :
                time = int(line)
                if time :
                    # TODO check if time value makes sense
                    self.SchedulePeriod = time
            else :
                LOG.error('Need a time value as input')
        except Exception as e :
            LOG.critical('Error :' + str(e))

    def _show_time_granularity(self, line) :
        """
            * display the current time granularity
        """
        LOG.info('Time granularity : '+ str(self.SchedulePeriod))

    def _halt_requirement(self, line) :
        """
            * INPUT :  key of the requirement
            * if the requirement is running, it will be stopped
        """
        if line :
            try :
                LOG.info('halt requirement %s' % line)
                if line in self.cache :
                    self.lock.acquire()
                    self.cache[line].reset_all_flags()
                    if self.cache[line].status == UP :
                        self.cache[line].set_flag(F_halt)
                        self.cache[line].set_flag(F_delete)
                        self.cache[line].set_flag(F_present)
                        REFRESH = self.process_flags(str(line))
                        if REFRESH :
                            LOG.debug('Trying to refresh topo')
                            #self.manager.refresh_augmented_topo()
                            self.manager.commit_change()
                        else :
                            LOG.debug('Not refreshing')

                    elif self.cache[line].status == SCHED and\
                        self.cache[line].runningstatus == UP :
                        self.cache[line].set_flag(F_halt)
                        self.cache[line].set_flag(F_present)
                        REFRESH = self.process_flags(str(line))
                        if REFRESH :
                            LOG.debug('Trying to refresh topo')
                            #self.manager.refresh_augmented_topo()
                            self.manager.commit_change()
                    self.lock.release()
                else :
                    LOG.error('no requirements stored for key '+ str(line))
            except Exception as e :
                LOG.critical("Error : " + str(e))
                self.lock.release()
        else :
            LOG.error('Need the key of a requirement as input')
            LOG.info('Do <show_requirements> to have info about the requirments')

    def _show_requirements(self,line) :
        """
            * display the stored requirements
        """
        if self.isrequirement :
            self.dump_requirement_log()

        else :
            LOG.error('There is no requirements ')

    def dump_requirement_log(self) :
        """
            show requirement in a LOG.info()
        """
        colors = {UP : 'green', DOWN : 'red', SCHED : 'magenta',
                  TIME : 'yellow', BAND : 'blue', BACK : 'cyan'}
        Str = '\n----------------------------------\n'
        Str +=  '   Stored requirements :\n'
        for key, value in self.cache.iteritems() :
            Str += '----------------------------------\n'
            Str += '!  key : %s\n' % str(key)
            Str += '!  dest : %s\n' %  str(value.dest)
            Str += '!  requirement : %s\n' %  str(value.req)
            Str += '!  status : %s \n' % colored(str(value.status), colors[str(value.status)], attrs=['bold'])
            if value.status == SCHED :
                Str += '!  ! running status : %s\n' % colored(str(value.runningstatus), colors[str(value.runningstatus)], attrs=['bold'])
                Str += '!  ! Type : %s\n' %  colored(str(value.scheduleType), colors[str(value.scheduleType)], attrs=['bold'])
                Str += '!  ! start hour : %s\n' % str(value.start_hour_str)
                Str += '!  ! end hour : %s\n' % str(value.end_hour_str)

                if value.scheduleType == BAND or value.scheduleType == BACK :
                    Str += '!  ! from : %s\n' % str(value.from_R)
                    Str += '!  ! to : %s\n' % str(value.to_R)
                    if value.scheduleType == BAND :
                        Str += '!  ! bw (%) : %s\n ' % str(value.bw_perc)

                WD = []
                for x in value.weekdays :
                    WD.append(WEEKDAYS[x])
                Str += '!  ! weekdays : %s\n' % str(WD)
            Str += '----------------------------------\n'
        Str +=  '  Time : %s\n' % str(self.get_time().ctime())
        Str += '----------------------------------\n'
        LOG.info(Str)

    def _xterm_config(self, line) :
        """
            * Launch an xterm terminal with the confD CLI
        """
        CLI_th = threading.Thread(target=self.confd_cli_th)
        CLI_th.start()
        LOG.info('confD CLI started...')

    def _config(self, line ) :
        """
            * Launch the confD CLI
        """
        comdline =[ 'make', 'cli']
        subprocess.call(comdline)
        LOG.info('confD CLI started...')

    def _mininet_cli(self,line) :
        """
            * it will start the Mininet CLI on the network
            * Require to have the network already running
        """
        if self.running :
            LOG.info('starting CLI...')
            FibbingCLI(self.network)
            LOG.info('exiting CLI...')
        else :
            LOG.error('The network is not running...')


    def _start_network(self, line) :
        """
            * it will start the network and set the state on running.
            * Require to have some available configuration
        """
        if self.process_network_config() :
            LOG.info('Start network')
            self.start_network()

    def _stop_network(self,line) :
        """
            * it will stop the network and set the state on not running (running=False).
            * Require to have the network already running
        """
        if self.running :
            if self.controllerrunning :
                LOG.error('the controller should be stopped first...')
            else :
                LOG.warning('stopping the network...')
                self.stop_snmp()
                self.network.stop()
                self.running = False
                if self.verbose :
                    self.set_prompt()
        else :
            LOG.error('The network is not running...')


    def _start_controller(self,line) :
        """
            * it will start the Fibbing controller and set the state on running.
            * Require to have a running network
            * Require to have some available requirements
        """
        if not self.controllerrunning :
            if self.setup_requirement() :
                LOG.info('Start controller')
                self.launch_controller()
                if self.checker :
                    LOG.info('Checking requirement deployment...')
                    # time.sleep(5)
                    self.check_requirement()
        else :
            LOG.error('The controller is already running...')

    def _apply_new_requirement(self, line) :
        """
            * add the new requirements to the controller
            * Require running controller
            * should have new requirements
        """
        if self.controllerrunning :
            if self.setup_requirement() :
                if self.process_requirement() :
                    LOG.info('Apply new requirement')
                    LOG.debug('Trying to refresh topo')
                    self.manager.commit_change()
                    if self.checker :
                        # time.sleep(2)
                        self.check_requirement()

        else :
            LOG.error('The controller must be running')


    def _stop_controller(self, line ) :
        """
            * if the controller is running, it will stop
              the fibbing controller
        """
        if self.controllerrunning :
            self.manager.stop()
            LOG.warning('Stopping controller...')
            self.controllerrunning = False
            LOG.info('Clearing all stored requirements')
            for key in self.cache.keys() :
                del self.cache[key]

            if self.verbose :
                self.set_prompt()

        else :
            LOG.error('Contoller is not running...')


    def _enable_auto_schedule(self, line ):
        """
            * periodically checks the scheduled requirements, and start if
              their starting deadline has been reached and stop them
              if their ending deadline has been reached
        """
        if self.controllerrunning :
            if not self.auto_schedule :
                LOG.info('Enable auto schedule')
                timer_th = threading.Thread(target=self.schedule_requirement)
                timer_th.start()
                self.auto_schedule = True
                if self.verbose :
                    self.set_prompt()
            else :
                LOG.error('Auto schedule already running')
        else :
            LOG.error('Contoller must be running')
    def _halt_auto_schedule(self, line ):
        """
            * stop the auto schedule function
        """
        if self.auto_schedule :
            self.timerEvent.set()
            LOG.info('halt auto schedule')
            self.auto_schedule = False
            if self.verbose :
                self.set_prompt()

    def _show_status(self,line) :
        """
            * show the status of the network
        """
        global newconfig
        global new_req
        topdelimiter = '+++++++'
        enddelimiterFalse = ' |'
        enddelimiterTrue  = '  |'
        netstate = str(self.running)
        NewConfigState =  str(newconfig)
        StoredConfigState = str(self.firstconfig)
        CtrlState = str(self.controllerrunning)
        NewREqState = str(new_req)
        StoredReqState = str(self.isrequirement)

        colors = {'False' : 'red', 'True' : 'green'}

        netstate = colored(netstate, colors.get(netstate), attrs=['bold'])
        NewConfigState = colored(NewConfigState, colors.get(NewConfigState), attrs=['bold'])
        StoredConfigState = colored(StoredConfigState, colors.get(StoredConfigState), attrs=['bold'])

        CtrlState = colored(CtrlState, colors.get(CtrlState), attrs=['bold'])
        NewREqState = colored(NewREqState, colors.get(NewREqState), attrs=['bold'])

        StoredReqState = colored(StoredReqState, colors.get(StoredReqState), attrs=['bold'])

        if self.running :
            netstate = netstate + enddelimiterTrue
        else :
            netstate = netstate + enddelimiterFalse

        if newconfig:
            NewConfigState =  NewConfigState + enddelimiterTrue
        else :
            NewConfigState =  NewConfigState + enddelimiterFalse

        if self.firstconfig :
             StoredConfigState =  StoredConfigState + enddelimiterTrue
        else :
            StoredConfigState =  StoredConfigState + enddelimiterFalse

        if self.controllerrunning :
            CtrlState = CtrlState + enddelimiterTrue
        else :
            CtrlState = CtrlState + enddelimiterFalse

        if new_req :
            NewREqState = NewREqState + enddelimiterTrue
        else :
            NewREqState = NewREqState + enddelimiterFalse

        if self.isrequirement :
            StoredReqState =  StoredReqState + enddelimiterTrue
        else :
            StoredReqState =  StoredReqState + enddelimiterFalse

        print '+++++++++++++++++++++++++++' + '+++++++'
        print '* network running :      | ' + netstate
        print '* new configuration :    | ' +  NewConfigState
        print '* stored configuration : | ' +  StoredConfigState
        print '+++++++++++++++++++++++++++' + '+++++++'
        print '* controller running :   | ' + CtrlState
        print '* new requirements:      | ' +  NewREqState
        print '* stored requirements:   | ' +  StoredReqState
        print '+++++++++++++++++++++++++++' + '+++++++'

    def _quit(self, args):
        """
            * Quits the program.
            * /!\ : require to have NO RUNNING  network
            * /!\ : require to have NO RUNNING  controller

        """
        if self.running :
            LOG.error('The network is still running...')
        else :
            self.do_halt_auto_schedule('Forcing Halt')
            LOG.info("Quitting...")
            raise SystemExit


    # ---------------------------------------------------
    #               lib functions
    # ---------------------------------------------------
    def shutdown(self):
        """
            shutdown the two daemon thread, handler
            of ConfD Agent commits
        """
        LOG.info('Closing connection')

        self.network_server.shutdown()
        self.network_server.server_close()

        self.controller_server.shutdown()
        self.controller_server.server_close()


    def stop_controller(self) :
        if self.controllerrunning :
            self.manager.stop()
            LOG.warning('Stopping controller...')
            self.controllerrunning = False
            if self.verbose :
                self.set_prompt()
        else :
            LOG.error('Contoller is not running...')

    def setup_requirement(self) :
        """
            check that there is some requirements
            and store them
        """
        Success = False
        global new_req
        global has_req
        global E
        global d_req
        if has_req or self.isrequirement:
            if new_req :
                self.isrequirement = True
                self.requirements = d_req
                LOG.info('Storing JSON requirements...')

            if self.running :
                new_req = False
                if E.is_set() :
                    E.clear()
                Success = True

            else :
                LOG.error('The network must be running before starting the controller')
        else :
            LOG.error('Need some requirements...')

        return Success

    def launch_controller(self):
        """
            Start the controller with some initial requirements
        """
        try :
            self.manager = MultipleSouthboundManager(self.get_ctrls())
            # self.manager = MultipleSouthboundManager([self.get_first_ctrl()])
            if self.process_requirement() :

                LOG.debug('Trying to refresh topo')
                self.manager.commit_change()


            self.manager.run()
            self.controllerrunning = True
            if self.verbose :
                self.set_prompt()


        except Exception as e :
            LOG.critical('Error ' + str(e))




    def add_requirement(self) :
        """
            Add/Remove new requirements that the controller will apply
            to the network
            Check the stored requirements flags and apply operation
            accordingly
        """
        try :
            REFRESH = False
            for key in self.cache.keys() :
                if self.process_flags(key) :
                    REFRESH = True
            if REFRESH : #and not start :
                LOG.debug('Trying to refresh topo')
                self.manager.commit_change()
        except Exception as e :
            LOG.critical("Error : "+str(e))

    def add_scheduled_requirement(self) :
        """
            Add/Remove new requirements that the controller will apply
            to the network
            Check the stored requirements flags and apply operation
            accordingly
        """
        try :
            REFRESH = False
            for key in self.scheduled_req :
                if self.process_flags(key) :
                    REFRESH = True

        except Exception as e :
            LOG.critical("Error : "+str(e))



    def start_network(self) :
        """
            Start the Mininet network
        """
        self.init_configuration_network()
        self.network = CustomIPNet(topo=CustomTopo(self.data),
                          debug=_lib.DEBUG_FLAG,
                          intf=custom(TCIntf)
                          )

        self.network.start()
        # # Make sure no nodes are still waiting
        for node in self.network.values():
            while node.waiting:
                node.sendInt()
                node.waitOutput()
        # set state into running
        self.running = True
        # waiting for all LSA to be exchange
        time.sleep(self.waitingTime)

        self.post_setup_network()

    def post_setup_network(self) :
        """
            Apply function after network has started
        """
        try :
            self.setup_node_fs()

            self.ip_name_mapping = build_ip_mapping(self.data)
            self.router_dest_mapping = build_router_dest_mapping(self.data)
            if self.verbose :
                self.set_prompt()

        except Exception as e :
            LOG.critical('Error :'+str(e))

    def setup_node_fs(self) :
        """
            set a file system per node
        """
        try :

            for node in self.network.keys():
                Node = self.network[node]

                Node.cmd(MKDIR+str(node))
                LOG.debug('create directory :'+str(node))

                Node.cmd('rm '+DIR+str(node)+'/'+PIDFILE)
                LOG.debug('remove potential pid file : ')

                Node.cmd('touch '+DIR+str(node)+'/'+PIDFILE)
                LOG.debug('create pid file : ')

                Node.cmd(STARTSNMP+DIR+str(node)+'/'+PIDFILE)
                LOG.debug('start snmpd on : '+ str(node))

        except Exception as e :
            LOG.critical('ERROR :'+str(e))

    def stop_snmp(self) :
        """
            clear node fs, and stop snmp
        """
        try :

            for node in self.network.keys():
                Node = self.network[node]

                killcmd = KILLSNMP1 +DIR+str(node)+'/'+PIDFILE+KILLSNMP2
                Node.cmd(killcmd)
                LOG.debug('kill snmpd on :'+str(node))

                removecmd = 'rm -R ' + DIR+'/'+str(node)
                Node.cmd(removecmd)
                LOG.debug('rm tmp directory on :'+str(node))

        except Exception as e :
            LOG.critical('ERROR :'+str(e))

    def process_network_config(self) :
        """
            process JSON object received by daemon thread
        """
        Success = False
        if not self.running :
            global firstconfig
            global d
            global newconfig
            global E
            if firstconfig or self.firstconfig:
                self.firstconfig = True
                if newconfig :
                    self.data = d
                    self.isdata = True
                    LOG.info('Storing JSON network configuration...')
                    newconfig = False
                    if E.is_set() :
                        E.clear()
                Success = True
            else :
                LOG.error('Need some configuration...')

        else :
            LOG.error('The network is already running...')

        return Success


    def init_configuration_network(self) :
        # check config
        write_CFG_ospf(self.data)
        self.data = gen_private_ips(self.data)
        network_topo = write_topology(self.data)
        write_private_ip_binding(data=self.data,topo=network_topo)
        self.db = TopologyDB(net=network_topo)

    def confd_cli_th(self) :

        # TODO explicitly use path to ConfD
        comdline =['xterm', '-e', 'make', 'cli']
        subprocess.call(comdline)

    def netconf_th(self) :
        comdline =['xterm', '-e', 'make', 'netconf-restart']
        subprocess.call(comdline)

    def get_time(self) :
        """
            return the time value
            NB: for simulation override this function to
                fast forward in time
        """
        return datetime.datetime.now()

    def plot_dag(self, dest) :
        """
            Plot the DAG of requirement for
            the destinatons dest
            using networkx, matplotlib
        """
        try :
            Edges = set()
            Nodes = set()
            Bottleneck = []
            for key in self.cache :
                if self.cache[key].dest == dest :
                    for node in self.cache[key].req :
                        Nodes.add(node)

                    for s, d in zip(self.cache[key].req[:-1],self.cache[key].req[1:] ) :
                        if (s, d) in Edges :
                            Bottleneck.append((s, d))
                        Edges.add((s, d))



            LOG.info('DAG composed of %s ' % str(Edges))
            LOG.info('Bottleneck edges found %s ' % str(Bottleneck))
            DAG = Gnx.Graph()
            LOG.debug('Building DAG with nodes %s' % str(Nodes))
            LOG.debug('Building DAG with edges %s' % str(Edges))
            DAG.add_nodes_from(list(Nodes))
            DAG.add_edges_from(list(Edges))

            Gnx.draw(DAG, node_color='c', edge_color='k', with_labels=True)
            time.sleep(3)
            Dplt.show()
        except Exception as e :
            LOG.critical('ERROR :'+str(e))
    def update_schedule_requirement(self) :
        """
            scan through the cache to check if the
            scheduled requirements have reach their end or start_h
            deadline
        """
        self.lock.acquire()
        ct = self.get_time()
        REFRESH = False

        for key in self.scheduled_req :
            self.cache[key].reset_all_flags()
            self.cache[key].set_flag(F_present)
            if self.cache[key].status == SCHED :
                start_h = self.cache[key].start_hour
                end_h   = self.cache[key].end_hour
                weekdays = self.cache[key].weekdays

                if ct.date().weekday() in weekdays :
                    if (ct.time().hour, ct.time().minute) > start_h and \
                        (ct.time().hour, ct.time().minute) < end_h  :
                        if self.cache[key].runningstatus == DOWN :
                            if self.cache[key].scheduleType == BAND :
                                from_R = self.cache[key].from_R
                                to_R  = self.cache[key].to_R
                                bw_perc = self.cache[key].bw_perc

                                if self.check_bw_status(from_R,to_R,bw_perc) :
                                    self.cache[key].set_flag(F_Add)
                                    self.cache[key].set_runningstatus(UP)

                                else :
                                    self.cache[key].set_flag(F_OK)

                            elif self.cache[key].scheduleType == BACK :
                                from_R = self.cache[key].from_R
                                to_R  = self.cache[key].to_R

                                if self.check_link_status(from_R,to_R)  :
                                    self.cache[key].set_flag(F_Add)
                                    self.cache[key].set_runningstatus(UP)
                                else :
                                    self.cache[key].set_flag(F_OK)
                            else :
                                self.cache[key].set_flag(F_Add)
                                self.cache[key].set_runningstatus(UP)

                        elif self.cache[key].runningstatus == UP:
                            if self.cache[key].scheduleType == BACK :
                                from_R = self.cache[key].from_R
                                to_R  = self.cache[key].to_R

                                if not self.check_link_status(from_R,to_R)  :
                                    self.cache[key].set_flag(F_halt)
                                    self.cache[key].set_runningstatus(DOWN)
                                else :
                                    self.cache[key].set_flag(F_OK)

                    elif self.cache[key].runningstatus == UP and \
                        (ct.time().hour, ct.time().minute) > end_h :
                        self.cache[key].set_flag(F_halt)
                        self.cache[key].set_runningstatus(DOWN)
                    else :
                        self.cache[key].set_flag(F_OK)
                else :
                    self.cache[key].set_flag(F_OK)

            else :
                self.cache[key].set_flag(F_OK)

            if self.process_flags(key) :
                REFRESH = True

        self.lock.release()
        return REFRESH


    def schedule_requirement(self) :
        """
            should periodically (SchedulePeriod) launch the update on
            scheduled requirements
        """
        LOG.info('Starting the auto schedule')
        while not self.timerEvent.is_set():

            if self.controllerrunning :
                if self.update_schedule_requirement() :
                    LOG.debug('Trying to refresh topo')
                    self.manager.commit_change()


            self.timerEvent.wait(timeout=self.SchedulePeriod)

        if self.timerEvent.is_set() :
            self.timerEvent.clear()

        LOG.info('stopping the auto schedule')

    def set_prompt(self) :
        """
            update the prompt according to the current status
            variable
        """
        prompt =  self.base_prompt
        if self.running :
            text = colored('Yes', 'green', attrs=['bold'])
            prompt = prompt + '(N:' + text
        else :
            text = colored('No', 'red', attrs=['bold'])
            prompt = prompt + '(N:' + text

        if self.controllerrunning :

            text = colored('Yes', 'green', attrs=['bold'])
            prompt = prompt + ', C:' + text

        else :
            text = colored('No', 'red', attrs=['bold'])
            prompt = prompt + ', C:' + text

        if self.auto_schedule :
            text = colored('Yes', 'green', attrs=['bold'])
            prompt = prompt + ', A:'+text
        else :
            text = colored('No', 'red', attrs=['bold'])
            prompt = prompt + ', A:'+text

        prompt = prompt + ')'
        prompt = prompt + self.end_prompt
        self.prompt = prompt


    def get_bw(self, R1,R2) :
        """
            get the bandwidth configured for link
            R1<->R2
        """
        try :
            d = self.data
            conf = d['config']
            ospf = conf.get('ospf')
            lsa  = ospf.get('lsa-config')
            ospf_routers = ospf.get('ospf-routers')
            ospf_links = ospf.get('link')
            bw = False

            for OL in ospf_links :
                src = OL.get('src')
                dest = OL .get('dest')

                if src.get('name') == R1 and dest.get('name') == R2 :
                    bw = src.get('ospf-interface').get('bw')
                elif src.get('name') == R2 and dest.get('name') == R1 :
                    bw = dest.get('ospf-interface').get('bw')

            return int(bw)*1000.0

        except Exception as e :
            LOG.critical(str(e))
            return False

    def get_intf_by_router(self,from_R,to_R) :
        """
            return the interface name of router
            from_R connected to router to_R
        """
        try :
            if from_R in self.network and to_R in self.network :
                node1 =  self.network[from_R]
                node2 = self.network[to_R]

                connected_intfs1 = [itf
                                   for itf in node1.intfList()
                                   if L3Router.is_l3router_intf(otherIntf(itf)) and
                                   itf.name != 'lo']
                connected_intfs2 = [itf
                                   for itf in node2.intfList()
                                   if L3Router.is_l3router_intf(otherIntf(itf)) and
                                   itf.name != 'lo']

                intfName = ''
                for intf in connected_intfs1 :
                    oposite = otherIntf(intf)
                    if oposite in connected_intfs2 :
                        intfName = intf

                return intfName

        except Exception as e :
            LOG.critical('ERROR : ' +str(e))
            return False

    def check_bw(self,from_R,to_R,bw_perc) :
        """
            check that the bandwidth for the link
            from_R -> to_R does not exceed bw_perc
        """
        try :
            if from_R in self.network and to_R in self.network :
                node1 =  self.network[from_R]
                node2 = self.network[to_R]

                connected_intfs1 = [itf
                                   for itf in node1.intfList()
                                   if L3Router.is_l3router_intf(otherIntf(itf)) and
                                   itf.name != 'lo']
                connected_intfs2 = [itf
                                   for itf in node2.intfList()
                                   if L3Router.is_l3router_intf(otherIntf(itf)) and
                                   itf.name != 'lo']

                intfName = ''
                for intf in connected_intfs1 :
                    oposite = otherIntf(intf)
                    if oposite in connected_intfs2 :
                        intfName = intf

                if intfName :
                    command = 'ifstat -b -i '+ str(intfName) +' 5 1'

                    bw = self.get_bw(from_R,to_R)
                    if bw :
                        LOG.debug('Testing bandwidth (max ' + str(bw) +' Kbps) on interface '+str(intfName))
                        results = node1.cmd(command)
                        resulttab = results.split()
                        bwin = float(resulttab[-2])
                        bwout = float(resulttab[-1])

                        if bwout/bw < bw_perc/100.0 :
                            LOG.debug('bandwidth within limit '+str(bw_perc)+' percent')
                            return False
                        else :
                            LOG.debug('bandwidth over limit '+str(bw_perc)+' percent')
                            return True
                    else :
                        LOG.error('No bw found for those routers ')
                        return False


                else :
                    LOG.error('No intf found for those routers ')
                    return False

        except Exception as e :
            LOG.critical(str(e))
            return False


    def get_intf_stats(self, index, node,ip) :
        """
            get via SNMP the interface stats
        """
        try :
            getcmd = SNMPBULKGET+str(ip)+" ifOutOctet 1.3.6.1.2.1.1.1.0"
            intfstats = node.cmd(getcmd)
            LOG.debug('\n'+intfstats+'\n')

            lines = intfstats.split('\n')
            speed = 0
            ifInOctets = 0
            ifOutOctets = 0
            upTime =0
            for line in lines :
                sp_line = line.split()
                if sp_line :
                    first = sp_line[0].split('::')[-1]
                    if str(first) == 'sysUpTimeInstance' :
                        upTime = sp_line[-1].split()[-1]
                    elif first and str(first) == 'ifOutOctets.'+str(index) :
                        ifOutOctets = int(sp_line[-1])


            LOG.debug('sysUpTimeInstance :'+str(upTime))
            LOG.debug('ifOutOctet : '+ str(ifOutOctets))
            return upTime, ifOutOctets

        except Exception as e :
            LOG.critical('ERROR :'+str(e))
            return False,False

    def get_link_status(self, index, node,ip) :
        """
            get via SNMP the interface stats
        """
        try :
            getcmd = SNMPWALK+str(ip)+" ifOperStatus."+str(index)
            intfstats = node.cmd(getcmd)
            LOG.debug('\n'+intfstats+'\n')

            lines = intfstats.split('\n')
            ifOperStatus = False
            for line in lines :
                sp_line = line.split()
                if sp_line :
                    first = sp_line[0].split('::')[-1]
                    if str(first) == 'ifOperStatus.'+str(index) :
                        ifOperStatus = str(sp_line[-1].split()[-1])


            LOG.debug('ifOperStatus :'+str(ifOperStatus))

            return ifOperStatus

        except Exception as e :
            LOG.critical('ERROR :'+str(e))
            return False

    def bandwidth(self, octets1,octets2,speed,delta_t) :
        """
            compute bandwidth utilization based on the
            args
        """
        try :
            band = 0
            deltaOct = octets2 - octets1
            band = (deltaOct*8.0*100.0)/float(delta_t * speed)
            return band

        except Exception as e :
            LOG.critical('Error :' +str(e))
            return False

    def diff_time(self, upTime1, upTime2) :
        """
            compute delta time between two responses
        """
        try :
            time1 = upTime1.split(':')
            time2 = upTime2.split(':')

            time1Sec = float(time1[0])*3600 + float(time1[1])*60 + float(time1[2])
            time2Sec = float(time2[0])*3600 + float(time2[1])*60 + float(time2[2])

            return time2Sec - time1Sec
        except Exception as e :
            LOG.critical('Error :' +str(e))

    def get_snmp_ctrl(self) :
        """
            from the JSON config, retrieve the SNMP conroller
        """
        try :
            if self.isdata :
                data = self.data
                return str(data.get('config').get('main-controller'))

        except Exception as e :
            LOG.critical('Error :'+str(e))
            return False

    def get_first_ctrl(self) :
        """
            from the JSON config, retrieve the SNMP conroller
        """
        try :
            if self.isdata :
                data = self.data.get('config')
                fibbing_ctrl = data.get('fibbing-controller')
                ctrl_links = fibbing_ctrl.get('links')
                return str(ctrl_links[0].get('controller').get('name'))

        except Exception as e :
            LOG.critical('Error :'+str(e))
            return False

    def get_ctrls(self) :
        """
            from the JSON config, retrieve the SNMP conroller
        """
        try :
            if self.isdata :
                data = self.data.get('config')
                fibbing_ctrl = data.get('fibbing-controller')
                ctrl_links = fibbing_ctrl.get('links')
                ctrl = []
                for c in map(lambda x: x.get('controller').get('name'), ctrl_links):
                    if c not in ctrl :
                        ctrl.append(c)

                return ctrl

        except Exception as e :
            LOG.critical('Error :'+str(e))
            return False

    def setup_snmp_manager(self) :
        try :
            if not self.snmpCtrl :
                temp = self.get_snmp_ctrl()
                if temp :
                    self.snmpCtrl = temp
                else :
                    LOG.error('No SNMP manager found')
                    self.snmpCtrl = str(self.network.hosts[0].name)
            else :
                if self.snmpCtrl not in self.network :
                    LOG.error('No SNMP manager found')
                    self.snmpCtrl = str(self.network.hosts[0].name)
        except Exception as e :
            LOG.critical('Error :'+str(e))


    def check_traceroute(self,from_R,to_R) :
        """
            run a traceroute between from_R, and to_R
            Note : from_R and to_R should be hosts/destinations
        """
        try :
            if self.running :
                if from_R in self.network and to_R in self.network :
                    node1 =  self.network[from_R]
                    node2 = self.network[to_R]
                    Route = node1.cmd('paris-traceroute '+node2.IP())

                    return Route
                else:
                    LOG.error("router not in network")
                    return False

        except Exception as e :
            LOG.critical('Error : '+ str(e))
            return False




    def check_requirement(self) :
        """
            check that the requirements are correctly
            applied to the network
        """
        try:
            if self.isrequirement :
                for key in self.cache.keys() :
                    if self.cache[key].status == UP or \
                    (self.cache[key].status == SCHED and \
                    self.cache[key].runningstatus == UP) :
                        if not self.check_single_requirement(key) :
                            LOG.error('requirement '+str(key)+ ' does not seem to work')
                        else :
                            LOG.info('Requirement '+str(key)+' seems to be correctly working')

        except Exception as e:
            LOG.critical('Error :'+str(e))

    def parse_traceroute(self,traceroute):
        """
        take a traceroute as input and parse it to just retrun a list of the IP's in the right order.
        """
        split=traceroute.split('\n')
        pattern2= r"[0-9]+(?:\.[0-9]+){3}"
        path=[]
        for i in split[3:]:
            test = re.search(pattern2,i)
            if test and test.group(0):
                path.append(test.group(0))
        return path


# --------------------------------------------------------
class NetworkManagerCLI(NetworkManagerCore,Cmd):
    """
        CLI that allow to :
        * configure a network with the confD CLI provided
          via the YANG model
        * run the netwrok via Mininet and Quagga
        * launch the Mininet CLI on the running netwrok
        * configure some fibbing requirements with the confD
          CLI
        * launch the fibbing controller on the Mininet/Quagga
          running network

    """
    def __init__(self, verbose=True,checker=False) :
        NetworkManagerCore.__init__(self,checker=checker)
        self.verbose = verbose
        Cmd.__init__( self )
        self.do_info('info')
        self.base_prompt = "[NetworkManagerCLI]"
        self.end_prompt = "$ "
        if self.verbose :
            self.set_prompt()
        else :
            self.prompt = "[NetworkManagerCLI]$ "


    def start(self) :
        """
            start the CLI
        """
        try :
            while True :
                try :
                    self.cmdloop('Starting prompt...')
                except KeyboardInterrupt  as e :
                    # prevent hard exit
                    LOG.error('Please use <quit> command to exit ...')
                    pass
        except SystemExit :
            self.shutdown()
    # ---------------------------------------------------
    #               CLI Commands
    # ---------------------------------------------------
    def do_print_dag_for(self, line) :
        """
            Print the DAG of all path requirement
            for the given destination
            usage: print_dag_for <destination hosts>
        """
        self._print_dag_for(line)

    def do_ip(self, line):
        """
            usage:
               ip <ipadress>
            return name of the node corresponding to
            the ipaddress
        """
        self._ip(line)

    def do_set_time_granularity(self, line) :
        """
            * INPUT :  a integer value of time in sec for
              the period at which the application will check
              the scheduled requirements
        """
        self._set_time_granularity(line)

    def do_show_time_granularity(self, line) :
        """
            * display the current time granularity
        """
        LOG.info('Time granularity : '+ str(self.SchedulePeriod))

    def do_halt_requirement(self, line) :
        """
            * INPUT :  key of the requirement
            * if the requirement is running, it will be stopped
        """
        self._halt_requirement(line)

    def do_show_requirements(self,line) :
        """
            * display the stored requirements
        """
        self._show_requirements(line)

    def do_xterm_config(self, line) :
        """
            * Launch an xterm terminal with the confD CLI
        """
        self._xterm_config(line)

    def do_config(self, line ) :
        """
            * Launch the confD CLI
        """
        self._config(line)

    def do_mininet_cli(self,line) :
        """
            * it will start the Mininet CLI on the network
            * Require to have the network already running
        """
        self._mininet_cli(line)
    # *************************
    # network & controller command
    # *************************
    def do_start_network(self, line) :
        """
            * it will start the network and set the state on running.
            * Require to have some available configuration
        """
        self._start_network(line)

    def do_stop_network(self,line) :
        """
            * it will stop the network and set the state on not running (running=False).
            * Require to have the network already running
        """
        self._stop_network(line)

    def do_start_controller(self,line) :
        """
            * it will start the Fibbing controller and set the state on running.
            * Require to have a running network
            * Require to have some available requirements
        """
        self._start_controller(line)

    def do_apply_new_requirement(self, line) :
        """
            * add the new requirements to the controller
            * Require running controller
            * should have new requirements
        """
        self._apply_new_requirement(line)

    def do_stop_controller(self, line ) :
        """
            * if the controller is running, it will stop
              the fibbing controller
        """
        self._stop_controller(line)

    def do_enable_auto_schedule(self, line ):
        """
            * periodically checks the scheduled requirements, and start if
              their starting deadline has been reached and stop them
              if their ending deadline has been reached
        """
        self._enable_auto_schedule(line)

    def do_halt_auto_schedule(self, line ):
        """
            * stop the auto schedule function
        """
        self._halt_auto_schedule(line)


    def do_info(self, line ) :
        """
            * show some explanations about the CLI
        """
        print '****************************************'
        print '   Welcome to Nework Manager CLI'
        print '* type <help> to have more information '
        print '  about the different commands'
        print '* type <config> or <xterm_config> to start'
        print '  configuration CLI'
        print '****************************************'

    def do_terminal(self,line):
        """
            start a terminal bash.
        """
        os.system('/bin/bash')

    def do_show_status(self,line) :
        """
            * show the status of the network
        """
        self._show_status(line)



    def emptyline( self ) :
        """Don't repeat last command when you hit return."""
        pass

    def default( self, line ):
        """Skip if command is not known"""
        pass


    def do_quit(self, args):
        """
            * Quits the program.
            * /!\ : require to have NO RUNNING  network
            * /!\ : require to have NO RUNNING  controller

        """
        self._quit(args)


    def do_print_network_config(self, line ) :
        """
            * Display the JSON network configuration received from
              the confD daemon
            * or 'no configuration stored'
        """
        if self.isdata :
            print json.dumps(self.data)

        else :
            print 'no configuration stored'

    def do_print_requirements(self, line ) :
        """
            * Display the JSON requirements received from
              the confD daemon
            * or 'no requirements stored'
        """
        if self.isrequirement :
            print json.dumps(self.requirements)
        else :
            print 'no requirements stored'
