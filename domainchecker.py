import sys
from optparse import OptionParser
import optparse
import sqlite3 as lite
import datetime
import dns.resolver
from elasticsearch import Elasticsearch
import json

#es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
#https://towardsdatascience.com/getting-started-with-elasticsearch-in-python-c3598e718380

def es_store_record(elastic_object, index_name, record):
    try:
        outcome = elastic_object.index(index=index_name, doc_type='_doc', body=record)
    except Exception as ex:
        print('Error in indexing data')
        print(str(ex))

def es_create_index(es_object, index_name):
    created = False
    # index settings
    settings = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "members": {
                "properties": {
                    "record_old": {
                        "type": "text"
                    },
                    "record_new": {
                        "type": "text"
                    },
                    "recordtype": {
                        "type": "text"
                    },
                    "last_seen": {
                        "type": "date"
                    },
                    "domain": {
                        "type": "text"
                    },
                    "timestamp":{
                        "type": "date"
                    },
                }
            }
        }
    }
    try:
        if not es_object.indices.exists(index_name):
            # Ignore 400 means to ignore "Index Already Exist" error.
            es_object.indices.create(index=index_name, ignore=400, body=settings)
            print('Created Index')
        created = True
    except Exception as ex:
        print(str(ex))
    finally:
        return created
                            
						

#This function is used to connect to Elasticsearch
def es_connection(es_host,es_port):
    es = Elasticsearch([{'host': es_host, 'port': es_port}])
    return es

#This function checks the difference between the actual resolution and the database
def checkRecord(database_file,es_host,es_port,es_index_name,domain,checked_list,recordtype):
    epochdate = int(datetime.datetime.now().timestamp())
    connect = lite.connect(database_file)
    if es_host != False:
        es = es_connection(es_host,es_port)
    with connect:
        connect.row_factory = lite.Row
        cur = connect.cursor()
        request = "SELECT domain,record,recordtype,updatedate FROM domains WHERE domain=\""+domain+"\" AND recordtype = \""+recordtype+"\""
        cur.execute(request)
        rows = cur.fetchall()
        for row in rows:
                #for each host to check
                if str(checked_list) not in row["record"] :
                        logging = {}
                        logging = {'domain':domain, 'record_old': row["record"], 'record_new':str(checked_list),'last_seen':row['updatedate'], 'timestamp':str(epochdate), 'recordtype': row["recordtype"]}
                        #print(json.dumps(logging))
                        record = json.dumps(logging)
                        if es_host != False:
                            es_store_record(es,es_index_name,record)
                        else:
                           print(json.dumps(logging)) 
                        #print("Change detected on \""+domain+"\" - New MX is : \""+str(mx_list)+"\" - Record updated")
                        #Now need to update IP
                        request = "UPDATE domains SET record =\""+str(checked_list)+"\"  WHERE domain = ? AND recordtype = ?"
                        cur.execute(request,(domain,recordtype))
                        request = "UPDATE domains SET updatedate =\""+str(epochdate)+"\"  WHERE domain = ? AND recordtype = ?"
                        cur.execute(request,(domain,recordtype))

#This function resolv the domains to create lists of MX, A or NS records
def listgenerator(domain,recordtype,dns_server):
    listgenerator=list()
    dnsresolver = dns.resolver.Resolver()
    #Change DNS Server for custom DNS server (to avoid using system default one)
    if dns_server != False:
        try:
            dnsserver = list()
            dnsserver.append(dns_server)
            dnsresolver.nameservers = dnsserver
        except Exception as e :
            print(">>>> Problem changing DNS : "+str(e))
    if recordtype == "MX":
        try:
            answersMX = dnsresolver.query(domain,'MX')
            for answer in answersMX: 
                #print(str(answer).split(" ")[1])
                #if it worked
                mx = str(answer).split(" ")[1]
                listgenerator.append(mx)
            listgenerator.sort()
            return (listgenerator)
        except:
            print("error in MX resolver block- maybe no MX record ?")
    if recordtype == "A":
        try:
            answersA = dnsresolver.query(domain, 'A')
            for answer in answersA:		
                ip = str(answer)
                listgenerator.append(ip)
            listgenerator.sort()
            return (listgenerator)
        except:
            print(">>> error in A resolver block - maybe no A record ?")
    if recordtype == "NS":
        try:
            answersNS = dnsresolver.query(domain, 'NS')
            for answer in answersNS:		
                ns = str(answer)
                listgenerator.append(ns)
            listgenerator.sort()
            return (listgenerator)
        except:
            print(">>> error in NS resolver block - maybe no NS record ?")
 
#This function is made to insert domains to check in DB
def firstInsertDB(database_file,domain,recordtype,checked_list):
    epochdate = int(datetime.datetime.now().timestamp())
    connect = lite.connect(database_file)
    with connect:
        connect.row_factory = lite.Row
        cur = connect.cursor()
        request = "SELECT * FROM domains WHERE domain=\""+domain+"\""
        cur.execute(request)
        rows = cur.fetchall()
        #Then add non existent
        if not rows :
            request = "INSERT INTO domains(domain,record,recordtype,updatedate) VALUES(\""+domain+"\",\""+str(checked_list)+"\",\""+recordtype+"\","+str(epochdate)+")"
            try:
                cur.execute(request)
            except Exception as e:
                print(">>> Problem inserting into database : "+str(e))

