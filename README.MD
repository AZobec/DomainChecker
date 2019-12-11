# DomainChecker
DomainChecker aims to perform regular checks on A, NS and MX records, and to store output of modifications in elasticsearch.

It could be used to monitor domains for protection or hunt/follow known malicious domains (if they pivot)

## Usage
to create db :
python3 domainchecker.py -f hosts.txt -c database.db

to perform checks and store in elasticsearch
python3 domainchecker.py -f hosts.txt -b database.db -o 127.0.0.1 > /dev/null
