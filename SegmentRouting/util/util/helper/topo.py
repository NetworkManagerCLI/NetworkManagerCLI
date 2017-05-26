from nanonet.node import *
import socket
from util import LOG



class IPv6Topo(Topo):
    """
        IPv6Topo class from Nanonet framework
        to build and represent the network

        Build network based on network configurations
    """
    def build(self):

        destinations = map(lambda x : x.get('name'), self.config.get('destinations'))
        controller = self.config.get('controller')
        for router in self.config.get('routers') :
            loaddr = socket.inet_ntop(socket.AF_INET6,
                    socket.inet_pton(socket.AF_INET6,
                 router.get('loopback-addr').split('/')[0] ))+'/'+router.get('loopback-addr').split('/')[1]
            params = router.get('ospf6')
            if params.get('enable') :
                if router.get('name') == controller :
                    self.add_controller(router.get('name'),loaddr, **params)
                else :
                    self.add_router(router.get('name'),loaddr, **params)
            else :
                self.add_host(router.get('name'))
                n = self.get_node(router.get('name'))
                n.addr = loaddr

        ospf_link = {}
        for link in self.config.get('ospf-links') :
            ospf_link[link.get('name')] = link

        for link in self.config.get('link') :
            src = link.get('src')
            dest =  link.get('dest')
            r1 = self.get_node(src.get('name'))
            r2 = self.get_node(dest.get('name'))

            srcAddr = socket.inet_ntop(socket.AF_INET6,\
            socket.inet_pton(socket.AF_INET6, src.get('ip').split('/')[0] ))+'/'+src.get('ip').split('/')[1]
            destAddr = socket.inet_ntop(socket.AF_INET6,\
            socket.inet_pton(socket.AF_INET6, dest.get('ip').split('/')[0]))+'/'+dest.get('ip').split('/')[1]
            if link.get('name') in ospf_link :
                o_l = ospf_link[link.get('name')]
                src_cost = link.get('cost')
                dest_cost = link.get('cost')
                if not link.get('bidirectional') :
                    src_cost = link.get('src').get('cost')
                    dest_cost = link.get('dest').get('cost')


                params1 = {
                    'area' : o_l.get('src').get('ospf').get('area'),
                    'hello-interval' :o_l.get('src').get('ospf').get('hello-interval'),
                    'dead-interval' : o_l.get('src').get('ospf').get('dead-interval'),
                    'cost' :src_cost
                }
                params2 = params1 = {
                    'area' :o_l.get('dest').get('ospf').get('area'),
                    'hello-interval' :o_l.get('dest').get('ospf').get('hello-interval'),
                    'dead-interval' : o_l.get('dest').get('ospf').get('dead-interval'),
                    'cost' :dest_cost
                }
                if not link.get('bidirectional') :
                    self.add_ospf_link(r1, r2,srcAddr, destAddr,
                            cost=link.get('cost'),
                            delay=link.get('delay'),
                            bw=link.get('bw'),
                            directed=True,
                            cost1=int(src_cost),
                            cost2=int(dest_cost),
                            params1=params1,
                            params2=params2)
                else:
                    self.add_ospf_link(r1, r2,srcAddr, destAddr,
                            cost=link.get('cost'),
                            delay=link.get('delay'),
                            bw=link.get('bw'),
                            params1=params1,
                            params2=params2)
            else :
                self.add_link(r1, r2,srcAddr, destAddr,
                        cost=link.get('cost'),
                        delay=link.get('delay'),
                        bw=link.get('bw'))

            LOG.debug( 'Adding link %s <-> %s', src.get('name'), dest.get('name'))


            if link.get('name') not in ospf_link:
                # destinations links :
                if src.get('name') in destinations and isinstance(r1,Host):
                    r1.set_opposite_intf(destAddr)

                elif dest.get('name') in destinations and isinstance(r2,Host):
                    r2.set_opposite_intf(srcAddr)
