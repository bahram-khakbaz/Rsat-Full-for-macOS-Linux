USERS = [
    {"samAccountName":"admin.user","displayName":"Admin User","mail":"admin.user@example.local","department":"IT","title":"IT Supervisor","enabled":True,"lockedOut":False,"ou":"OU=IT,OU=Users,DC=example,DC=local"},
    {"samAccountName":"a.rezaei","displayName":"Ali Rezaei","mail":"a.rezaei@example.local","department":"Operations","title":"Operations Specialist","enabled":True,"lockedOut":True,"ou":"OU=Operations,OU=Users,DC=example,DC=local"},
    {"samAccountName":"s.ahmadi","displayName":"Sara Ahmadi","mail":"s.ahmadi@example.local","department":"Finance","title":"Financial Analyst","enabled":False,"lockedOut":False,"ou":"OU=Finance,OU=Users,DC=example,DC=local"},
]
GROUPS = [
    {"name":"IT-Admins","description":"Infrastructure administrators","scope":"Global","members":4},
    {"name":"VPN-Users","description":"Remote access users","scope":"Global","members":128},
    {"name":"Helpdesk","description":"Service desk operators","scope":"Global","members":12},
]
COMPUTERS = [
    {"name":"PC-IT-001","os":"Windows 11 Enterprise","enabled":True,"lastLogon":"2026-10-02T07:10:00Z","ou":"OU=IT,OU=Computers,DC=example,DC=local"},
    {"name":"NB-BD-014","os":"Windows 11 Pro","enabled":True,"lastLogon":"2026-10-02T05:31:00Z","ou":"OU=BD,OU=Computers,DC=example,DC=local"},
]
OUS = [
    {"name":"IT","dn":"OU=IT,DC=example,DC=local"},
    {"name":"Finance","dn":"OU=Finance,DC=example,DC=local"},
    {"name":"Operations","dn":"OU=Operations,DC=example,DC=local"},
]
DNS = [
    {"zone":"example.local","name":"crm","type":"A","value":"10.10.10.20","ttl":3600},
    {"zone":"example.local","name":"n8n","type":"A","value":"10.10.10.21","ttl":3600},
]
DHCP = [
    {"scopeId":"10.20.0.0","name":"Office-LAN","startRange":"10.20.0.20","endRange":"10.20.0.240","free":113,"inUse":107},
]
GPOS = [
    {"displayName":"Default Domain Policy","id":"demo-1","status":"AllSettingsEnabled","modified":"2026-09-18T09:10:00Z"},
    {"displayName":"Endpoint Security Baseline","id":"demo-2","status":"AllSettingsEnabled","modified":"2026-09-27T12:30:00Z"},
]
