from util import *
from util.helper import *
from mako.template import Template
from util.helper.Quagga import ConfigDict, render
from util.helper.simplifier import Simplifier
from nanonet.node import *
import copy


class SimpleRequirement(ConfigDict):
    def __init__(self,name,prefix,path, intf, action):
        self.name=name
        self.prefix=prefix
        self.path=path
        self.segs= path
        self.intf = intf
        self.action = action

    def __eq__(self, o) :
        return self.name == o.name

class SSHManager(object) :
    """
        Manage the ssh session that will install/remove
        the SR requirements on the SRagent routers
    """
    def __init__(self, controller):
        """
            :param controller = the controller
                object for the network
        """
        self.controller = controller

    def install_requirement(self, router,prefix, segs, intf) :
        """
            will install the segs via intf on the router
        """

        segsStr = ",".join(map(str, segs))
        insertRoute = ADDROUTE % (prefix, segsStr,intf)
        loaddr = router.addr.split('/')[0]
        sshcmd = SSH6CMD % (loaddr, insertRoute)
        self.controller.cmd_process(sshcmd)
        # TODO find a way to see of install has been
        # successful or not

    def remove_requirement(self,router,prefix ) :
        """
            will remove the requirement on router for prefix
        """
        rmRoute = REMOVEROUTE % (prefix)
        sshrm = SSH6CMD % (router.addr.split('/')[0], rmRoute)
        self.controller.cmd_process(sshrm)
        # TODO find a way to see of remove has been
        # successful or not

    def commit(self) :
        pass



class NetconfManagerECMP(object) :
    def __init__(self, controller):
        """
            :param controller = the controller
                object for the network
        """
        self.controller = controller
        self.state = {}
        self.transaction = {}
        self.tmp_state = {}
        self.successlTransaction = []
        self.deleted_pfx = {}

    def install_requirement(self,name, router,prefix, segs, intf) :
        """
            will install the segs via intf on the router
        """

        # new requirement
        Req = SimpleRequirement(name, prefix, segs, intf, ADD)
        if not self.transaction.get(router) :
            self.transaction[router] = {prefix :  [Req] }
        elif not self.transaction[router].get(prefix) :
            self.transaction[router][prefix] =   [Req]
        else :
            self.transaction[router][prefix].append(Req)




    def remove_requirement(self,name,router,prefix ) :
        """
            will remove the requirement on router for prefix
        """

        Req = SimpleRequirement(name, prefix, None, None, DELETE)
        if not self.transaction.get(router) :
            self.transaction[router] = {prefix :  [Req] }
        elif not self.transaction[router].get(prefix) :
            self.transaction[router][prefix] =   [Req]
        else :
            self.transaction[router][prefix].append(Req)

    def merge_routes(self, RunningRoutes, TransactionRoutes) :
        """
            compute the new  set of routes to install on router
        """
        NewSet = []
        DeleteSet = []
        LOG.debug('TransactionRoutes %s ' % str(TransactionRoutes))
        for Troute in TransactionRoutes :
            if Troute.action == DELETE : # and Troute in RunningRoutes :
                # do not add this route for the update
                DeleteSet.append(Troute)
            else:
                NewSet.append(Troute)

        LOG.debug('RunningRoutes %s ' % str(RunningRoutes))
        for Rroute in RunningRoutes :
            if Rroute not in DeleteSet and Rroute not in TransactionRoutes:
                NewSet.append(Rroute)

        LOG.debug('NewSet %s ' % str(NewSet))
        return NewSet



    def setup_config_dic(self, router) :
        """
            process transaction and prepare config files
        """

        Req = []
        for prefix in self.transaction[router].keys() :

            # already some state of this router/pfx pairs
            if self.state.get(router) :
                # if already something for this prefix
                if self.state[router].get(prefix) :
                    # list of routes for the given pfx
                    RunningRoutes = copy.copy(self.state[router][prefix])
                    TransactionRoutes = self.transaction[router][prefix]

                    NewSet = self.merge_routes(RunningRoutes, TransactionRoutes)
                    if not self.tmp_state.get(router) :
                        self.tmp_state[router] = {prefix :  copy.copy(NewSet) }
                    else :
                        self.tmp_state[router][prefix] = copy.copy(NewSet)
                    action = MODIFY
                    if len(NewSet) == 0:
                        action = DELETE

                    destReq = ConfigDict(prefix=prefix, action=action, routes=NewSet)
                    Req.append(destReq)

                else :
                    TransactionRoutes = self.transaction[router][prefix]
                    if not self.tmp_state.get(router) :
                        self.tmp_state[router] = {prefix :  copy.copy(TransactionRoutes)  }
                    else :
                        self.tmp_state[router][prefix] = copy.copy(TransactionRoutes)

                    action = ADD

                    destReq = ConfigDict(prefix=prefix, action=action, routes=TransactionRoutes)
                    Req.append(destReq)
            else :
                TransactionRoutes = self.transaction[router][prefix]

                if not self.tmp_state.get(router) :
                    self.tmp_state[router] = {prefix :  copy.copy(TransactionRoutes)  }
                else :
                    self.tmp_state[router][prefix] = copy.copy(TransactionRoutes)

                action = ADD

                destReq = ConfigDict(prefix=prefix, action=action, routes=TransactionRoutes)
                Req.append(destReq)

        return Req

    def apply_change(self, router) :
        """
            apply changes if transaction sucessful
        """
        for pfx in self.transaction[router].keys() :
            if not self.state.get(router) :
                self.state[router] = {pfx : copy.copy(self.tmp_state[router][pfx])}
            elif self.state[router].get(pfx) :
                self.state[router][pfx] = copy.copy(self.tmp_state[router][pfx])
            else:
                self.state[router][pfx] = copy.copy(self.tmp_state[router][pfx])


    def send_request(self,router, filename) :
        """
            Send netconf request to router where filename is
            the XML file
        """
        LOG.info('Sending Routes to %s' % router.name)
        sendcmd = NETCONFSEND % (CONFDDIR, router.loopback(), filename)
        rpc_resp = self.controller.cmd_process(sendcmd)
        LOG.debug('RPC RESPONSE : \n %s \n' % rpc_resp)
        if rpc_resp and 'ok' in rpc_resp :
            LOG.info('Requirement Successfully sent to %s' % router.name)
            return True
        else:
            return DBG


    def send_netconf_file(self) :
        """
            build a netconf file per node that needs
            to be updated
        """
        self.successlTransaction = []
        for router in self.transaction.keys() :
            conf = self.setup_config_dic(router)
            filename = file_path(ConfigDIR, 'netconf',router.name,'xml')
            render(NetconfSRTEMP, ConfigDict(stack=conf, delete=[]),filename)
            status = self.send_request(router,filename)

            if status :
                self.apply_change(router)
                # Successful
                for pfx in self.transaction[router].keys() :
                    for Req in self.transaction[router][pfx] :
                        self.successlTransaction.append(Req.name)




        self.transaction = {}
        self.tmp_state = {}

    def commit(self):
        """
            send the netconf request to the different
            routers
        """
        self.send_netconf_file()
        return self.successlTransaction

