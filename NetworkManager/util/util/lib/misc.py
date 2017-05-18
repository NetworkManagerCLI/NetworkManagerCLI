# ALL import
import json
from ipaddress import ip_interface
from util import *
import ipaddress
# from util.lib import *
import ipaddress
import copy
import ConfigParser as cparser
from fibbingnode import CFG


# -----------------------------------------
#   Private Ip binding & ip router name mapping
# -----------------------------------------
def write_private_ip_binding(data,topo, private_ip_binding=PRIVATEIPBINDING) :
    # get the config
    conf = data['config']
    ospf_links = conf.get('link-ospf')

    topodata = topo
    # ip binding dict
    binding = {}
    for ol in ospf_links :
        src = ol.get('src')
        dest = ol.get('dest')
        src_name =  src.get('name')
        dest_name = dest.get('name')
        neighbor = {}
        # get routerid
        getRouterid = topodata[src_name]['routerid']
        # add routerid / ip mapping
        neighbor[getRouterid] = [str(src.get('ip'))]
        # get routerid
        getRouterid = topodata[dest_name]['routerid']
        # add routerid / ip mapping
        neighbor[getRouterid] = [str(dest.get('ip'))]

        PrivateLAN = str(ipaddress.ip_interface(unicode(src.get('private-ip'))).network)
        binding[PrivateLAN] = neighbor


    # --------------------------------------------------------
    with open(private_ip_binding,'w') as outputfile :
        json.dump(binding, outputfile)
    # --------------------------------------------------------


def process_router(router, mapping) :
    mapping[router.get('ip').split('/')[0]] = router.get('name')
    mapping[router.get('private-ip').split('/')[0]] = router.get('name')

    # for sec in router.get('secondary-ips') :
    #     mapping[sec.split('/')[0]] = router.get('name')

def build_ip_mapping(data):
    """
        Create a mapping between ips addresses and router name
    """
    conf = data['config']

    fibbing_ctrl = conf.get('fibbing-controller')
    ospf_links = conf.get('link-ospf')
    hosts_link  = conf.get('hosts-link')
    ctrl_links = fibbing_ctrl.get('links')
    mapping = {}

    for ol in ospf_links :
        src = ol.get('src')
        dest = ol.get('dest')

        process_router(src, mapping)
        process_router(dest, mapping)

    for des in hosts_link :
        router = des.get('router')
        host = des.get('host')

        mapping[router.get('ip').split('/')[0]] = router.get('name')
        mapping[host.get('ip').split('/')[0]] = host.get('name')

    for des in ctrl_links :
        router = des.get('router')
        ctrl = des.get('controller')

        mapping[router.get('ip').split('/')[0]] = router.get('name')
        mapping[ctrl.get('ip').split('/')[0]] = ctrl.get('name')



    return mapping

def build_router_dest_mapping(data) :
    """
        build a mapping bewteen router and destination
    """
    conf = data['config']
    hosts_link  = conf.get('hosts-link')

    mapping = {}

    for d in hosts_link :
        router = d.get('router')
        host = d.get('host')
        mapping[router.get('name')] = host.get('name')

    return mapping

