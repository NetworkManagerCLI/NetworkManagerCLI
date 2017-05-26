# exceotion file
import json
import argparse
from util import TOPOLOGY_CONFIG, REQUIREMENT_CONFIG
from util import LOG, SCHED,TIME, BAND, BACK
import ipaddress


def checkExist_controllerlink(controller_link, Error):
    try :
        links = controller_link.get('links')

        if not links :
            LOG.error('NO fibbing controller configured' )
            Error=True
            return Error
        for cont in links :
            if not cont.get('controller').get('ip') :
                LOG.error('NO fibbing controller ip configured' )
                Error=True
            if not cont.get('controller').get('name') :
                LOG.error('NO fibbing controller name configured' )
                Error=True

            if not cont.get('router').get('ip') :
                LOG.error('NO fibbing controller connected router configured' )
                Error=True
            if not cont.get('router').get('name') :
                LOG.error('NO fibbing controller connected router name configured' )
                Error=True


        return Error
    except KeyError :
        LOG.error('checkExist_controllerlink :'+'KeyError' )
        Error = True

    return Error

def check_ip(base_net, private_net, ip, Error) :
    ip_pfx =  str(ip.split('/')[0]) + '/8'
    ip_intf = ipaddress.ip_interface(unicode(ip_pfx))

    if private_net ==  str(ip_intf.network) :
        LOG.error('IP address has same prefix than private_net :'+str(ip))
        Error = True

    ip_pfx =  str(ip.split('/')[0]) + '/16'
    ip_intf = ipaddress.ip_interface(unicode(ip_pfx))
    if base_net == str(ip_intf.network) :
        LOG.error('IP address has same prefix than base_net :'+str(ip))
        Error= True
    return Error


def compare(start_hour,end_hour):
    start=start_hour.split(':')
    end=end_hour.split(':')
    if(int(start[0])>int(end[0])):
        return False
    if(int(start[1])>int(end[1])):
        return False
    return True

def check_network(config, Error):
    try :
        fibbing_ctrl = config.get('fibbing-controller')
        hosts_link  = config.get('hosts-link')
        links = config.get('links')
        main_controller = config.get('main-controller')
        ospf_links = config.get('ospf-links')
        routers = config.get('routers')

        routerid = []
        ospf_router= []
        for r in routers :
            if r.get('ospf').get('enable') :
                if r.get('ospf').get('router-id') in routerid :
                    LOG.error('Router id already used %s' % r.get('ospf').get('router-id') )
                    Error= True
                else :
                    routerid.append(r.get('ospf').get('router-id'))
            else :
                LOG.warning('For this framework all routers must have ospf enable')
            ospf_router.append(r.get('name'))

        link_key_map = {}
        for link in links :
            if not link.get('src').get('name') :
                LOG.error('A link must have a src router name' )
                Error= True
            if not link.get('src').get('ip') :
                LOG.error('A link must have a src router ip' )
                Error= True
            if not link.get('dest').get('name') :
                LOG.error('A link must have a dest router name' )
                Error= True
            if not link.get('dest').get('ip') :
                LOG.error('A link must have a dest router ip' )
                Error= True
            link_key_map[link.get('name')] = link

        ospf_config = {}
        for o_l in ospf_links :
            link = link_key_map.get(o_l.get('name'))
            if link.get('src').get('name') not in ospf_router or \
            link.get('dest').get('name') not in ospf_router:
                LOG.error('A link with ospf configured must have both src and dest with ospf enabled' )
                Error= True

            src_o_conf = o_l.get('src').get('ospf')
            dest_o_conf = o_l.get('dest').get('ospf')

            if src_o_conf.get('area') not in ospf_config :
                ospf_config[src_o_conf.get('area')] = src_o_conf

            else :
                area_conf = ospf_config[src_o_conf.get('area')]
                if src_o_conf.get('hello-interval') != area_conf.get('hello-interval') or\
                src_o_conf.get('dead-interval') != area_conf.get('dead-interval') :
                    LOG.error('Hello and dead interval must be the same for the same broadcast domain' )
                    Error= True

            if dest_o_conf.get('area') not in ospf_config :
                ospf_config[dest_o_conf.get('area')] = dest_o_conf

            else :
                area_conf = ospf_config[dest_o_conf.get('area')]
                if dest_o_conf.get('hello-interval') != area_conf.get('hello-interval') or\
                dest_o_conf.get('dead-interval') != area_conf.get('dead-interval') :
                    LOG.error('Hello and dead interval must be the same for the same broadcast domain' )
                    Error= True




        controller_o_conf = fibbing_ctrl.get('controller-config').get('ospf')
        if controller_o_conf.get('area') not in ospf_config :
            LOG.error('The Fibbing controller should be in the same area of at least some other router' )
            Error= True

        else :
            area_conf = ospf_config[controller_o_conf.get('area')]
            if controller_o_conf.get('hello-interval') != area_conf.get('hello-interval') or\
            controller_o_conf.get('dead-interval') != area_conf.get('dead-interval') :
                LOG.error('Hello and dead interval must be the same for the same broadcast domain' )
                Error= True

        if not main_controller :
            LOG.error('The host acting as the main controller must be specified' )
            Error= True





        return Error
    except Exception as e  :
        LOG.critical('Error :'+ str(e))
        Error = True

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
                if (str(s),str(d)) not in edge:
                    error=True
                    LOG.error('Unvalid path %s not exists' % str((s,d)))

    return error


# --------------------------------------------------------
def checkNetworkConfig(d) :

    conf = d['config']

    fibbing_ctrl = conf.get('fibbing-controller')

    Error = False
    Error = checkExist_controllerlink(fibbing_ctrl, Error)
    Error = check_network(conf,  Error)

    return Error

# --------------------------------------------------------
def checkRequirementConfig(d, d_req) :

    config = d['config']
    fibbing_ctrl = config.get('fibbing-controller')
    hosts_link  = config.get('hosts-link')
    links = config.get('links')
    main_controller = config.get('main-controller')
    ospf_links = config.get('ospf-links')
    routers = config.get('routers')
    conf = d_req['config']
    link =  conf["link"]

    Error = False



    # Set up the Controller requirements
    for x in link :
        # set up router connected to dest as last one of the path
        rs = x.get('requirement')[-1]
        if rs == '*' :
            LOG.error('The Path cannot end with the * router')
            Error=True
            continue
        ds = str(x.get('dest'))
        R = ()
        for r in x.get('requirement') :
            R += (str(r),)

        IS_OK = False
        for dsr in hosts_link :
            host = dsr.get('host')
            router = dsr.get('router')
            # check if dest is indeed connected to router
            # in the topology
            if host.get('name') == ds and router.get('name') == rs :
                IS_OK = True

        if not IS_OK :
            LOG.warning('Destination ' + ds + ' is not connected to '+ds)
            
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

    Error = check_path(links,Error,link)

    return Error
