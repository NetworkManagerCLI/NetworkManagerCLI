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
      <fibbing-requirement>
        <restart> 10 </restart>
        % for req in requirements :
          <requirement nc:operation="replace">
            <name>${req.name}</name>
            <state>${req.state}</state>
            <dest>${req.dest}</dest>
            %for r in req.path :
              <Path>${r}</Path>
            % endfor
            % if req.state == "scheduled" :
              <schedule>
                <Type>${req.Type}</Type>
                % for day in req.days :
                  <days>${day}</days>
                %endfor
                <start-hour>${req.start_time}</start-hour>
                <end-hour>${req.end_time}</end-hour>
                % if req.Type != 'time' :
                  <link>
                    <from>${req.link.src}</from>
                    <to>${req.link.dest}</to>
                    % if req.Type == 'bandwidth' :
                    <bw-percentage>${req.link.bw}</bw-percentage>
                    % endif
                  </link>
                % endif

              </schedule>
            % endif
          </requirement>
        % endfor
      </fibbing-requirement>
    </fibbing>
    </config>
  </edit-config>
</rpc>
]]>]]>
<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="2">
  <close-session/>
</rpc>