# -----------------------------------------
#   Building topology view from configuration
# -----------------------------------------
def write_topology(config, topo=TOPOlOGY_FILE) :

    # get the configuration
    conf = config['config']
    fibbing_ctrl = conf.get('fibbing-controller')


    private_pfx =fibbing_ctrl.get('controller-config').get('private-ip-prefix')
    private_pfx_len = int(private_pfx.split('/')[1])
    links = conf.get('links')
    main_controller = conf.get('main-controller')
    ospf_links = conf.get('link-ospf')
    hosts_link  = conf.get('hosts-link')
    ctrl_links = fibbing_ctrl.get('links')
    routers = conf.get('routers')

    router_id_map = {}
    for r in routers :
        if r.get('ospf').get('enable') :
            router_id_map[r.get('name')] = r.get('ospf').get('router-id')

    # topology dict
    topology = {}

    # get link config
    for ol in ospf_links :
        src = ol.get('src')
        dest = ol.get('dest')
        src_name =  src.get('name')
        dest_name = dest.get('name')
        # check if already in topology
        if src_name in topology  :
            neighbor = topology.get(src_name)
        else:
            neighbor = {}

        # create a new neighbor
        newneighbor = { "bw" :int(ol.get('bw')),
                        "ip" : src.get('ip'),
                        "name" : src.get('intf')}

        #
        # add the new neighbor
        neighbor[dest_name] = newneighbor
        neighbor['type'] = 'router'

        neighbor['routerid'] = router_id_map[src_name]
        topology[src_name] = neighbor

        # Add the other router
        if dest_name in topology  :
            neighbor = topology.get(dest_name)
        else:
            neighbor = {}

        # create a new neighbor
        newneighbor = { "bw" :int(ol.get('bw')),
                        "ip" : dest.get('ip'),
                        "name" : dest.get('intf')}
        #
        # add the new neighbor
        neighbor[src_name] = newneighbor
        neighbor['type'] = 'router'
        neighbor['routerid'] = router_id_map[dest_name]
        topology[dest_name] = neighbor



    for d in hosts_link :
        host = d.get('host')
        router = d.get('router')
        host_name = host.get('name')
        router_name =  router.get('name')

        if host_name in topology :
            neighbor = topology.get(host_name)
        else :
            neighbor = {}

        newneighbor = { "bw" : int(d.get('bw')),
                        "ip" : host.get('ip'),
                        "name" : host.get('intf') }
        neighbor[router_name] = newneighbor
        neighbor['type'] = 'host'
        topology[host_name] = neighbor

        # add the host to neighbor list of router
        if  router_name in topology :
            neighbor = topology.get(router_name)
        else :
            neighbor = {}

        newneighbor = { "bw" :int(d.get('bw')),
                        "ip" : router.get('ip'),
                        "name" : router.get('intf') }
        neighbor[host_name] = newneighbor
        neighbor['type'] = 'router'
        neighbor['routerid'] = router_id_map[router_name]
        topology[router_name] = neighbor


    # --------------------------------------------------------
    # ADD the controller to router list of neighbor
    for c_l in ctrl_links :
        controller = c_l.get('controller')
        router = c_l.get('router')
        ctrl_name = controller.get('name')
        router_name =  router.get('name')

        if ctrl_name in topology :
            neighbor = topology.get(ctrl_name)
        else :
            neighbor = {}

        newneighbor = { "bw" : int(c_l.get('bw')),
                        "ip" : controller.get('ip'),
                        "name" : controller.get('intf') }
        neighbor[router_name] = newneighbor
        neighbor['type'] = 'controller'
        topology[ctrl_name] = neighbor

        # add the host to neighbor list of router
        if  router_name in topology :
            neighbor = topology.get(router_name)
        else :
            neighbor = {}

        newneighbor = { "bw" :int(c_l.get('bw')),
                        "ip" : router.get('ip'),
                        "name" : router.get('intf') }
        neighbor[ctrl_name] = newneighbor
        neighbor['type'] = 'router'
        neighbor['routerid'] = router_id_map[router_name]
        topology[router_name] = neighbor

    # --------------------------------------------------------
    # DEBUG
    # with open(topo, 'w') as outputfile :
    #     json.dump(topology, outputfile)
    # print (json.dumps(topology))
    # --------------------------------------------------------

    return topology

# -----------------------------------------
#      Generating default configuration
# -----------------------------------------
def write_CFG_ospf(config) :
    # create new parser
    cfg = cparser.ConfigParser()
    # read the template
    cfg.read(template)

    conf = config['config']

    fibbing_ctrl = conf.get('fibbing-controller')
    controller_o_conf = fibbing_ctrl.get('controller-config').get('ospf')
    th_initial_holdtime = controller_o_conf.get('throttle').get('initial_holdtime')
    th_delay = controller_o_conf.get('throttle').get('delay')
    th_max_holdtime = controller_o_conf.get('throttle').get('max_holdtime')
    min_ls_arrival = controller_o_conf.get('lsa').get('min_ls_arrival')
    min_ls_interval = controller_o_conf.get('lsa').get('min_ls_interval')
    hello = controller_o_conf.get('hello-interval')
    dead = controller_o_conf.get('dead-interval')

    private_net = fibbing_ctrl.get('controller-config').get('private-ip-prefix')
    base_net = fibbing_ctrl.get('controller-config').get('base-net-perfix')
    cfg.set(cparser.DEFAULTSECT, 'area', str(controller_o_conf.get('area')))
    cfg.set(cparser.DEFAULTSECT, 'initial_holdtime', int(th_initial_holdtime))
    cfg.set(cparser.DEFAULTSECT, 'delay', int(th_delay))
    cfg.set(cparser.DEFAULTSECT, 'max_holdtime', int(th_max_holdtime))
    cfg.set(cparser.DEFAULTSECT, 'min_ls_interval', int(min_ls_interval))
    cfg.set(cparser.DEFAULTSECT, 'min_ls_arrival', int(min_ls_arrival))
    cfg.set(cparser.DEFAULTSECT, 'hello_interval', str(hello))
    cfg.set(cparser.DEFAULTSECT, 'dead_interval', str(dead))

    # set private ips needed for the fibbing controller
    cfg.set(cparser.DEFAULTSECT, 'private_net', str(private_net))
    cfg.set(cparser.DEFAULTSECT, 'base_net', str(base_net))
    # overrite the default.cfg file
    with open(pathtoREScfg, 'w') as f :
        cfg.write(f)

    # reload the configuration
    CFG.read(pathtoREScfg)

# -----------------------------------------
#     Auto generate private ips
# -----------------------------------------
def get_prefix(address) :
    intf = ipaddress.ip_interface(unicode(address))
    return intf.network


def change_pfx(oldaddress, newpf, newpf_len) :
    # Only support for /8
    address_pfx_len = oldaddress.split('/')[1]
    ipv4_addr_parts = oldaddress.split('/')[0].split('.')
    newpfx_first_part =  newpf.split('/')[0].split('.')[0]
    newaddr = newpfx_first_part
    for i in range(1,4) :
        newaddr = newaddr + '.'+ipv4_addr_parts[i]

    return newaddr+'/'+address_pfx_len


