from fibbingnode.algorithms.southbound_interface import SouthboundManager
from fibbingnode.algorithms.ospf_simple import OSPFSimple
from fibbingnode.misc.igp_graph import IGPGraph
from fibbingnode import CFG
from util import LOG, pathtoREScfg
import threading
import time

class SimpleRequirement(object):
    def __init__(self,name,prefix,path):
        self.name=name
        self.prefix=prefix
        self.path=path


class SouthBoundExtended(SouthboundManager):
    def __init__(self,cfg=None,
                optimizer=OSPFSimple(),
                additional_routes=None,
                *args, **kwargs):
                if cfg :
                    # reading CFG config
                    CFG.read(pathtoREScfg)
                    CFG.read(cfg)
                self.simple_req={}
                self.change_pfx=[] #TODO IF prefixfix is already present before adding it
                super(SouthBoundExtended,self).__init__( optimizer=optimizer,*args,**kwargs)

    def add_requirement(self,name,prefix,path):
        """
            @API
            :name = unique identifier of a requirement
            :prefix =  destination prefix of the requirement
            :path = hop-by-hop path for the requirement

        """
        if not self.simple_req.get(prefix):
            req=SimpleRequirement(name,prefix,path)
            self.simple_req[prefix]=[]
            self.simple_req[prefix].append(req)
        else:
            req=SimpleRequirement(name,prefix,path)
            self.simple_req[prefix].append(req)
        self.change_pfx.append(prefix)

    def remove_requirement(self,name,prefix):
        """
            @API
            :name = unique identifier of a requirement
            :prefix = destination prefix of the requirement
        """
        if not self.simple_req.get(prefix):
            LOG.critical("No requirement for this prefix : "+ str(prefix))
        else:
            index = self.get_index_by_name(name,prefix)
            if index != -1:
                del self.simple_req[prefix][index]
                self.change_pfx.append(prefix)
            else:
                LOG.critical("No prefix has this name : "+ str(name))

    def commit_change(self):
        """
            @API
            commit the changes, and applied the requirements
            entered for the current session
        """
        for prefix in self.change_pfx:
            tmp=[]
            if not self.simple_req[prefix] :
                self.remove_dag_requirement(prefix)
            else :
                for item in self.simple_req[prefix]:
                    for s,d in zip(item.path[:-1],item.path[1:]):
                        if (s,d) not in tmp:
                            tmp.append((s,d))
                LOG.debug('add_dag_requirement')
                self.add_dag_requirement(prefix,IGPGraph(tmp))
        del self.change_pfx[:]
        self.refresh_augmented_topo()


    def get_index_by_name(self,name,prefix):
        counter=0
        for item in self.simple_req[prefix]:
            if item.name == name :
                return counter
            counter+=1
        return -1



class MultipleSouthboundManager(object) :
    def __init__(self, Controllers) :
        self.controllers = Controllers
        self.managers = {}

        self._start()


    def _start(self) :
        """
            for each of the controllers,
            read config CFG and build the
            corresponding SouthBoundExtended manager
        """
        for ctrl_name in self.controllers :
            # CFG.read(pathtoREScfg)
            CFG_p = '/tmp/%s.cfg' % ctrl_name
            # CFG.read(CFG_p)
            LOG.info('creating SouthBoundExtended for %s...' % ctrl_name)
            self.managers[ctrl_name] = SouthBoundExtended(cfg=CFG_p)
            time.sleep(10)



    def run(self) :
        """
            run each of the manager in its given thread
        """
        for key in self.managers :
            LOG.info('starting SouthBoundExtended for %s' % key)
            tmp_th= threading.Thread(target=self.managers[key].run)
            tmp_th.start()

    def stop(self) :
        """
            stop each of the managers
        """
        for key in self.managers :
            self.managers[key].stop()

    # Same API as SouthBoundExtended
    def add_requirement(self,name,prefix,path):
        """
            @API
        """
        for key in self.managers :
            self.managers[key].add_requirement(name, prefix, path)

    def remove_requirement(self,name,prefix):
        """
            @API
        """
        for key in self.managers :
            self.managers[key].remove_requirement(name, prefix)

    def commit_change(self):
        """
            @API
        """
        for key in self.managers :
            self.managers[key].commit_change()
