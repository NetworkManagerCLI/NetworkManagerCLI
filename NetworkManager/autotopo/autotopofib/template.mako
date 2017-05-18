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
      <fibbing xmlns="http://tail-f.com/ns/example/fibbing"
            xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
        <network>
          <restart> 10 </restart>
          <!-- Routers -->
          <router nc:operation="replace">
            <name>*</name>
          </router>

          <!-- OSPF Routers -->
           % for router in topo.ospfrouters :
           <router nc:operation="replace">
             <name>${router.name}</name>
             <ospf>
               <enable>true</enable>
               <router-id>${router.routerid}</router-id>
             </ospf>

           </router>
           % endfor

           % for edge in topo.ospflinks :
             <link nc:operation="replace">
               <name>${edge.name}</name>
               <src>
                 <name>${edge.src.name}</name>
                  <ip>${edge.srcip}</ip>
               </src>
               <dest>
                 <name>${edge.dest.name}</name>
                 <ip>${edge.destip}</ip>
               </dest>
               <bw>${edge.bw}</bw>
               <cost>${edge.cost}</cost>
             </link>
           % endfor

           <!-- Declare  -->
           % for edge in topo.ospflinks :
            <ospf-link-config nc:operation="replace">
              <link-name>${edge.name}</link-name>
            </ospf-link-config>
           % endfor

           <!-- Controller -->
           <fibbing-controller>
           % for edge in topo.controllerlink :
           <links nc:operation="replace">
            <name>${edge.name}</name>
             <controller>
               <name>${edge.ctrl.name}</name>
               <ip>${edge.ctrlip}</ip>
             </controller>
             <router>
               <name>${edge.router.name}</name>
               <ip>${edge.routerip}</ip>
             </router>
          </links>
           % endfor
         </fibbing-controller>

         % for edge in topo.destinationlink :
            <hosts-link nc:operation="replace">
              <name>${edge.name}</name>
              <host>
                <name>${edge.dest.name}</name>
                <ip>${edge.destip}</ip>
              </host>
              <router>
                <name>${edge.router.name}</name>
                <ip>${edge.routerip}</ip>
              </router>
            </hosts-link>
          % endfor

        <main-controller>${topo.main_controller}</main-controller>





        </network>
      </fibbing>
    </config>
  </edit-config>
</rpc>
]]>]]>
<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="2">
  <close-session/>
</rpc>