def set_private_ips_1(src_intf, private_pfx_len, private_network) :
    src_primary_ip = src_intf.get('primary-ip')
    src_intf["private-ip"] = change_pfx(src_primary_ip, private_network,private_pfx_len)
    return src_intf

def set_private_ip_2(src_intf, private_ip) :
    src_intf["private-ip"] = private_ip
    return src_intf


def gen_private_ips(config) :
    conf = config['config']
    fibbing_ctrl = conf.get('fibbing-controller')
    private_pfx =fibbing_ctrl.get('controller-config').get('private-ip-prefix')
    private_pfx_len = int(private_pfx.split('/')[1])
    links = conf.get('links')
    main_controller = conf.get('main-controller')
    ospf_links = conf.get('ospf-links')
    hosts_link  = conf.get('hosts-link')
    ctrl_links = fibbing_ctrl.get('links')
    link_key_map = {}
    for link in links :
        link_key_map[link.get('name')] = link

    # merge the topology link and ospf link
    link_ospf = []
    router_port_map = {}
    for o_l in ospf_links :
        tmp =copy.copy(o_l)
        link = link_key_map.get(o_l.get('name'))
        tmp['bw'] = link.get('bw')
        tmp['cost'] = link.get('cost')
        tmp['src']['ip'] = link.get('src').get('ip')
        tmp['src']['name'] = link.get('src').get('name')
        tmp['dest']['ip'] = link.get('dest').get('ip')
        tmp['dest']['name'] = link.get('dest').get('name')
        if link.get('src').get('name') not in router_port_map :
            router_port_map[link.get('src').get('name')] = 0
        else :
            router_port_map[link.get('src').get('name')] += 1
        if link.get('dest').get('name') not in router_port_map :
            router_port_map[link.get('dest').get('name')] = 0
        else :
            router_port_map[link.get('dest').get('name')] += 1

        tmp['src']['intf'] = '%s-eth%d' % (link.get('src').get('name'), router_port_map[link.get('src').get('name')])
        tmp['dest']['intf'] = '%s-eth%d' % (link.get('dest').get('name'), router_port_map[link.get('dest').get('name')])

        link_ospf.append(tmp)


    for h_l in hosts_link :
        src_name  = h_l.get('host').get('name')
        dest_name = h_l.get('router').get('name')
        if src_name not in router_port_map :
            router_port_map[src_name] = 0
        else :
            router_port_map[src_name] += 1
        if dest_name not in router_port_map :
            router_port_map[dest_name] = 0
        else :
            router_port_map[dest_name] += 1

        h_l['host']['intf'] = '%s-eth%d' %(src_name, router_port_map[src_name] )
        h_l['router']['intf'] = '%s-eth%d' %(dest_name, router_port_map[dest_name] )


    for c_l in ctrl_links :
        src_name  = c_l.get('controller').get('name')
        dest_name = c_l.get('router').get('name')
        if src_name not in router_port_map :
            router_port_map[src_name] = 0
        else :
            router_port_map[src_name] += 1
        if dest_name not in router_port_map :
            router_port_map[dest_name] = 0
        else :
            router_port_map[dest_name] += 1
        c_l['controller']['intf'] = '%s-eth%d' %(src_name, router_port_map[src_name] )
        c_l['router']['intf'] = '%s-eth%d' %(dest_name, router_port_map[dest_name] )





    # TODO support other than /8
    if private_pfx.split('/')[1] != '8' :
        LOG.error('The private-ip-prefix should be /8')

    ospf_links_len = len(link_ospf)
    # TODO only rely on /30 address ?

    if ospf_links_len < 255 :
        first_part = private_pfx.split('/')[0].split('.')[0]
        for i in range(ospf_links_len) :
            src_private_ip = first_part +'.'+str(i)+'.'+'255'+'.253/30'
            dest_private_ip = first_part +'.'+str(i)+'.'+'255'+'.254/30'
            link_ospf[i]['src']['private-ip'] = src_private_ip
            link_ospf[i]['dest']['private-ip'] = dest_private_ip

    elif ospf_links_len > 255 and ospf_links_len < 2*255 :
        first_part = private_pfx.split('/')[0].split('.')[0]
        for i in range(ospf_links_len) :
            if i < 255 :
                src_private_ip = first_part +'.'+str(i)+'.'+'255'+'.253/30'
                dest_private_ip = first_part +'.'+str(i)+'.'+'255'+'.254/30'
                link_ospf[i]['src']['private-ip'] = src_private_ip
                link_ospf[i]['dest']['private-ip'] = dest_private_ip
            else :
                src_private_ip  = first_part +'.'+'255'+'.'+ str(255-i)+'.253/30'
                dest_private_ip = first_part +'.'+'255'+'.'+ str(255-i)+'.254/30'
                link_ospf[i]['src']['private-ip'] = src_private_ip
                link_ospf[i]['dest']['private-ip'] = dest_private_ip

    else :
        raise Exception('Not enough private ips, max is 510')

    config['config']['link-ospf'] = link_ospf
    return config
