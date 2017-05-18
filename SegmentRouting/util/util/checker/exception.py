# exceotion file
import json
import argparse
from util import LOG, SCHED,TIME, BAND, BACK
import ipaddress

def check_network(network, Error) :
    """
        return True if and Error has been detected
        otherwise return Error
    """

    controller = network.get('controller')
    if not controller :
        LOG.error('A controller must be specified')
        Error = True
    if not network.get('destinations') :
        LOG.warning('Destinations should be configured to specify requirements')

    ips = {}
    routerids = {}
    routerospf = []
    hosts = []
    for router in network.get('routers') :
        if router.get('ospf6').get('enable') and\
        not router.get('ospf6').get('router-id') :
            LOG.error('If ospf is enable router %s must have a router-id ' % router.get('name'))
            Error = True

        if not router.get('ospf6').get('enable') :
            hosts.append(router.get('name'))

        if router.get('ospf6').get('enable') and\
        routerids.get(router.get('ospf6').get('router-id') ) :
            LOG.error('routerid should be unique %s' % router.get('ospf6').get('router-id'))
            LOG.info('already found here %s ' % routerids.get(router.get('ospf6').get('router-id') ))
            Error = True
        else :
            routerids[router.get('ospf6').get('router-id')] = router.get('name')
            routerospf.append(router.get('name'))

        if not router.get('loopback-addr') :
            LOG.error('router %s have a loopback-addr' % router.get('name'))
            Error = True
        else :
            if ips.get(router.get('loopback-addr')) :
                LOG.error('loopback-addr must be unique %s' % router.get('loopback-addr'))
                LOG.info('already found here %s ' % ips.get(router.get('loopback-addr')))
                Error = True
            else:
                ips[router.get('loopback-addr')] = router.get('name')


    ospfconfig = {}
    host_link = {}
    ospf_link = []
    link_name_map = {}
    for link in network.get('link') :
        link_name_map[link.get('name')] = link

    for link in network.get('ospf-links') :
        l = link_name_map[link.get('name')]
        ospf_link.append(link.get('name'))

        for intf in [link.get('src'), link.get('dest')] :
            area = intf.get('ospf').get('area')
            if not ospfconfig  or ospfconfig.get(area):

                ospfconfig[area] = {
                    'area' :intf.get('ospf').get('area'),
                    'hello-interval' :intf.get('ospf').get('hello-interval'),
                    'dead-interval' : intf.get('ospf').get('dead-interval'),
                }
            else :
                if ospfconfig.get(area).get('hello-interval') != intf.get('ospf').get('hello-interval') :
                    LOG.error('hello-interval should be the same for the same area %s' % area)
                    Error = True
                if ospfconfig.get(area).get('hello-interval') != intf.get('ospf').get('hello-interval') :
                    LOG.error('hello-interval should be the same for the same area %s' % area)
                    Error = True
            if l.get('src').get('name') not in routerospf :
                LOG.error('To enable ospf on a link both router must have ospf enable %s' % l.get('src').get('name'))
                Error = True
            if l.get('dest').get('name') not in routerospf :
                LOG.error('To enable ospf on a link both router must have ospf enable %s' % l.get('dest').get('name'))
                Error = True




    for link in network.get('link') :
        src = link.get('src')
        dest =  link.get('dest')
        if not src.get('name') :
            LOG.error('Link must have a src ')
            Error = True
            continue
        if not dest.get('name'):
            LOG.error('Link must have a dest ')
            Error = True
            continue
        if not src.get('ip') :
            LOG.error('Link must have an ip address')
            Error = True
            continue
        if not dest.get('ip'):
            LOG.error('Link must have an ip address')
            Error = True
            continue


        if ips.get(src.get('ip')) :
            LOG.error('ip address should be different %s than loopback-addr' % src.get('ip'))
            LOG.info('already found %s' % ips.get(src.get('ip')))
            Error = True

        if ips.get(dest.get('ip')) :
            LOG.error('ip address should be different %s' % dest.get('ip'))
            LOG.info('already found %s' % ips.get(dest.get('ip')))
            Error = True

        if link.get('name') not in ospf_link :
            # checking static link
            if src.get('name') in hosts and src.get('name') in host_link :
                LOG.error('A router without ospf can only have one static link')
                Error = True

            else:
                if src.get('name') in hosts and dest.get('name') in hosts :
                    LOG.error('Cannot have a static link between two router without ospf')
                    Error = True
                else:
                    host_link[src.get('name')] = dest.get('name')

            if dest.get('name') in hosts and dest.get('name') in host_link :
                LOG.error('A router without ospf can only have one static link')
                Error = True
            else:
                if src.get('name') in hosts and dest.get('name') in hosts :
                    LOG.error('Cannot have a static link between two router without ospf')
                    Error = True
                else:
                    host_link[dest.get('name')] = src.get('name')


    return Error
