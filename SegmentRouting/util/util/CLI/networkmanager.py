# Network Manager

# general purpose imports
import socket
import sys
import json
import argparse
import time
import threading
import SocketServer
import datetime
from cmd import Cmd
import sys
import time
import subprocess
import os
from ipaddress import ip_interface
import ipaddress
import random
from termcolor import colored
import re
import copy
import matplotlib.pyplot as plt
import networkx as nx


from util.checker.exception import checkNetworkConfig, checkRequirementConfig
from util.helper.Dijkstra import Graph, get_simple_path_req, is_ok_path_req, complete_path
from util.helper.topo import IPv6Topo
from util.helper.Quagga import *
from util.helper import *
from util.helper.southboundmanager import SRSouthboundManager

# package un util
from util import *

from nanonet.node import *
from nanonet.net import *


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
                with open(SR_OUT, 'r') as sr_out :
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
class NetworkManagerCore(object) :
    """
        Core functions that will make the
        bridge between the CLI, and interfaces
        exposed to the user, and the network

    """
    def __init__(self,checker=False) :
        self.checker = checker
        self.network = False
        self.running = False
        self.firstconfig = False
        self.waitingTime = 20
        self.isdata = False
        self.manager = False
        self.isrequirement = False
        self.requirements = False
        self.db = False
        self.store = {}
        self.timerEvent = threading.Event()
        self.lock = threading.Lock()
        self.SchedulePeriod = 60 # sec
        self.auto_schedule = False
        self.intf_index = {}
        self.scheduled_req = []
        self.snmpCtrl = False

        self.label_stack = {}
        self.ip_name_mapping = {}

        self.added_set = []
        self.remove_set = []
        self.key_to_remove = None
        self.replacing_set = []

        self.link_down = []

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
    def pre_process_flags(self, key) :
        """
            @API
            handle the flags of the requirement identified
            by its key. May call Southbound API
        """
        try :
            REFRESH = False
            if self.store[key].flags[F_OK] :
                return False
            if not self.store[key].flags[F_present] :
                if self.store[key].status == UP :
                    self.store[key].set_flag(F_stop)
                elif self.store[key].status == DOWN :
                    self.store[key].set_flag(F_delete)
                elif self.store[key].status == SCHED :
                    if self.store[key].runningstatus == UP :
                        self.store[key].set_flag(F_stop)
                    elif self.store[key].runningstatus == DOWN :
                        self.store[key].set_flag(F_delete)

            if self.store[key].flags[F_stop] :
                LOG.debug('Removing requirement %s' % key)
                self.manager.remove_requirement(key)
                self.remove_set.append(key)
                REFRESH = True
                return REFRESH

            if self.store[key].flags[F_halt] :
                LOG.debug('Halting requirement %s' % key)
                self.manager.remove_requirement(key)
                self.remove_set.append(key)
                REFRESH = True


            if self.store[key].flags[F_delete] :
                if key in self.remove_set :
                    # if requirement needs to be removed in the
                    # current transation postpone the del until
                    # the commit is sucessful
                    return REFRESH
                LOG.debug('deleting : %s ' % str(key))
                if self.store[key].status == SCHED :
                    remove_from_list(self.scheduled_req,key)

                del self.store[key]
                if self.label_stack.get(key) :
                    del self.label_stack[key]
                return REFRESH

            if self.store[key].flags[F_replace] :
                if key not in self.remove_set :
                    oldREQ = self.store[key]
                    newREQ = self.store[key].newRequirement
                    if self.store[key].status == SCHED and newREQ.status != SCHED:
                        remove_from_list(self.scheduled_req,key)
                    self.store[key] = newREQ
                    self.store[key].set_flag(F_replace)
                    self.store[key].set_newRequirement(oldREQ)
                    if self.store[key].status == SCHED :
                        self.scheduled_req.append(key)
                    LOG.debug('replacing %s : %s '% (key, str(self.store[key].req)))
                else :
                    # wait for confirmation that the old requirement
                    # is correct removed before replacing
                    return REFRESH

            if self.store[key].flags[F_Add] :
                LOG.debug('Flag Add for %s' % str(key))
                self.added_set.append(key)
                if not self.has_link_down(self.store[key].req) :
                    REQ = self.store[key]
                    rs = REQ.router
                    ds = REQ.dest
                    R = REQ.req
                    LOG.debug('Call Add API for %s' % str(key))
                    stack = self.manager.add_requirement(key,ds, R )
                    # self.added_set.append(key)
                    REFRESH = True
                    self.label_stack[key] = stack

            return REFRESH
        except Exception as e :
            LOG.critical('Error :' + str(e))
            return False

    def post_process_flags(self, key, status) :
        """
            @API
            post process the requirement based on the
            flags and the status of the updates
        """
        try :
            if self.store[key].flags[F_stop] :
                if status == T_SUCCESS :
                    # actually remove from cache
                    if self.store[key].status == SCHED :
                        remove_from_list(self.scheduled_req,key)
                    del self.store[key]
                    del self.label_stack[key]
                    LOG.debug('Removing requirement %s' % key)
                    return
                elif status == T_ABORT :
                    LOG.error('Transaction Aborted for %s' % key)
                    self.store[key].reset_all_flags()
                    return


            if self.store[key].flags[F_halt] :
                if status == T_SUCCESS :
                    if self.store[key].flags[F_replace] :
                        # perform the actual replace
                        newREQ = self.store[key].newRequirement
                        if self.store[key].status == SCHED and newREQ.status != SCHED:
                            remove_from_list(self.scheduled_req,key)
                        self.store[key] = newREQ
                        # self.store[key].set_flag(F_replace)
                        if self.store[key].status == SCHED :
                            self.scheduled_req.append(key)
                        LOG.debug('replacing %s : %s '% (key, str(self.store[key].req)))
                        # this new req will need to be pre_processed
                        self.replacing_set.append(key)
                        return

                    del self.label_stack[key]
                    if self.store[key].status == SCHED :
                        if self.store[key].runningstatus ==UP :
                            self.store[key].set_runningstatus(DOWN)
                    if self.store[key].status == UP :
                        self.store[key].set_status(DOWN)

                elif status == T_ABORT :
                    LOG.error('Transaction Aborted for %s' % key)
                    if self.store[key].flags[F_replace] :
                        self.store[key].reset_all_flags()
                        return

            if self.store[key].flags[F_delete] :
                if status == T_SUCCESS :
                    # actually remove from cache
                    LOG.debug('deleting : %s ' % str(key))
                    if self.store[key].status == SCHED :
                        remove_from_list(self.scheduled_req,key)

                    del self.store[key]
                    if self.label_stack.get(key) :
                        del self.label_stack[key]
                    return
                elif status == T_ABORT :
                    LOG.error('Transaction Aborted for %s' % key)
                    self.store[key].reset_all_flags()
                    return

            if self.store[key].flags[F_Add] :
                if status == T_SUCCESS :
                    if self.store[key].status == SCHED :
                        if self.store[key].runningstatus == DOWN :
                            self.store[key].set_runningstatus(UP)
                    if self.store[key].status == DOWN :
                        self.store[key].set_status(UP)


                elif status == T_ABORT :
                    if self.store[key].status == UP :
                        self.store[key].set_status(DOWN)

                    if self.store[key].status == SCHED :
                        if self.store[key].runningstatus == UP :
                            self.store[key].set_runningstatus(DOWN)


                    LOG.error('Transaction Aborted for %s' % key)
                    if self.label_stack.get(key) :
                        del self.label_stack[key]


            # if key still in cache
            if self.store.get(key) :
                self.store.get(key).reset_all_flags()


        except Exception as e :
            LOG.critical('Error :' + str(e))

    def process_requirement(self) :
        """
            @API
            go through the stored requirements,
            * check the requirement configuration
            * to path expantion if * in path
            * compare new requirements with stored ones
              and set the corresponding Flags
              if changes detected
        """


        conf = self.requirements['config']
        link =  conf["link"]

        tmp_keys = self.store.keys()
        REFRESH = False

        for x in link :
            if str(x.get('name')) not in self.store or\
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
                if not self.store.get(str(x.get('name'))) :
                    if str(x.get('status')) == str(UP) :
                        newRequirement = Requirement(str(x.get('name')), ds, rs, Req, str(x.get('status')))
                        newRequirement.set_flag(F_Add)
                        newRequirement.set_flag(F_present)
                        self.store[ str(x.get('name'))] = newRequirement
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
                        self.store[ str(x.get('name'))] = newRequirement
                        LOG.debug('Storing new requirements '+  str(x.get('name')))
                        self.scheduled_req.append(str(x.get('name')))

                else :
                    # the requirement is already stored
                    if str(x.get('status')) == str(DOWN) :
                        if self.store.get(str(x.get('name'))).status == SCHED :
                            if self.store.get(str(x.get('name'))).runningstatus == UP :
                                self.store.get(str(x.get('name'))).set_flag(F_stop)
                                self.store.get(str(x.get('name'))).set_flag(F_present)
                                LOG.debug('Seting Flag stop ')
                            elif self.store.get(str(x.get('name'))).runningstatus == DOWN :
                                self.store.get(str(x.get('name'))).set_flag(F_delete)
                                self.store.get(str(x.get('name'))).set_flag(F_present)
                                LOG.debug('Seting Flag Delete ')
                        else :
                            self.store.get(str(x.get('name'))).set_flag(F_stop)
                            self.store.get(str(x.get('name'))).set_flag(F_present)
                            LOG.debug('Seting Flag stop ')
                    else :
                        newRequirement =  Requirement(str(x.get('name')), ds, rs, Req,str(x.get('status')))
                        if self.store.get(str(x.get('name'))).to_string() !=  newRequirement.to_string() :
                            if self.store.get(str(x.get('name'))).status == UP and newRequirement.status== UP :
                                self.store.get(str(x.get('name'))).set_flag(F_halt)
                                self.store.get(str(x.get('name'))).set_flag(F_replace)

                                newRequirement.set_flag(F_present)
                                newRequirement.set_flag(F_Add)
                                self.store.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                self.store.get(str(x.get('name'))).set_flag(F_present)
                                LOG.debug(' Diff req UP UP ')

                            elif self.store.get(str(x.get('name'))).status == UP and newRequirement.status== SCHED :
                                self.store.get(str(x.get('name'))).set_flag(F_halt)
                                self.store.get(str(x.get('name'))).set_flag(F_replace)

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
                                self.store.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                self.store.get(str(x.get('name'))).set_flag(F_present)
                                LOG.debug(' Diff req UP SCHED ')

                            elif self.store.get(str(x.get('name'))).status == SCHED and newRequirement.status== UP :
                                LOG.debug(' Diff req SCHED UP ')
                                if self.store.get(str(x.get('name'))).runningstatus == UP :
                                    self.store.get(str(x.get('name'))).set_flag(F_halt)
                                    self.store.get(str(x.get('name'))).set_flag(F_replace)
                                    newRequirement.set_flag(F_present)
                                    newRequirement.set_flag(F_Add)
                                    self.store.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                    self.store.get(str(x.get('name'))).set_flag(F_present)

                                elif self.store.get(str(x.get('name'))).runningstatus == DOWN :
                                    self.store.get(str(x.get('name'))).set_flag(F_replace)
                                    newRequirement.set_flag(F_present)
                                    newRequirement.set_flag(F_Add)
                                    self.store.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                    self.store.get(str(x.get('name'))).set_flag(F_present)

                            elif self.store.get(str(x.get('name'))).status == SCHED and newRequirement.status== SCHED :
                                LOG.debug(' Diff req SCHED SHED ')
                                if self.store.get(str(x.get('name'))).runningstatus == UP :
                                    self.store.get(str(x.get('name'))).set_flag(F_halt)
                                    self.store.get(str(x.get('name'))).set_flag(F_replace)
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
                                    self.store.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                    self.store.get(str(x.get('name'))).set_flag(F_present)

                                elif self.store.get(str(x.get('name'))).runningstatus == DOWN :
                                    self.store.get(str(x.get('name'))).set_flag(F_replace)

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
                                    self.store.get(str(x.get('name'))).set_newRequirement(newRequirement)
                                    self.store.get(str(x.get('name'))).set_flag(F_present)
                                    LOG.debug(' Diff req SCHED SHED ')


                        else :
                            # no modifications within the requirement
                            if self.store.get(str(x.get('name'))).status == UP and newRequirement.status== UP :
                                self.store.get(str(x.get('name'))).set_flag(F_OK)
                                self.store.get(str(x.get('name'))).set_flag(F_present)

                            elif self.store.get(str(x.get('name'))).status == SCHED and newRequirement.status== SCHED :
                                schedinfo = x.get('scheduled')
                                if schedinfo.get('type') == TIME and \
                                self.store.get(str(x.get('name'))).scheduleType == TIME:
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    newRequirement.set_start_hour(startTuple, start_h_str)
                                    newRequirement.set_end_hour(endTuple, end_h_str)
                                    days = schedinfo.get('days')
                                    newRequirement.set_weekday(days)
                                    newRequirement.set_type(TIME)

                                    if self.store.get(str(x.get('name'))).sched_to_string() != newRequirement.sched_to_string() :
                                        self.store.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                        self.store.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                        self.store.get(str(x.get('name'))).set_weekday(days)
                                        if self.store.get(str(x.get('name'))).runningstatus == UP :
                                            self.store.get(str(x.get('name'))).set_flag(F_halt)
                                        self.store.get(str(x.get('name'))).set_flag(F_present)

                                    else :
                                        self.store.get(str(x.get('name'))).set_flag(F_OK)
                                        self.store.get(str(x.get('name'))).set_flag(F_present)

                                elif (schedinfo.get('type') == BAND or schedinfo.get('type') == BACK) and \
                                (self.store.get(str(x.get('name'))).scheduleType == BAND or \
                                 self.store.get(str(x.get('name'))).scheduleType == BACK):
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

                                    if self.store.get(str(x.get('name'))).bw_to_string() != newRequirement.bw_to_string() :
                                        self.store.get(str(x.get('name'))).set_bw_perc(int(link_bw.get('bw-perc')))
                                        self.store.get(str(x.get('name'))).set_link(link_bw.get('from'), link_bw.get('to'))
                                        self.store.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                        self.store.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                        self.store.get(str(x.get('name'))).set_weekday(days)
                                        self.store.get(str(x.get('name'))).set_type(schedinfo.get('type'))
                                        if self.store.get(str(x.get('name'))).runningstatus == UP :
                                            self.store.get(str(x.get('name'))).set_flag(F_halt)
                                        self.store.get(str(x.get('name'))).set_flag(F_present)

                                    else :
                                        self.store.get(str(x.get('name'))).set_flag(F_OK)
                                        self.store.get(str(x.get('name'))).set_flag(F_present)

                                elif (schedinfo.get('type') == BAND  or schedinfo.get('type') == BACK) and \
                                     self.store.get(str(x.get('name'))).scheduleType == TIME:
                                    link_bw  = schedinfo.get('link')
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    days = schedinfo.get('days')
                                    self.store.get(str(x.get('name'))).set_bw_perc(int(link_bw.get('bw-perc')))
                                    self.store.get(str(x.get('name'))).set_link(link_bw.get('from'), link_bw.get('to'))
                                    self.store.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                    self.store.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                    self.store.get(str(x.get('name'))).set_weekday(days)
                                    self.store.get(str(x.get('name'))).set_type(schedinfo.get('type'))
                                    if self.store.get(str(x.get('name'))).runningstatus == UP :
                                        self.store.get(str(x.get('name'))).set_flag(F_halt)
                                    self.store.get(str(x.get('name'))).set_flag(F_present)

                                elif schedinfo.get('type') == TIME and \
                                (self.store.get(str(x.get('name'))).scheduleType == BAND or\
                                 self.store.get(str(x.get('name'))).scheduleType == BACK):
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    days = schedinfo.get('days')
                                    self.store.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                    self.store.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                    self.store.get(str(x.get('name'))).set_weekday(days)
                                    self.store.get(str(x.get('name'))).set_type(TIME)
                                    if self.store.get(str(x.get('name'))).runningstatus == UP :
                                        self.store.get(str(x.get('name'))).set_flag(F_halt)
                                    self.store.get(str(x.get('name'))).set_flag(F_present)

                            elif self.store.get(str(x.get('name'))).status == UP and newRequirement.status== SCHED :

                                schedinfo = x.get('scheduled')
                                if schedinfo.get('type') == TIME :
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    days = schedinfo.get('days')
                                    self.store.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                    self.store.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                    self.store.get(str(x.get('name'))).set_weekday(days)
                                    self.store.get(str(x.get('name'))).set_type(TIME)
                                    self.store.get(str(x.get('name'))).set_flag(F_halt)
                                    self.store.get(str(x.get('name'))).set_flag(F_present)
                                    self.store.get(str(x.get('name'))).set_status(SCHED)

                                if schedinfo.get('type') == BAND or schedinfo.get('type') == BACK:
                                    link_bw  = schedinfo.get('link')
                                    days = schedinfo.get('days')
                                    start_h_str = str(schedinfo.get('start-hour'))
                                    end_h_str = str(schedinfo.get('end-hour'))
                                    startTuple = (int(start_h_str.split(':')[0]),int(start_h_str.split(':')[1]) )
                                    endTuple = (int(end_h_str.split(':')[0]),int(end_h_str.split(':')[1]) )
                                    self.store.get(str(x.get('name'))).set_bw_perc(int(link_bw.get('bw-perc')))
                                    self.store.get(str(x.get('name'))).set_link(link_bw.get('from'), link_bw.get('to'))
                                    self.store.get(str(x.get('name'))).set_start_hour(startTuple, start_h_str)
                                    self.store.get(str(x.get('name'))).set_end_hour(endTuple, end_h_str)
                                    self.store.get(str(x.get('name'))).set_weekday(days)
                                    self.store.get(str(x.get('name'))).set_type(schedinfo.get('type'))
                                    self.store.get(str(x.get('name'))).set_flag(F_halt)
                                    self.store.get(str(x.get('name'))).set_flag(F_present)
                                    self.store.get(str(x.get('name'))).set_status(SCHED)

                                self.scheduled_req.append(str(x.get('name')))


                            elif self.store.get(str(x.get('name'))).status == SCHED and newRequirement.status== UP :
                                if self.store.get(str(x.get('name'))).runningstatus == UP :
                                    self.store.get(str(x.get('name'))).set_flag(F_OK)
                                elif self.store.get(str(x.get('name'))).runningstatus == DOWN :
                                    self.store.get(str(x.get('name'))).set_flag(F_Add)

                                self.store.get(str(x.get('name'))).set_flag(F_present)
                                remove_from_list(self.scheduled_req, str(x.get('name')))

                # Processing the requirement after having seting the flags
                if self.pre_process_flags(str(x.get('name'))) :
                    REFRESH = True

                if str(x.get('name'))in tmp_keys :
                    LOG.debug('Del %s, processed' % x.get('name'))
                    del tmp_keys[tmp_keys.index(str(x.get('name')))]
            else :
                # if not new requirement or
                # has not changed
                self.store.get(str(x.get('name'))).reset_all_flags()
                LOG.debug('No change for %s' % x.get('name'))
                self.store.get(str(x.get('name'))).set_flag(F_present)
                if str(x.get('name')) in tmp_keys :
                    LOG.debug('Del %s, processed' % x.get('name'))
                    del tmp_keys[tmp_keys.index(str(x.get('name')))]

        # All remaining keys are obsolete requirements
        # thus needing to be removed
        LOG.debug('%s keys left unprocessed' % str(tmp_keys))
        for key in tmp_keys :
            self.store[key].reset_all_flags()
            if self.pre_process_flags(key) :
                REFRESH = True

        return REFRESH

    def check_link_status(self,from_R,to_R) :
        """
            @API
            check that the link
            from_R -> to_R is still up
            return False if it is up
            return True if it is down
        """
        try :
            node1 = self.network.topo.get_node(from_R)
            node2 = self.network.topo.get_node(to_R)
            if node1 and node2 :
                intfName, bw = self.get_intf_by_router(node1,node2)

                if intfName :
                    index = self.intf_index.get(intfName)
                    if not index :
                        walkcmd = SNMPWALK % (node1.addr.split('/')[0], ' ifDescr')
                        descr = self.network.topo.controller.cmd_process(walkcmd)
                        LOG.debug('\n'+descr+'\n')

                        lines = descr.split('\n')
                        index = -1
                        for line in lines :
                            sp_line = line.split()
                            if sp_line and str(sp_line[-1]) == str(intfName) :
                                index = int(sp_line[0].split('.')[-1])
                        LOG.debug('index for '+str(intfName)+' is '+str(index))
                        if index != -1 :
                            self.intf_index[intfName] = index

                    if index != -1:
                        ifOperStatus = self.get_link_status(index,node1.addr.split('/')[0])
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
            @API
            check that the bandwidth for the link
            from_R -> to_R does not exceed bw_perc
            return False if bw does not exceed bw_perc
            return True if bw exceeds bw_perc
        """
        try :
            node1 = self.network.topo.get_node(from_R)
            node2 = self.network.topo.get_node(to_R)
            if node1 and node2 :

                intfName, bw = self.get_intf_by_router(node1,node2)

                if intfName :
                    index = self.intf_index.get(intfName)
                    if not index :
                        walkcmd = SNMPWALK % (node1.addr.split('/')[0], ' ifDescr')
                        descr = self.network.topo.controller.cmd_process(walkcmd)
                        LOG.debug('\n'+descr+'\n')

                        lines = descr.split('\n')
                        index = -1
                        for line in lines :
                            sp_line = line.split()
                            if sp_line and str(sp_line[-1]) == str(intfName) :
                                index = int(sp_line[0].split('.')[-1])
                        LOG.debug('index for '+str(intfName)+' is '+str(index))
                        if index != -1:
                            self.intf_index[intfName] = index

                    if index != -1:
                        upTime1, ifOutOctets1 =  self.get_intf_stats(index, node1.addr.split('/')[0])
                        time1 = time.time()
                        if upTime1 and ifOutOctets1 :
                            time.sleep(20)
                            upTime2, ifOutOctets2 =  self.get_intf_stats(index,node1.addr.split('/')[0])
                            if upTime2 and ifOutOctets2 :
                                delta_t = time.time() - time1
                                LOG.debug('delta_t : '+ str(delta_t))
                                Dtime = self.diff_time(upTime1,upTime2)
                                LOG.debug('sys time diff :'+str(Dtime) )
                                if Dtime :
                                    band = self.bandwidth(ifOutOctets1,ifOutOctets2,bw, Dtime)
                                    if band :
                                        LOG.info('bandwidth : '+ str(band))

                                        if band > bw_perc :
                                            return True
            return False
        except Exception as e :
            LOG.critical('Error : '+ str(e))
            return False

    def check_single_requirement(self, key) :
        """
            @API
            check that the path taken by requirement
            with key is correct
        """
        try:
            Req = copy.copy(self.store[key].req)
            LOG.debug(str(Req))
            # Get Source and Dest
            src = Req[0]
            dest = self.store[key].dest

            # get label stack
            stack = self.label_stack[key]

            global_traceroute = []
            for stk_ip in stack :
                for tr_ip in self.check_traceroute(src, stk_ip) :
                    node = self.ip_name_mapping[tr_ip]
                    if node not in global_traceroute :
                        global_traceroute.append(node)
                # update src of traceroute

                src = self.ip_name_mapping[stk_ip]
            if stack :
                src = self.ip_name_mapping[stack[-1]]
            lo_dest =self.network.topo.get_node(dest).loopback()
            for tr_ip in self.check_traceroute(src, lo_dest) :
                node = self.ip_name_mapping[tr_ip]
                if node not in global_traceroute :
                    global_traceroute.append(node)


            LOG.debug('global_traceroute: %s ' % str(global_traceroute))

            Req.append(dest)

            if self.is_path_eq(Req[1:], global_traceroute) :
                return True

            return False
        except Exception as e:
            LOG.critical('Error '+str(e))
            return False


    # -----------------------------------------------------
    #             CLI  callback functions
    # -----------------------------------------------------
    def _print_dag_for(self, line) :
        """
            @callback
            Print the DAG of all path requirement
            for the given destination
            usage: print_dag_for <destination hosts>
        """
        try :
            if self.network.topo.get_node(line) :
                runOS('cp /home/sr6/.Xauthority /root/')
                self.plot_dag(line)
            else:
                LOG.error('%s is not known' % line)

        except Exception as e :
            LOG.critical("Error : "+str(e))


    def _ip(self, line):
        """
            @callback
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

    def _link(self,line) :
        """
            @callback
            Bring link(s) between two nodes up or down.
            Usage: link node1 node2 [up/down]
        """
        if self.running :
            LOG.info('link %s' % line)
            args = line.split()
            if len(args) != 3:
                LOG.error('invalid number of args: ping6 R1 R2 [up/down] ')
            elif self.network.topo.get_node(args[0]) and self.network.topo.get_node(args[1]) :
                n1 = args[0]
                n2 = args[1]
                if args[2] == 'up' :
                    for edge in self.network.topo.edges :
                        if edge.equal(n1,n2) :
                            edge.restart()
                elif args[2] == 'down' :
                    for edge in self.network.topo.edges :
                        if edge.equal(n1,n2) :
                            edge.shutdown()
                else:
                    LOG.error('invalid number of args: ping6 R1 R2 [up/down] ')

            else :
                LOG.error('Nodes do not exists')
        else :
            LOG.error('Netwok must be running')

    def _ssh_router(self, line) :
        """
            @callback
            Start a ssh session with the router <router>
        """
        if self.running :
            args = line
            if len(line.split()) != 1:
                LOG.error('invalid number of args: ssh_router <router> ')
            elif self.network.topo.get_node(args) :
                r = self.network.topo.get_node(args)
                c = self.network.topo.controller
                if isinstance(r,Router):
                    c.cmd_os('ssh -6 %s' % r.addr.split('/')[0])
                else :
                    LOG.error('Node is not a Quagga router')
            else :
                LOG.error('Nodes do not exists')
        else :
            LOG.error('Netwok must be running')

    def _connect_zebra(self, line) :
        """
            @callback
            Open Zebra CLI for specified router

        """
        if self.running :
            args = line
            if len(line.split()) != 1:
                LOG.error('invalid number of args: connect_zebra <router> ')
            elif self.network.topo.get_node(args) :
                r = self.network.topo.get_node(args)
                c = self.network.topo.controller
                if isinstance(r,Router):
                    c.cmd_os('telnet %s %s' % (r.addr.split('/')[0],ZEBRAPORT))
                else :
                    LOG.error('Node is not a Quagga router')
            else :
                LOG.error('Nodes do not exists')
        else :
            LOG.error('Netwok must be running')

    def _connect_ospf6d(self, line) :
        """
            @callback
            Open Zebra CLI for specified router

        """
        if self.running :
            args = line
            if len(line.split()) != 1:
                LOG.error('invalid number of args: connect_ospf6d <router> ')
            elif self.network.topo.get_node(args) :
                r = self.network.topo.get_node(args)
                c = self.network.topo.controller
                if isinstance(r,Router):
                    c.cmd_os('telnet %s %s' % (r.addr.split('/')[0],OSPF6dPORT))
                else :
                    LOG.error('Node is not a Quagga router')

            else :
                LOG.error('Nodes do not exists')
        else :
            LOG.error('Netwok must be running')


    def _xterm(self, line) :
        """
            @callback
            usage: xterm [ROUTER]
            open an xterm terminal on the [ROUTER]
        """
        if self.running :
            args = line
            if len(line.split()) != 1:
                LOG.error('invalid number of args: xterm <router> ')
            elif self.network.topo.get_node(args) :
                runOS('cp /home/sr6/.Xauthority /root/')
                XTERM_th = threading.Thread(target=self.xterm_th, args=(args,))
                XTERM_th.start()
                LOG.info('Xterm started on %s ...' % args)


            else :
                LOG.error('Nodes do not exists')
        else :
            LOG.error('Netwok must be running')

    def _ping6(self, line) :
        """
            @callback
            * INPUT :  Two routers name
            * Ouput : ping between the two routers
        """
        if self.running :
            LOG.info('ping6 %s' % line)
            args = line.split()
            if len(args) != 2:
                LOG.error('invalid number of args: ping6 R1 R2 ')
            elif self.network.topo.get_node(args[0]) and self.network.topo.get_node(args[1]) :
                n1 = self.network.topo.get_node(args[0])
                n2 = self.network.topo.get_node(args[1])
                lo1 = n1.addr.split('/')[0]
                lo2 = n2.addr.split('/')[0]

                n1.cmd_os(PING6 % (lo1,lo2, 3))

            else :
                LOG.error('Nodes do not exists')
        else :
            LOG.error('Netwok must be running')

    def _traceroute6(self, line ) :
        """
            @callback
            * INPUT :  Two routers name
            * Ouput : traceroute between the two routers
        """
        if self.running :
            LOG.info('traceroute6 %s' % line)
            args = line.split()
            if len(args) != 2:
                LOG.error('invalid number of args: traceroute6 R1 R2 ')
            elif self.network.topo.get_node(args[0]) and self.network.topo.get_node(args[1]) :
                n1 = self.network.topo.get_node(args[0])
                n2 = self.network.topo.get_node(args[1])
                lo1 = n1.addr.split('/')[0]
                lo2 = n2.addr.split('/')[0]

                n1.cmd_os(TRACEROUTE6 % (lo1, lo2))
            else :
                LOG.error('Nodes do not exists')
        else :
            LOG.error('Netwok must be running')


    def _show_ip_route(self, line) :
        """
            @callback
            * INPUT :  A router name
            * Ouput : ip -6 ro of the router
        """
        if self.running :
            args = line.split()
            if len(args) != 1:
                LOG.error('invalid number of args: show_ip_route R1')
            elif self.network.topo.get_node(args[0]) :
                n1 = self.network.topo.get_node(args[0])
                c = self.network.topo.controller
                # n1.cmd_os(IPROUTE)
                c.cmd_os(SSH6CMD % (n1.loopback(), IPROUTE))

            else :
                LOG.error('Nodes do not exists')
        else :
            LOG.error('Netwok must be running')


    def _set_time_granularity(self, line) :
        """
            @callback
            * INPUT :  a integer value of time in sec for
              the period at which the application will check
              the scheduled requirements
        """
        try :
            if line :
                time = int(line)
                if time :
                    self.SchedulePeriod = time
            else :
                LOG.error('Need a time value as input')
        except Exception as e :
            LOG.critical('Error :' + str(e))

    def _show_time_granularity(self, line) :
        """
            @callback
            * display the current time granularity
        """
        LOG.info('Time granularity : '+ str(self.SchedulePeriod))


    def _halt_requirement(self, line) :
        """
            @callback
            * INPUT :  key of the requirement
            * if the requirement is running, it will be stopped
        """

        if line :
            try :
                LOG.info('halt requirement %s' % line)
                if line in self.store :
                    self.key_to_remove = line
                    self.transaction(self.halt_requirement)
                else :
                    LOG.error('no requirements stored for key '+ str(line))
            except Exception as e :
                LOG.critical("Error : " + str(e))

        else :
            LOG.error('Need the key of a requirement as input')
            LOG.info('Do <show_requirements> to have info about the requirments')

    def _show_requirements(self,line) :
        """
            @callback
            * display the stored requirements
        """
        if self.isrequirement :
            self._dump_requirement_log()


        else :
            LOG.error('There is no requirements ')

    def _dump_requirement_log(self) :
        """
            show requirement in a LOG.info()
        """
        colors = {UP : 'green', DOWN : 'red', SCHED : 'magenta',
                  TIME : 'yellow', BAND : 'blue', BACK : 'cyan'}
        Str = '\n----------------------------------\n'
        Str +=  '   Stored requirements :\n'
        for key, value in self.store.iteritems() :
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
        Str +=  '  Links down : %s\n' % str(self.link_down)
        Str += '----------------------------------\n'
        LOG.info(Str)

    def _config(self, line ) :
        """
            @callback
            * Launch the confD CLI
        """
        comdline =[ 'make', 'cli']
        subprocess.call(comdline)
        LOG.info('confD CLI started...')

    # *************************
    # network & controller command
    # *************************
    def _start_network(self, line) :
        """
            @callback
            * it will start the network and set the state on running.
            * Require to have some available configuration
        """
        if self.process_network_config() :
            LOG.info('Start network')
            self.start_network()

    def _stop_network(self,line) :
        """
            @callback
            * it will stop the network and set the state on not running (running=False).
            * Require to have the network already running
        """
        if self.running :
            self.remove_network()
            LOG.warning('stopping the network...')
            LOG.info('Clearing all stored requirements')
            for key in self.store.keys():
                del self.store[key]
            self.running = False
            if self.verbose :
                self.set_prompt()
        else :
            LOG.error('The network is not running...')

    def _apply_new_requirement(self, line) :
        """
            @callback
            * add the new requirements to the controller
            * Require running controller
            * should have new requirements
        """
        if self.running :
            if self.setup_requirement() :
                LOG.info('Apply new requirement')
                self.transaction(self.process_requirement)
                if self.checker :
                    self.check_requirement()

                # if self.process_requirement() :
                #     self.manager.commit_change()
                #     if self.checker :
                #         self.check_requirement()

        else :
            LOG.error('The controller must be running')

    def _enable_auto_schedule(self, line ):
        """
            @callback
            * periodically checks the scheduled requirements, and start if
              their starting deadline has been reached and stop them
              if their ending deadline has been reached
        """

        if self.running :
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
            @callback
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
            @callback
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
        NewREqState = str(new_req)
        StoredReqState = str(self.isrequirement)

        colors = {'False' : 'red', 'True' : 'green'}

        netstate = colored(netstate, colors.get(netstate), attrs=['bold'])
        NewConfigState = colored(NewConfigState, colors.get(NewConfigState), attrs=['bold'])
        StoredConfigState = colored(StoredConfigState, colors.get(StoredConfigState), attrs=['bold'])


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
        print '* new requirements:      | ' +  NewREqState
        print '* stored requirements:   | ' +  StoredReqState
        print '+++++++++++++++++++++++++++' + '+++++++'

    def _quit(self, args):
        """
            @callback
            * Quits the program.
            * /!\ : require to have NO RUNNING  network
            * /!\ : require to have NO RUNNING  controller

        """
        if self.running :
            LOG.error('The network is still running...')
        else :
            self._halt_auto_schedule('Forcing Halt')
            LOG.info("Quitting...")
            raise SystemExit

    # ---------------------------------------------------
    #               lib functions
    # ---------------------------------------------------
    def shutdown(self) :
        """
            shutdown the daemon thread handler
            of ConfD Agent commits
        """
        LOG.info('Closing connection')


        self.network_server.shutdown()
        self.network_server.server_close()

        self.controller_server.shutdown()
        self.controller_server.server_close()



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



    def add_requirement(self) :
        """
            Add/Remove new requirements that the controller will apply
            to the network
            Check the stored requirements flags and apply operation
            accordingly
        """
        try :
            REFRESH = False
            for key in self.store.keys() :
                if self.process_flags(key) :
                    REFRESH = True
            if REFRESH :
                self.manager.commit_change()
                if self.checker :
                    self.check_requirement()
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

            if REFRESH :
                self.manager.commit_change()
                if self.checker :
                    self.check_requirement()
        except Exception as e :
            LOG.critical("Error : "+str(e))

    def process_flags(self, key) :
        """
            process the requirement with name=key,
            according to its flags
            return True if the fibbing controller needs
            to refresh the topology
        """
        try :
            REFRESH = False
            if self.store[key].flags[F_OK] :
                return False
            if not self.store[key].flags[F_present] :
                if self.store[key].status == UP :
                    self.store[key].set_flag(F_stop)
                elif self.store[key].status == DOWN :
                    self.store[key].set_flag(F_delete)
                elif self.store[key].status == SCHED :
                    if self.store[key].runningstatus == UP :
                        self.store[key].set_flag(F_stop)
                    elif self.store[key].runningstatus == DOWN :
                        self.store[key].set_flag(F_delete)

            if self.store[key].flags[F_stop] :
                LOG.debug('Removing requirement %s' % key)
                self.manager.remove_requirement(key)
                if self.store[key].status == SCHED :
                    remove_from_list(self.scheduled_req,key)
                REFRESH = True
                del self.store[key]
                del self.label_stack[key]
                return REFRESH

            if self.store[key].flags[F_halt] :
                LOG.debug('Halting requirement %s' % key)
                REQ = self.store[key]
                self.manager.remove_requirement(key)
                del self.label_stack[key]
                REFRESH = True
                if self.store[key].status == SCHED :
                    if self.store[key].runningstatus ==UP :
                        self.store[key].set_runningstatus(DOWN)

            if self.store[key].flags[F_delete] :
                value =self.store[key]
                LOG.debug('deleting : %s ' % str(key))
                if self.store[key].status == SCHED :
                    remove_from_list(self.scheduled_req,key)

                del self.store[key]
                if self.label_stack.get(key) :
                    del self.label_stack[key]
                return REFRESH

            if self.store[key].flags[F_replace] :
                newREQ = self.store[key].newRequirement
                if self.store[key].status == SCHED and newREQ.status != SCHED:
                    remove_from_list(self.scheduled_req,key)
                self.store[key] = newREQ
                if self.store[key].status == SCHED :
                    self.scheduled_req.append(key)
                LOG.debug('replacing %s : %s '% (key, str(self.store[key].req)))

            if self.store[key].flags[F_Add] :
                REQ = self.store[key]
                rs = REQ.router
                ds = REQ.dest
                R = REQ.req

                stack = self.manager.add_requirement(key,ds, R )
                REFRESH = True
                if self.store[key].status == SCHED :
                    if self.store[key].runningstatus == DOWN :
                        self.store[key].set_runningstatus(UP)
                LOG.debug('Adding %s : %s' % (key, str(self.store[key].req)))
                self.label_stack[key] = stack

            # if key still in cache
            if self.store.get(key) :
                self.store.get(key).reset_all_flags()

            return REFRESH
        except Exception as e :
            LOG.critical('Error :' + str(e))
            return False




    def transaction(self,update_flag_fct) :
        """
            update_flag_fct:  void function that will update some flags and
                            call pre_process_flags for the requirement
                            must return true if need to True if need to
                            commit_change
        """
        self.lock.acquire()
        # make sure the added_set and remove_set are empty before
        # calling update_flag_fct
        self.remove_set = []
        self.added_set = []
        LOG.debug('Begin transaction')
        if update_flag_fct() :
            SuccessKeys = self.manager.commit_change()

            tmp_added_set = copy.copy(self.added_set)
            self.added_set = []
            for key in tmp_added_set :
                status = T_ABORT
                if key in SuccessKeys :
                    status = T_SUCCESS
                else :
                    status = T_ABORT

                self.post_process_flags(key,status)

            tmp_remove_set = copy.copy(self.remove_set)
            self.remove_set = []
            for key in tmp_remove_set :
                status = None
                if key in SuccessKeys :
                    status = T_SUCCESS
                else :
                    status = T_ABORT

                self.post_process_flags(key,status)


            # if replace was successful may be that need to add some requirements

            REFRESH = False
            for key in self.replacing_set:
                LOG.debug('pre_process_flags %s' % key)
                if self.pre_process_flags(key) :
                    REFRESH = True

            self.replacing_set = []
            if REFRESH :
                SuccessKeys = self.manager.commit_change()
                tmp_added_set = copy.copy(self.added_set)
                self.added_set = []
                for key in tmp_added_set :
                    status = None
                    if key in SuccessKeys :
                        status = T_SUCCESS
                    else :
                        status = T_ABORT

                    self.post_process_flags(key,status)

        else :
            tmp_added_set = copy.copy(self.added_set)
            self.added_set = []
            for key in tmp_added_set :
                status = T_ABORT
                self.post_process_flags(key,status)
        self.remove_set = []
        self.added_set = []
        self.lock.release()
        LOG.debug('End transaction')


    def halt_requirement(self) :
        """
            setup flags for halting/removing the requirement with key=self.key_to_remove
        """
        line = self.key_to_remove
        self.store[line].reset_all_flags()
        self.key_to_remove = None
        if self.store[line].status == UP :
            self.store[line].set_flag(F_halt)
            self.store[line].set_flag(F_delete)
            self.store[line].set_flag(F_present)


        elif self.store[line].status == SCHED and\
        self.store[line].runningstatus == UP :
            self.store[line].set_flag(F_halt)
            self.store[line].set_flag(F_present)

        return self.pre_process_flags(str(line))

    def remove_network(self) :
        """
            stop and remove the network
        """
        self.stop_quagga()
        self.remove_ns()

    def build_bootstrap(self) :
        """
            bootstrap the network
        """
        self.network.dump_commands(lambda x: runOS('%s\n' % x), noroute=True)


    def start_quagga(self) :
        """
            start the zebra and ospf6d daemon for each router
        """
        for n in self.network.topo.nodes:
            LOG.info('Starting node %s' % n.name)
            if isinstance(n,Router) :
                n.build_quagga_router()
                LOG.debug('Building quagga configfiles')
                n.quagga_router.build_zebra()
                n.quagga_router.build_ospf6d()
                LOG.debug('Starting Zebra and Ospf6d')
                n.quagga_router.start_zebra()
                n.quagga_router.start_ospf6d()
                n.quagga_router.start_snmp()
                n.quagga_router.start_sshd()
                n.quagga_router.build_confd_agent()
            elif type(n) is Host :
                n.setup_default_route()


    def stop_quagga(self) :
        """
            stop zebra and ospf6d for each router
        """
        for n in self.network.topo.nodes:
            LOG.info('Stoping node %s' % n.name)
            if isinstance(n,Router) :
                n.quagga_router.kill_ospf6d()
                n.quagga_router.kill_zebra()
                n.quagga_router.kill_snmp()
                n.quagga_router.kill_sshd()
                n.quagga_router.kill_confd_agent()

    def remove_ns(self) :
        """
            remove the name space
        """
        for n in self.network.topo.nodes:
            cmd = RMNS % n.name
            runOS(cmd)

    def build_ip_mapping(self) :
        """
            Build the ip/RouterName mapping
        """
        for node in self.network.topo.nodes:
            self.ip_name_mapping[node.loopback()] = node.name
            for port in node.intfs_addr :
                ip = node.intfs_addr[port].split('/')[0]
                self.ip_name_mapping[ip] = node.name

    def start_network(self) :
        """
            Start the IPv6 network
        """
        # Build Nanonet network
        self.network = Nanonet(IPv6Topo(self.data))

        self.network.start()
        self.build_bootstrap()

        self.start_quagga()
        self.build_ip_mapping()

        self.manager = SRSouthboundManager(self.network)
        # set state into running
        self.running = True

        if self.verbose :
            self.set_prompt()


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



    def xterm_th(self, router) :

        runOS('xterm -e ip netns exec %s bash' % router)


    def get_time(self) :
        """
            return the time value
            NB: for simulation override this function to
                fast forward in time
        """
        return datetime.datetime.now()

    def update_schedule_requirement(self) :
        """
            scan through the store to check if the
            scheduled requirements have reach their end or start_h
            deadline
        """

        ct = self.get_time()
        REFRESH = False

        for key in self.scheduled_req :
            self.store[key].reset_all_flags()
            self.store[key].set_flag(F_present)
            if self.store[key].status == SCHED :
                # if self.store[key].scheduleType == TIME  :
                start_h = self.store[key].start_hour
                end_h   = self.store[key].end_hour
                weekdays = self.store[key].weekdays

                if ct.date().weekday() in weekdays :
                    if (ct.time().hour, ct.time().minute) > start_h and \
                        (ct.time().hour, ct.time().minute) < end_h  :
                        if self.store[key].runningstatus == DOWN :
                            if self.store[key].scheduleType == BAND :
                                from_R = self.store[key].from_R
                                to_R  = self.store[key].to_R
                                bw_perc = self.store[key].bw_perc

                                if self.check_bw_status(from_R,to_R,bw_perc) :
                                    self.store[key].set_flag(F_Add)


                                else :
                                    self.store[key].set_flag(F_OK)

                            elif self.store[key].scheduleType == BACK :
                                from_R = self.store[key].from_R
                                to_R  = self.store[key].to_R

                                if self.check_link_status(from_R,to_R)  :
                                    self.store[key].set_flag(F_Add)
                                    self.link_down.append((from_R, to_R))

                                else :
                                    self.store[key].set_flag(F_OK)
                            else :
                                self.store[key].set_flag(F_Add)


                        elif self.store[key].runningstatus == UP:
                            if self.store[key].scheduleType == BACK :
                                from_R = self.store[key].from_R
                                to_R  = self.store[key].to_R

                                if not self.check_link_status(from_R,to_R)  :
                                    self.store[key].set_flag(F_halt)
                                    # if link is up
                                    index = self.link_down.index((from_R, to_R))
                                    del self.link_down[index]

                                else :
                                    self.store[key].set_flag(F_OK)

                    elif self.store[key].runningstatus == UP and \
                        (ct.time().hour, ct.time().minute) > end_h :
                        self.store[key].set_flag(F_halt)

                    else :
                        self.store[key].set_flag(F_OK)
                else :
                    self.store[key].set_flag(F_OK)

            else :
                self.store[key].set_flag(F_OK)


            if self.pre_process_flags(key) :
                REFRESH = True


        if self.update_link_requirement() :
            REFRESH = True
        return REFRESH

    def update_link_requirement(self) :
        """
            If a requirement path has a known link
            down the requirement will be halted,
            if requirement was halted but has no
            known link down will be added
        """
        REFRESH = False
        for key in self.store.keys() :
            if self.store[key].status == UP and\
            self.has_link_down(self.store[key].req) :
                self.store[key].set_flag(F_present)
                self.store[key].set_flag(F_halt)
                if self.pre_process_flags(key) :
                    REFRESH = True

            if self.store[key].status == DOWN and\
            not self.has_link_down(self.store[key].req) :
                self.store[key].set_flag(F_present)
                self.store[key].set_flag(F_Add)
                if self.pre_process_flags(key) :
                    REFRESH = True
        return REFRESH

    def has_link_down(self, path) :
        """
            return whether the path contains
            a knonw down link
        """
        for s, d in zip(path[:-1], path[1:]) :
            if (s,d) in self.link_down :
                return True
        return False

    def schedule_requirement(self) :
        """
            should periodically (SchedulePeriod) launch the update on
            scheduled requirements
        """
        LOG.info('Starting the auto schedule')
        while not self.timerEvent.is_set():
            if self.running :
                self.transaction(self.update_schedule_requirement)
                if self.checker :
                    self.check_requirement()


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


        if self.auto_schedule :
            text = colored('Yes', 'green', attrs=['bold'])
            prompt = prompt + ', A:'+text
        else :
            text = colored('No', 'red', attrs=['bold'])
            prompt = prompt + ', A:'+text

        prompt = prompt + ')'
        prompt = prompt + self.end_prompt
        self.prompt = prompt





    def get_intf_by_router(self,from_R, to_R) :
        """
            return the intf name of router from_R
            that is connected to router to_R
        """
        assert isinstance(from_R, Router), 'from_R must be a router'
        assert isinstance(to_R, Router), 'to_R must be a router'

        edges = self.network.topo.get_edges(from_R, to_R)
        for intfname in from_R.intfs_name.keys() :
            for e in edges :
                if e.node1 == from_R :
                    return '%s-%d' % (from_R.name, e.port1), e.bw * 1000
                elif e.node2 == from_R :
                    return '%s-%d' % (from_R.name, e.port2), e.bw * 1000
        return False, False




    def get_intf_stats(self, index,ip) :
        """
            get via SNMP the interface stats
        """
        try :
            getcmd = SNMPBULKGET % (ip, ' ifOutOctet 1.3.6.1.2.1.1.1.0')
            intfstats = self.network.topo.controller.cmd_process(getcmd)
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




    def get_link_status(self, index, ip) :
        """
            get via SNMP the interface stats
        """
        try :
            getcmd = SNMPWALK % (ip," ifOperStatus.%d" % index )
            intfstats = self.network.topo.controller.cmd_process(getcmd)
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


    def check_traceroute(self, src, destIP):
        """
            run a traceroute and check that the output
            matches the path
        """

        n1 = self.network.topo.get_node(src)
        lo1 = n1.addr.split('/')[0]


        tr_ouptut = n1.cmd_process(TRACEROUTE6 % (lo1, destIP))
        LOG.debug('traceroute6 output: %s' % str(tr_ouptut))
        out = self.parse_traceroute(tr_ouptut)
        LOG.debug('parsed output: %s' % str(out))
        return out


    def parse_traceroute(self,traceroute):
        """
        take a traceroute as input and parse it to just retrun a list of the IP's in the right order.
        """
        lines=traceroute.split('\n')

        path=[]
        # ignoring first line
        for line in lines[1:] :
            for string in line.split() :
                try :
                    if ipaddress.ip_address(unicode(string)) :
                        path.append(string)
                except ipaddress.AddressValueError :
                    continue
                except ValueError :
                    continue
        return path

    def is_path_eq(self, p1, p2) :
        """
            return if p1 == p2
        """
        if len(p1) !=  len(p2) :
            return False

        for i in range(len(p1)) :
            if str(p1[i]) != str(p2[i]) :
                return False
        return True



    def check_requirement(self) :
        """
            Check that the path taken all
            running requirements is indeed
            correct
        """
        try:
            if self.isrequirement :
                for key in self.store.keys() :
                    if self.store[key].status == UP or \
                    (self.store[key].status == SCHED and \
                    self.store[key].runningstatus == UP) :
                        if not self.check_single_requirement(key) :
                            LOG.error('requirement '+str(key)+ ' does not seem to work')
                        else :
                            LOG.info('Requirement '+str(key)+' seems to be correctly working')

        except Exception as e:
            LOG.critical('Error :'+str(e))

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
            for key in self.store :
                if self.store[key].dest == dest :
                    for node in self.store[key].req :
                        Nodes.add(node)

                    for s, d in zip(self.store[key].req[:-1],self.store[key].req[1:] ) :
                        if (s, d) in Edges :
                            Bottleneck.append((s, d))
                        Edges.add((s, d))



            LOG.info('DAG composed of %s ' % str(Edges))
            LOG.info('Bottleneck edges found %s ' % str(Bottleneck))
            DAG = nx.Graph()
            LOG.debug('Building DAG with nodes %s' % str(Nodes))
            LOG.debug('Building DAG with edges %s' % str(Edges))
            DAG.add_nodes_from(list(Nodes))
            DAG.add_edges_from(list(Edges))

            nx.draw(DAG, node_color='c', edge_color='k', with_labels=True)
            plt.show()
        except Exception as e :
            LOG.critical('ERROR :'+str(e))

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
    def __init__(self, verbose=True, checker=True) :
        NetworkManagerCore.__init__(self, checker)
        self.verbose=verbose
        Cmd.__init__( self )
        self.do_info('info')
        self.base_prompt = "[NetworkManagerCLI]"
        self.end_prompt = "$ "
        if self.verbose :
            self.set_prompt()
        else :
            self.prompt = "[NetworkManagerCLI]$ "

    def start(self):
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

    def do_link(self,line) :
        """
            Bring link(s) between two nodes up or down.
            Usage: link node1 node2 [up/down]
        """
        self._link(line)

    def do_ssh_router(self, line) :
        """
            Start a ssh session with the router <router>
        """
        self._ssh_router(line)



    def do_connect_zebra(self, line) :
        """
            Open Zebra CLI for specified router

        """
        self._connect_zebra(line)

    def do_connect_ospf6d(self, line) :
        """
            Open Zebra CLI for specified router

        """
        self._connect_ospf6d(line)

    def do_terminal(self,line) :
        """
            Start a terminal bash
        """
        os.system('/bin/bash')

    def do_xterm(self, line) :
        """
            usage: xterm [ROUTER]
            open an xterm terminal on the [ROUTER]
        """
        self._xterm(line)

    def do_ping6(self, line) :
        """
            * INPUT :  Two routers name
            * Ouput : ping between the two routers
        """
        self._ping6(line)

    def do_traceroute6(self, line ) :
        """
            * INPUT :  Two routers name
            * Ouput : traceroute between the two routers
        """
        self._traceroute6(line)


    def do_show_ip_route(self, line) :
        """
            * INPUT :  A router name
            * Ouput : ip -6 ro of the router
        """
        self._show_ip_route(line)


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
        self._show_time_granularity(line)

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


    def do_config(self, line ) :
        """
            * Launch the confD CLI
        """
        self._config(line)

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

    def do_apply_new_requirement(self, line) :
        """
            * add the new requirements to the controller
            * Require running controller
            * should have new requirements
        """
        self._apply_new_requirement(line)


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
        print '* type <config>  to start'
        print '  configuration CLI'
        print '* see in doc/ directory to have more '
        print '  information about the application.'
        print '****************************************'

    def do_show_status(self,line) :
        """
            * show the status of the network
        """
        self._show_status(line)

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
