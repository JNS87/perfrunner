[clusters]
nyx =
    172.23.99.241:8091
    172.23.99.245:8091
    172.23.99.246:8091
    172.23.99.251:8091
    172.23.99.118:8091
    172.23.99.119:8091
    172.23.99.123:8091
    172.23.99.247:8091
    172.23.98.118:8091,index
    172.23.98.119:8091
    172.23.99.122:8091

[clients]
hosts =
    172.23.99.87
credentials = root:couchbase

[storage]
data = /data
index = /data

[credentials]
rest = Administrator:password
ssh = root:couchbase

[parameters]
OS = CentOS 7
CPU = Data: E5-2630 (24 vCPU), Index: E5-2630 (24 vCPU)
Memory = Data: 64 GB, Index: 64 GB
Disk = SSD