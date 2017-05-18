from net import *
from topo import *


class Test(Topo) :
    def build(self) :
        self.add_edge_by_type('A', 'B', OSPF_LINK, 10, 100)
        self.add_edge_by_type('A', 'C', OSPF_LINK, 1, 100)
        self.add_edge_by_type('C', 'D', OSPF_LINK, 1, 100)
        self.add_edge_by_type('B', 'B', OSPF_LINK, 1, 100)

        self.add_edge_by_type('S', 'A', DEST_LINK)
        self.add_edge_by_type('Dest', 'D', DEST_LINK)

        self.add_edge_by_type('Ctrl', 'C', CTRL_LINK)



if __name__ == '__main__':
    net = Network(Test())

    net.assign()

    net.print_net()

    net.gen_xml()
