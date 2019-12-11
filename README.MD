# DomainChecker
DomainChecker aims to perform regular checks on A, NS and MX records, and to store output of modifications in elasticsearch.

It could be used to monitor domains for protection or hunt/follow known malicious domains (if they pivot)

## Usage
To create db :
```bash
python3 domainchecker.py -f hosts.txt -c database.db
```

To perform checks and store in elasticsearch:
```bash
python3 domainchecker.py -f hosts.txt -b database.db -o 127.0.0.1 > /dev/null
```

## Installation
install dependencies :
```bash
pip install -r requirements.txt
```
Install elasticsearch template in elasticsearch.
Create Database by giving hosts file
