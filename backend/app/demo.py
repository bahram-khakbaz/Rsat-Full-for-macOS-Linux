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
    {
        "samAccountName": f"user{i:02d}",
        "displayName": f"Demo User {i:02d}",
        "mail": f"user{i:02d}@example.local",
        "department": ["IT","Infrastructure","HR","Finance","Operations","Sales"][i % 6],
        "title": ["System Administrator","System Engineer","HR Specialist","Financial Analyst","Operations Specialist","Network Engineer"][i % 6],
        "company": "Example",
        "manager": "CN=Demo Manager,OU=Users,DC=example,DC=local",
        "mobile": f"+1 555 01{i:02d}",
        "employeeId": str(1000+i),
        "enabled": i not in (9,14),
        "lockedOut": i == 2,
        "lastLogon": f"2026-10-{1 + (i % 2):02d}T{8 + (i % 10):02d}:12:00Z",
        "created": f"202{1 + (i % 4)}-04-12T09:11:00Z",
        "passwordLastSet": "2026-09-20T07:30:00Z",
        "passwordExpires": "2026-12-19T07:30:00Z",
        "passwordNeverExpires": False,
        "dn": f"CN=Demo User {i:02d},OU=Users,DC=example,DC=local",
        "ou": "OU=Users,DC=example,DC=local",
    }
    for i in range(1, 16)
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

AUDIT = [
    {"id":1,"at":"2026-10-02T08:42:11Z","actor":"admin","role":"admin","action":"Reset Password","target":"user02","status":"success","details":{}},
    {"id":2,"at":"2026-10-02T08:40:45Z","actor":"admin","role":"admin","action":"Unlock Account","target":"user14","status":"success","details":{}},
    {"id":3,"at":"2026-10-02T08:38:32Z","actor":"admin","role":"admin","action":"Enable User","target":"user03","status":"success","details":{}},
    {"id":4,"at":"2026-10-02T08:35:19Z","actor":"helpdesk","role":"helpdesk","action":"Add to Group","target":"user04","status":"success","details":{}},
    {"id":5,"at":"2026-10-02T08:22:03Z","actor":"admin","role":"admin","action":"Create User","target":"user15","status":"success","details":{}},
    {"id":6,"at":"2026-10-02T08:19:47Z","actor":"helpdesk","role":"helpdesk","action":"Disable User","target":"user09","status":"success","details":{}},
    {"id":7,"at":"2026-10-02T08:15:28Z","actor":"admin","role":"admin","action":"Modify Attributes","target":"user01","status":"success","details":{}},
    {"id":8,"at":"2026-10-02T08:12:11Z","actor":"admin","role":"admin","action":"Move User","target":"user08","status":"success","details":{}},
]
