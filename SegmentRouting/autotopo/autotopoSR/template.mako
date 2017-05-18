<?xml version="1.0" encoding="UTF-8"?>
<hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <capabilities>
    <capability>urn:ietf:params:netconf:base:1.0</capability>
  </capabilities>
</hello>
]]>]]>
<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="1">
  <edit-config>
    <target>
      <running/>
    </target>

    <config>
      <!-- config for mininet -->
      <!-- name of principal container  -->
      <segment-routing xmlns="http://tail-f.com/ns/example/segmentrouting"
            xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
        <network>
          <!-- modify the restart value to trigger a commit -->
          <restart>12</restart>

          <!-- Router * for requirement -->
          <router nc:operation="replace">
            <name>*</name>
          </router>

          <!-- ROUTERS -->
          % for router in topo.routers :
            <router nc:operation="replace">
              <name>${router.name}</name>
              <loopback-addr>${router.loopback}</loopback-addr>
              <ospf>
                % if router.ospf6_enabled :
                  <enable>true</enable>
                  <router-id>${router.routerid}</router-id>
                % endif
              </ospf>
            </router>
          % endfor


          <!-- LINKS -->
          % for link in topo.links :
            <link nc:operation="replace">
              <name>${link.name}</name>
              % if link.cost :
                <cost>${link.cost}</cost>
              % endif
              % if link.bw :
                <bw>${link.bw}</bw>
              % endif
              <src>
                <name>${link.src.name}</name>
                <ip>${link.srcip}</ip>
              </src>
              <dest>
                <name>${link.dest.name}</name>
                <ip>${link.destip}</ip>
              </dest>
            </link>
          % endfor

          <!-- OSPF LINK -->
          % for link in topo.links :
              % if link.ospf6_enabled :
              <ospf-link-config nc:operation="replace">
                <link-name>${link.name}</link-name>
              </ospf-link-config>
              % endif
          % endfor



          <!-- Declaring destinations -->
          % for dest in topo.destinations :
            <destinations nc:operation="replace">
              <name>${dest.name}</name>
            </destinations>
          % endfor


          <!-- Declaring controller -->
          <main-controller>${topo.controller.name}</main-controller>


        </network>
      </segment-routing>
    </config>
  </edit-config>
</rpc>
]]>]]>
<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="2">
  <close-session/>
</rpc>
