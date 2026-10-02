DOMAIN = {
    "domain":"example.local","forest":"example.local","domainMode":"Windows2016Domain",
    "forestMode":"Windows2016Forest","pdc":"DC01.example.local","rid":"DC01.example.local",
    "infrastructure":"DC01.example.local","schema":"DC01.example.local","naming":"DC01.example.local"
}
DCS = [
    {"name":"DC01","hostName":"DC01.example.local","site":"HQ","ipv4":"10.10.0.10","os":"Windows Server 2022","globalCatalog":True,"enabled":True},
    {"name":"DC02","hostName":"DC02.example.local","site":"DR","ipv4":"10.10.1.10","os":"Windows Server 2022","globalCatalog":True,"enabled":True},
]
REPLICATION = [
    {"server":"DC01","partner":"DC02","lastSuccess":"2026-10-02T07:31:00Z","failures":0,"status":"Healthy"},
    {"server":"DC02","partner":"DC01","lastSuccess":"2026-10-02T07:30:00Z","failures":0,"status":"Healthy"},
]
TRUSTS = [{"name":"example.local","direction":"Bidirectional","type":"ParentChild","transitive":True}]
SITES = [{"name":"HQ","subnets":3},{"name":"DR","subnets":1}]
USERS = [
    {"samAccountName":"admin.user","displayName":"Admin User","mail":"admin.user@example.local","department":"IT","title":"IT Supervisor","company":"Example","enabled":True,"lockedOut":False,"ou":"OU=IT,OU=Users,DC=example,DC=local"},
    {"samAccountName":"a.rezaei","displayName":"Ali Rezaei","mail":"a.rezaei@example.local","department":"Operations","title":"Operations Specialist","company":"Example","enabled":True,"lockedOut":True,"ou":"OU=Operations,OU=Users,DC=example,DC=local"},
    {"samAccountName":"s.ahmadi","displayName":"Sara Ahmadi","mail":"s.ahmadi@example.local","department":"Finance","title":"Financial Analyst","company":"Example","enabled":False,"lockedOut":False,"ou":"OU=Finance,OU=Users,DC=example,DC=local"},
]
GROUPS = [
    {"name":"IT-Admins","description":"Infrastructure administrators","scope":"Global","category":"Security","members":4},
    {"name":"VPN-Users","description":"Remote access users","scope":"Global","category":"Security","members":128},
    {"name":"Helpdesk","description":"Service desk operators","scope":"Global","category":"Security","members":12},
]
GROUP_MEMBERS = {
    "IT-Admins":[{"name":"Admin User","samAccountName":"admin.user","objectClass":"user"}],
    "Helpdesk":[{"name":"Ali Rezaei","samAccountName":"a.rezaei","objectClass":"user"}],
}
COMPUTERS = [
    {"name":"PC-IT-001","os":"Windows 11 Enterprise","enabled":True,"lastLogon":"2026-10-02T07:10:00Z","ipv4":"10.20.0.31","ou":"OU=IT,OU=Computers,DC=example,DC=local"},
    {"name":"NB-BD-014","os":"Windows 11 Pro","enabled":True,"lastLogon":"2026-10-02T05:31:00Z","ipv4":"10.20.0.72","ou":"OU=BD,OU=Computers,DC=example,DC=local"},
]
OUS = [
    {"name":"Users","dn":"OU=Users,DC=example,DC=local","protected":True},
    {"name":"IT","dn":"OU=IT,OU=Users,DC=example,DC=local","protected":True},
    {"name":"Finance","dn":"OU=Finance,OU=Users,DC=example,DC=local","protected":True},
    {"name":"Operations","dn":"OU=Operations,OU=Users,DC=example,DC=local","protected":True},
]
DNS_ZONES = [
    {"name":"example.local","type":"Primary","integrated":True,"reverse":False},
    {"name":"20.10.in-addr.arpa","type":"Primary","integrated":True,"reverse":True},
]
DNS = [
    {"zone":"example.local","name":"crm","type":"A","value":"10.10.10.20","ttl":3600},
    {"zone":"example.local","name":"n8n","type":"A","value":"10.10.10.21","ttl":3600},
    {"zone":"example.local","name":"portal","type":"CNAME","value":"crm.example.local.","ttl":3600},
]
DHCP = [{"scopeId":"10.20.0.0","name":"Office-LAN","state":"Active","startRange":"10.20.0.20","endRange":"10.20.0.240","free":113,"inUse":107}]
DHCP_LEASES = [
    {"scopeId":"10.20.0.0","ipAddress":"10.20.0.31","hostName":"PC-IT-001.example.local","clientId":"AA-BB-CC-DD-EE-01","state":"Active","expiry":"2026-10-09T07:00:00Z"},
    {"scopeId":"10.20.0.0","ipAddress":"10.20.0.72","hostName":"NB-BD-014.example.local","clientId":"AA-BB-CC-DD-EE-02","state":"Active","expiry":"2026-10-09T06:00:00Z"},
]
DHCP_RESERVATIONS = [{"scopeId":"10.20.0.0","ipAddress":"10.20.0.10","clientId":"AA-BB-CC-DD-EE-10","name":"PRINTER-HQ","description":"HQ printer"}]
GPOS = [
    {"displayName":"Default Domain Policy","id":"demo-1","status":"AllSettingsEnabled","owner":"EXAMPLE\\Domain Admins","modified":"2026-09-18T09:10:00Z"},
    {"displayName":"Endpoint Security Baseline","id":"demo-2","status":"AllSettingsEnabled","owner":"EXAMPLE\\Domain Admins","modified":"2026-09-27T12:30:00Z"},
]
GPO_LINKS = [{"displayName":"Endpoint Security Baseline","target":"OU=IT,OU=Users,DC=example,DC=local","enabled":True,"enforced":False,"order":1}]

PASSWORD_POLICY = {"minPasswordLength":12,"maxPasswordAgeDays":90,"minPasswordAgeDays":1,"passwordHistoryCount":24,"complexityEnabled":True,"lockoutThreshold":5,"lockoutDurationMinutes":30}
FINE_GRAINED_POLICIES = [{"name":"Privileged-Accounts","precedence":10,"minPasswordLength":16,"maxPasswordAgeDays":45,"lockoutThreshold":5}]
SUBNETS = [{"name":"10.20.0.0/24","site":"HQ"},{"name":"10.30.0.0/24","site":"HQ"},{"name":"10.40.0.0/24","site":"DR"}]
DELETED_OBJECTS = [{"name":"Former User","objectClass":"user","lastKnownParent":"OU=Users,DC=example,DC=local","deletedAt":"2026-09-29T12:00:00Z","objectGuid":"11111111-1111-1111-1111-111111111111"}]
GPO_PERMISSIONS = [{"trustee":"EXAMPLE\\Domain Admins","type":"Group","permission":"GpoEditDeleteModifySecurity","inherited":False},{"trustee":"Authenticated Users","type":"WellKnownGroup","permission":"GpoApply","inherited":False}]