#This function aims to  create the DB
def createDB(hosts_file,database_file,dns_server):
    connect = lite.connect(database_file)
    with connect:
        connect.row_factory = lite.Row
        cur = connect.cursor()
        try:
            cur.execute("CREATE TABLE domains(id INTEGER PRIMARY KEY, domain TEXT, record TEXT, recordtype TEXT, updatedate TIMESTAMP)")
        except:
            print("Database already created")
        #cur.execute("INSERT INTO domains VALUES(, "domain","ip")
        with open(hosts_file, 'r') as domainFile:
            for domain in domainFile:
                domain = domain[:-1]
                mx_list = listgenerator(domain,"MX",dns_server) 
                ip_list = listgenerator(domain, "A",dns_server)        
                ns_list = listgenerator(domain,"NS",dns_server) 
                firstInsertDB(database_file,domain,"MX",mx_list)
                firstInsertDB(database_file,domain,"A",ip_list)
                firstInsertDB(database_file,domain,"NS",ns_list)
        
            domainFile.close()

#This function is used to launch diffs checks on observed domains. It launches the lists factories and the diffs checks
def checkChange(hosts_file,database_file,es_host,es_port,es_index_name,dns_server):
    with open(hosts_file, 'r') as domainFile:
        for domain in domainFile:
            domain = domain[:-1]
            mx_list = listgenerator(domain,"MX",dns_server)
            checkRecord(database_file,es_host,es_port,es_index_name,domain,mx_list,"MX")
            ip_list = listgenerator(domain, "A",dns_server)
            checkRecord(database_file,es_host,es_port,es_index_name,domain,ip_list,"A")
            ns_list = listgenerator(domain,"NS",dns_server)
            checkRecord(database_file,es_host,es_port,es_index_name,domain,ns_list,"NS")
            

if __name__ == "__main__":
    
    arguments = dict()
    
    parser = optparse.OptionParser()
    parser.add_option("-f", "--host-file", dest = 'hosts_file', help = "Hosts to monitor", metavar = "FILE", default = False)
    parser.add_option("-c", "--create-db-in-file", dest = 'create_db', help = "Create DB in specified file if first run", metavar = "DB", default = False)
    parser.add_option("-b", "--database", dest = 'database', help = "DB file to use for checking", metavar = "DB", default = False)
    parser.add_option("-e", "--elasticsearch-host", dest= 'elasticsearch', help="Precise Elasticsearch host if wanted or don't use this option -", metavar="output", default=False) 
    parser.add_option("-p", "--port", dest = 'port', help = 'Elasticsearch Port', metavar='PORT' ,default = False)
    parser.add_option("-i", "--index-name", dest='index', help='Elasticsearch Index Name. If false default will be domainchecker-YYYY-MM-DD', metavar='INDEX', default = False)
    parser.add_option("-d", "--dns-server", dest="dns", help="Change DNS for resolution. System's one if not used", metavar="DNS", default = False)
    options,args = parser.parse_args()

    if options.hosts_file != False:
        arguments["hosts_file"] = options.hosts_file
    if options.create_db != False:
        arguments["create_db"] = options.create_db
    if options.database != False:
        arguments["database"] = options.database
    if options.elasticsearch != False:
        arguments["elasticsearch"] = options.elasticsearch
    elif options.elasticsearch == False:
        arguments["elasticsearch"] = False
    if options.port != False:
        try:
            arguments["port"] = int(options.port)
        except:
            print("[-] Port is not an integer")
            exit()
    elif options.port == False:
        arguments["port"] = 9200
    if options.index != False:
        arguments["index"] = options.index
    elif options.index == False:
        daytime = datetime.datetime.now().strftime("%Y-%m-%d")
        es_index_name = "domainchecker-"+daytime
        arguments["index"] = es_index_name
    if options.dns != False:
        arguments["dns"] = options.dns
    elif options.dns == False:
        arguments["dns"] = False

    if len(sys.argv)==1:
        parser.print_help()
        exit()
    else:
        if options.create_db != False:
            #createDB(arguments["hosts_file"],arguments["create_db"])
            createDB(arguments["hosts_file"],arguments["create_db"],arguments["dns"])
            exit()
        elif ((options.database != False) and (options.hosts_file != False)):
            checkChange(arguments["hosts_file"],arguments["database"],arguments["elasticsearch"],arguments["port"],arguments["index"],arguments["dns"])
            exit()
        else :
            print("Usage : python3 domainchecker.py [options]")
            print("Usage : python3 domainchecker.py -f hosts.txt -b database.txt")
            print("Please read README.MD if first launch to set databases")
            exit()