def checkNetworkConfig(network) :
    """
        Check the config received from the ConfD agent,
        concerning the network
        Input : network is the dictionary that contains
                the network config
        return False if no Error was found,
        retrun True if at least one Error was found
    """
    Error = False
    Error = check_network(network,Error)
    return Error

# --------------------------------------------------------
def check_path(ospf_links,error,requirement):
    edge=[]
    for x in ospf_links:
        src  = x.get('src')
        dest = x.get('dest')
        edge.append((src.get('name'),dest.get('name')))
        edge.append((dest.get('name'),src.get('name')))

    for req in requirement:
        if '*' not in req.get('requirement') :
            for (s,d) in zip(req.get('requirement')[:-1],req.get('requirement')[1:]):
                if (s,d) not in edge:
                    error=True
                    LOG.error('Unvalid path')

    return error

def compare(start_hour,end_hour):
    start=start_hour.split(':')
    end=end_hour.split(':')
    if(int(start[0])>int(end[0])):
        return False
    if(int(start[1])>int(end[1])):
        return False
    return True


# --------------------------------------------------------
def checkRequirementConfig(network, requirement) :
    """
        Check the config received from the ConfD agent,
        concerning the requirement
        Input : network is the dictionary that contains
                the network config,
                requirement is the dictionary that contains
                the requirements config,
        return False if no Error was found,
        retrun True if at least one Error was found
    """

    Error = False
    # TODO : build function that check the config,
    # TODO : call checker function here

    conf = requirement['config']
    link =  conf["link"]

    for x in link :
        if x.get('requirement')[-1] == '*' :
            LOG.error('Path of requirement cannnot end by *')
            continue

        rs =  x.get('requirement')[-1]
        ds = str(x.get('dest'))

        IS_OK = False
        for lk in network.get('link') :
            src  = lk.get('src')
            dest = lk.get('dest')
            # check if dest is indeed connected to router
            # in the topology
            if (src.get('name') == ds and dest.get('name') == rs)\
            or (src.get('name') == rs and dest.get('name') == ds) :
                IS_OK = True
        if not IS_OK :
            LOG.error('Destination ' + ds + ' is not connected to '+rs)
            Error =True

        if str(x.get('status')) == SCHED:
            start_hour=x.get('scheduled').get('start-hour')
            end_hour=x.get('scheduled').get('end-hour')
            tmp=compare(start_hour,end_hour)
            if(tmp==False):
                Error=True
                LOG.error('start-hour must be smaller than end-hour')

        if str(x.get('status')) == SCHED and\
           (str(x.get('scheduled').get('type')) == BAND or\
           str(x.get('scheduled').get('type')) == BACK):
            if not x.get('scheduled').get('link').get('from') or \
                not x.get('scheduled').get('link').get('to') :
                Error = True
                LOG.error('router from and to of link bandwidth or backup  not set')

    Error = check_path(network.get('link'),Error,  link)
    return Error
