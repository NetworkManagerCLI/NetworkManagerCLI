hostname ${node.hostname}
password ${node.password}
% if node.zebra.logfile:
log file ${node.zebra.logfile}
% endif

!ipv6 prefix-list NETWORK permit fc00:42::/32 ge 33
!route-map NET deny 10
!  match ip address prefix-list NETWORK
!
!route-map NET permit 20
!ip protocol ospf6 route-map NET
!
