hostname ${node.hostname}
password ${node.password}
% if node.ospf.logfile:
log file ${node.ospf.logfile}
% endif
!
% for intf in node.ospf.interfaces:
  interface ${intf.name}
  # ${intf.description}
  # Highiest priority routers will be DR
  % if intf.ospf :
  ipv6 ospf6 priority ${intf.ospf.priority}
  ipv6 ospf6 cost ${intf.ospf.cost}
  # dead/hello intervals must be consistent across a broadcast domain
  ipv6 ospf6 dead-interval ${intf.ospf.dead_int}
  ipv6 ospf6 hello-interval ${intf.ospf.hello_int}
  % endif
!
% endfor
router ospf6
  router-id ${node.ospf.router_id}

  redistribute connected
  redistribute static
  !redistribute kernel
  % for intf in node.ospf.interfaces:
  interface ${intf.name} area ${intf.area}
  ! for some reason netwotk command not implemented on ospf6d
  ! network ${intf.network} area ${intf.area}
  % endfor
!
