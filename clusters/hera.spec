[clusters]
hera =
    172.23.96.117
    172.23.96.118
    172.23.96.119
    172.23.96.120
    172.23.96.123,index
    172.23.96.112,n1ql

[clients]
hosts =
    172.23.99.111
credentials = root:couchbase

[storage]
data = /data
index = /data

[credentials]
rest = Administrator:password
ssh = root:couchbase

[parameters]
OS = CentOS 7
CPU = Data: CPU E5-2630 v3 (32 vCPU), Query & Index: E5-2680 v3 (48 vCPU)
Memory = Data & Query: 64GB, Index: 512GB
Disk = SSD