class NoSimplifier(object) :
    """
        Fake simplifier that just
        output each node as 'normal'
    """
    def __init__(self) :
        pass
    def Simplifier(self, path, dest) :
        tmp = []
        for r in path :
            tmp.append((r, {'type' : 'normal'}))
        return tmp
    def add_node(self, name) :
        pass
    def add_edge(self, node1, node2, cost) :
        pass

class SRSouthboundManager(object) :
    """
        Bridge the NetworkManagerCLI and the network
        to install and remove SR requirements
    """
    def __init__(self, network, manager=NetconfManagerECMP, simplifier=Simplifier) :
        self.network = network
        self.req_encap_map = {}
        self.manager = manager(network.topo.controller)
        self.simplifier = simplifier()
        self.init_simplifier()

        self.remove_set = []
        self.added_set = []
        self.failkey = []

    # ------------------------------------------
    #       API functions
    # ------------------------------------------
    def add_requirement(self, name,dest, pathReq ) :
        """
            @API
            :name = unique identifier of a requirement
            :dest =  destination prefix of the requirement
            :pathReq = hop-by-hop path for the requirement

            add the requirement with path <pathReq>
            and name <name>
        """
        path = copy.copy(pathReq)
        # ingress router is the first router in the path
        ingress = path[0]


        # list of segs is the loopback addr of the
        # rest of the router in the path
        tempsegs = map(self.mapping_fct, self.simplifier.Simplify(path))
        segs = Flatten(tempsegs)
        segs = self.simplify(segs, ingress)
        # force path to neighbor
        # if not segs :
        #     segs = [self.network.topo.get_loopback_by_name(path[1])]

        LOG.debug('requirement for %s : %s' % (dest, str(segs)))

        prefix = self.network.topo.get_loopback_by_name(dest)
        # need a more specific route
        prefix = prefix + '/128'

        IngressNode = self.network.topo.get_node(ingress)
        # get first interface
        intf = self.get_intf_by_router(IngressNode, self.network.topo.get_node(path[1]))

        if intf in map(lambda x: self.req_encap_map[x]['intf'] and\
        self.req_encap_map[x]['prefix'] == prefix, self.req_encap_map.keys()) :
            LOG.error('DAG not solvable for this path %s' % str(path))
            # self.failkey.append(name)
            return segs


        if name in self.req_encap_map :
            LOG.critical('Requirment %s already exists' % (name))
        else :
            if segs :
                self.manager.install_requirement(name,IngressNode,prefix, segs,intf)
            else:
                LOG.info('Nothing to do for %s (empty label stack)' % name)
            # store requirement
            self.req_encap_map[name] = {
                'ingress' : ingress,
                'segs' : segs,
                'prefix' : prefix,
                'intf' : intf,
                'empty' : len(segs) == 0
            }

            self.added_set.append(name)

        return segs

    def remove_requirement(self, name) :
        """
            @API
            remove inserted route from ingress router,
            and delete requirement name
        """
        if name in self.req_encap_map :
            req = self.req_encap_map[name]
            if req.get('segs') :
                IngressNode = self.network.topo.get_node(req['ingress'])
                self.manager.remove_requirement(name,IngressNode, req.get('prefix'))

            # del self.req_encap_map[name]
            self.remove_set.append(name)

        else :
            LOG.critical('Requirement %s is not stored' % name)


    def commit_change(self) :
        """
            @API
            for NetconfManager this will trigger the
            netconf message
        """
        LOG.info('Commiting changes')
        SuccessKeys = self.manager.commit()
        self.backtrack(SuccessKeys)
        return SuccessKeys

    # ------------------------------------------
    #       Lib functions
    # ------------------------------------------

    def init_simplifier(self):
        """
            Initialize the simplifier with the network
            data
        """
        for node in self.network.topo.nodes :
            self.simplifier.add_node(node.name)

        for edge in self.network.topo.edges :
            self.simplifier.add_edge(edge.node1.name, edge.node2.name, edge.cost)

    def simplify(self, requirement, ingress) :
        """
            For a given requirement remove the
            duplicates
        """
        lo = self.network.topo.get_loopback_by_name(ingress)
        tmp = []
        for ip in requirement :
            if ip not in tmp and ip != lo :
                tmp.append(ip)

        return tmp

    def find_intf_addr(self, src, dest) :
        """
            return the intf address of node dest that is
            connected to neighbor node src
        """
        edges = self.network.topo.get_edges(src, dest)
        for e in edges :
            if e.node1 == dest :
                return dest.intfs_addr[e.port1].split('/')[0]
            elif e.node2 == dest :
                return dest.intfs_addr[e.port2].split('/')[0]


    def get_intf_by_router(self,from_R, to_R) :
        """
            return the intf name of router from_R
            that is connected to router to_R
        """

        edges = self.network.topo.get_edges(from_R, to_R)
        for intfname in from_R.intfs_name.keys() :
            for e in edges :
                if e.node1 == from_R :
                    return '%s-%d' % (from_R.name, e.port1)
                elif e.node2 == from_R :
                    return '%s-%d' % (from_R.name, e.port2)
        return False


    def mapping_fct(self,item) :
        """
            function that map the name
            with a loopback address
            (or a interface address for
            adjacency segments)
        """
        if item[1].get('type') == 'normal' :
            return self.network.topo.get_loopback_by_name(item[0])
        elif item[1].get('type') == 'adjacency' :
            src = self.network.topo.get_node(item[1].get('prev'))
            dest = self.network.topo.get_node(item[0])

            return [self.network.topo.get_loopback_by_name(item[1].get('prev')),
                    self.find_intf_addr(src, dest)
                    ]



    def backtrack(self,SuccessKeys) :
        """
            Based on the SuccessKeys and the remove and
            added set, kill backtrack if transation failed
        """
        for key in self.remove_set :
            # Empty label satck is ok
            if self.req_encap_map[key]['empty'] :
                if key not in SuccessKeys :
                    SuccessKeys.append(key)
                    del self.req_encap_map[key]
                continue
            if key in SuccessKeys :
                del self.req_encap_map[key]

        for key in self.added_set :
            # Empty label satck is ok
            if self.req_encap_map[key]['empty'] :
                SuccessKeys.append(key)
                continue

            if key not in SuccessKeys :
                del self.req_encap_map[key]

        self.remove_set = []
        self.added_set = []
