#!/usr/bin/env python

import sys, os
from node import *
from net import *
import socket
import json
#
# config = {
#     'link' : [
#         {'src' : {'name' : 'A', 'ip' : 'fc00:42:0:1::1'},
#          'dest' : {'name' : 'B', 'ip' : 'fc00:42:0:1::2'},
#          'cost' : 1, 'delay' : 3, 'bw' : 1
#         },
#         {'src' : {'name' : 'A', 'ip' : 'fc00:42:0:2::1'},
#          'dest' : {'name' : 'C', 'ip' : 'fc00:42:0:2::2'},
#          'cost' : 1, 'delay' : 3, 'bw' : 1
#         },
#         {'src' : {'name' : 'B', 'ip' : 'fc00:42:0:3::1'},
#          'dest' : {'name' : 'C', 'ip' : 'fc00:42:0:3::2'},
#          'cost' : 1, 'delay' : 3, 'bw' : 1
#         }
#     ],
#     'network' : {
#         'mask' : 32 ,
#         'submask' : 64
#     }
# }

with open('debug/network.json') as f :
    config = json.load(f)



class Test(Topo):
    def build(self):
        submask = config.get('network').get('submask')
        for link in config.get('link') :
            src = link.get('src')
            dest =  link.get('dest')
            self.add_node(src.get('name'))
            self.add_node(dest.get('name'))
            self.add_link_name(src.get('name'), dest.get('name'),\
            cost=link.get('cost'),\
            delay=link.get('delay'),\
            bw=link.get('bw'))
            #
            print 'Adding link %s, %s', src.get('name'), dest.get('name')
            nodeSrc = self.get_node(src.get('name'))
            nodeDesr = self.get_node(dest.get('name'))
            nodeSrc.intfs_addr[nodeSrc.cur_intf -1] = socket.inet_ntop(socket.AF_INET6,\
            socket.inet_pton(socket.AF_INET6, src.get('ip')))+'/'+str(submask)
            nodeDesr.intfs_addr[nodeDesr.cur_intf -1] = socket.inet_ntop(socket.AF_INET6,\
            socket.inet_pton(socket.AF_INET6, dest.get('ip')))+'/'+str(submask)

topo = Test()

net = Nanonet(topo,mask=config.get('network').get('mask'), submask=config.get('network').get('submask'))
net.start()

f = open('Test.topo.sh', 'w')

for n in net.topo.nodes:
	f.write('# %s loop: %s\n' % (n.name, n.addr))
f.write('\n')

net.dump_commands(lambda x: f.write('%s\n' % x), noroute=False)
f.close()
