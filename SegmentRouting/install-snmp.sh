cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.backup
cp res/snmpd.conf /etc/snmp/snmpd.conf
# comment the :mibs line 
sed -i '/^mibs :/s/^/# /' /etc/snmp/snmp.conf
