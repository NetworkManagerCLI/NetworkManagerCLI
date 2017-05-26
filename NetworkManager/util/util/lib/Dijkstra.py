from collections import defaultdict, deque
from util import LOG

# Dijkstra code from https://gist.github.com/econchick/4666413
class Graph(object):
    """
        Graph Object
        that computes Dijkstra
    """
    def __init__(self):
        self.nodes = set()
        self.edges = defaultdict(list)
        self.distances = {}
        self.path = {}

    def add_node(self, value):
        self.nodes.add(value)

    def add_edge(self, from_node, to_node, distance):
        self.edges[from_node].append(to_node)
        self.edges[to_node].append(from_node)
        self.distances[(from_node, to_node)] = distance
        self.distances[(to_node, from_node)] = distance

    def add_edge_unidirectional(self, from_node, to_node, distance) :
        self.edges[from_node].append(to_node)
        self.distances[(from_node, to_node)] = distance

    def dijkstra(self, initial):
        visited = {initial: 0}
        path = {}

        nodes = set(self.nodes)

        while nodes:
            min_node = None
            for node in nodes:
                if node in visited:
                    if min_node is None:
                        min_node = node
                    elif visited[node] < visited[min_node]:
                        min_node = node

            if min_node is None:
                break

            nodes.remove(min_node)
            current_weight = visited[min_node]

            for edge in self.edges[min_node]:
              weight = current_weight + self.distances[(min_node, edge)]
              if edge not in visited or weight < visited[edge]:
                visited[edge] = weight
                path[edge] = min_node

#   return visited, path
        self.path = path


    def build_path(self,source, dest) :
        s, u = deque(), dest
        while u != source and self.path[u]:
            s.appendleft(u)
            u = self.path[u]
        s.appendleft(u)
        return s


def get_simple_path_req(Requirement, destRouter, graph) :
    """
        from :Requirement, :destRouter, :graph
        compute the path expansion of the * routers
    """
    Simple_path_req = []

    for i in range(len(Requirement)):
        if i==0 and str(Requirement[i]) ==  '*' :
            # ignore
            continue
        elif i== len(Requirement) - 1 and str(Requirement[i]) == '*' :
            # fill the last part of Simple_path_req with
            # the shortest path to destRouter
            last = Simple_path_req[-1]
            graph.dijkstra(last)
            Path = graph.build_path(last, destRouter)

            for r in Path :
                if str(r) != str(last) :
                    Simple_path_req.append(str(r))


        elif str(Requirement[i]) == '*' :
            # fill this part of Simple_path_req with
            # the shortest path between the two routers
            last = Simple_path_req[-1]
            dest = Requirement[i+1]
            graph.dijkstra(last)
            Path = graph.build_path(last, dest)

            for r in Path :
                if str(r) != str(last) and str(r) != str(dest):
                    Simple_path_req.append(str(r))

        else :
            Simple_path_req.append(str(Requirement[i]))


    return Simple_path_req

def is_ok_path_req(req) :
    """
        checks if path of requirement is
        ok
    """
    for i in range(len(req)) :
        if i != len(req) -1 :
            if req[i] == '*' and req[i+1] == '*' :
                LOG.error('Cannot have two consecutive *  in requirement')
                return  False
    return True

def find_edge(src, dest, edges) :
    for edge in edges :
        if edge[0] == src and edge[1] == dest :
            return edge
    return False

def complete_path(data, Requirement, destRouter) :
    """
        @API
        function called by the NMCore to
        perform path expansion of :Requirement

        :data is the network config from ConfD Agent
    """

    conf = data['config']
    ospf_routers = conf.get('routers')
    ospf_links = conf.get('links')

    routers = []
    for r in ospf_routers :
        routers.append(r.get('name'))
    edges = []
    for OL in ospf_links :
        src = OL.get('src')
        dest = OL .get('dest')
        if OL.get('bidirectional') :
            edges.append( (src.get('name'), dest.get('name'), int(OL.get('cost')), 'bidirectional'))

        else:
            edges.append( (src.get('name'), dest.get('name'), int(src.get('cost')), 'unidirectional'))
            edges.append( (dest.get('name'), src.get('name'), int(dest.get('cost')), 'unidirectional'))




    for i in range(len(Requirement)-1) :
        # remove edges already in the Requirement
        if Requirement[i] != '*' and Requirement[i+1] != '*' :
            edge = find_edge(Requirement[i], Requirement[i+1], edges)
            index = edges.index(edge)
            del edges[index]
            edge = find_edge(Requirement[i+1], Requirement[i], edges)
            index = edges.index(edge)
            del edges[index]


    # build graph
    graph = Graph()
    for router in routers :
        graph.add_node(router)

    for edge in edges :
        if edge[3] == 'unidirectional' :
            graph.add_edge_unidirectional(edge[0], edge[1], edge[2])
        else:
            graph.add_edge(edge[0], edge[1], edge[2])
    try :
        Simple_path_req = get_simple_path_req(Requirement, destRouter, graph)
    except KeyError :
        LOG.critical('Could not solve path expansion for '+ str(Requirement))
        return False


    LOG.info('Success path expansion...')
    LOG.info('Path : ' + str(Simple_path_req) + '  for :' + str(destRouter))
    return Simple_path_req



if __name__ == '__main__':




    # Build simple path requirement from Requirement



    Requirement  = ['A','C']
    # destRouter = 'LOSA'
    # print 'Test * in the middle loop free path '

    # Requirement  = ['NEWY', 'CHIC', 'KANS', '*']
    # Requirement  = ['*', 'CHIC', 'KANS', 'SALT', 'LOSA']
    destRouter = 'C'
    print 'Test * at the end '
    print "Simple path requirement : "
    print str(Requirement)
    #  modify the graph to remove edges already in the path
    # this would prevent to find a shortest path will loop
    routers = [
        'A',
        'B',
        'C',
    ]

    edges = [
    ('A','B',1),
    ('A','C',2),
    ('B','C',1),

    ('B','A',1),
    ('C','A',2),
    ('C','B',1),
    ]


    # build graph
    prunedgraph = Graph()
    for router in routers :
        prunedgraph.add_node(router)

    for edge in edges :
        # print edge
        prunedgraph.add_edge(edge[0], edge[1], edge[2])


    print "DAG : "
    prunedgraph.dijkstra('A')
    print str(prunedgraph.path)
    Simple_path_req = prunedgraph.build_path('A','C')
    print str(Simple_path_req )




    #
    #
    # Simple_path_req = get_simple_path_req(Requirement, destRouter, graph)
    # for Router in Simple_path_req :
    #     print Router


    # Requirement  = ['NEWY', 'CHIC', '*', 'SALT', 'LOSA']
    # destRouter = 'LOSA'
    # print 'Test * in the middle'
    # print "Simple path requirement : "
    # Simple_path_req = get_simple_path_req(Requirement, destRouter, graph)
    # for Router in Simple_path_req :
    #     print Router
    #
    # Requirement  = ['*', 'CHIC', 'KANS', 'SALT', 'LOSA']
    # destRouter = 'LOSA'
    # print 'Test * at the beginning'
    # print "Simple path requirement : "
    # Simple_path_req = get_simple_path_req(Requirement, destRouter, graph)
    # for Router in Simple_path_req :
    #     print Router
