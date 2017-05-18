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
      <sragent xmlns="http://tail-f.com/ns/example/sragent"
            xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">

        % for req in node.stack:
          <sr-routes operation="replace">
            <destination>${req.prefix}</destination>
            <action>${req.action}</action>
            % if req.action != "delete":
              % for route in req.routes :
              <routes >
                <intf>${route.intf}</intf>
                % for seg in route.segs :
                  <segments>${seg}</segments>
                % endfor
              </routes>
              % endfor
            % endif
          </sr-routes>
        % endfor
        ## % for prefix in node.delete:
        ## <sr-requirement operation="delete">
        ##   <destination operation="delete">${prefix}</destination>
        ## </sr-requirement>
        ## % endfor
      </sragent>
    </config>
  </edit-config>
</rpc>
]]>]]>
<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="2">
  <close-session/>
</rpc>
