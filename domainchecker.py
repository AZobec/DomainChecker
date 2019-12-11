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

def store_record(elastic_object, index_name, record):
    try:
        outcome = elastic_object.index(index=index_name, doc_type='_doc', body=record)
    except Exception as ex:
        print('Error in indexing data')
        print(str(ex))

def create_index(es_object, index_name):
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
                            
def createDB(hosts_file,database_file):
    epochdate = int(datetime.datetime.now().timestamp())
    connect = lite.connect(database_file)
    ip_list = list()
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
                ip_list=list()
                mx_list=list()
                ns_list=list()
                domain = domain[:-1]
                #For A records
                try:
                    answersA = dns.resolver.query(domain,'A')
                    for answer in answersA: 
                    #if it worked
                        ip = str(answer)
                        ip_list.append(ip)
                except:
                    print("error in A resolver block - maybe no A record?")
                if  ip_list:
                    #Before need to check if already exists
                    request = "SELECT * FROM domains WHERE domain=\""+domain+"\""
                    cur.execute(request)
                    rows = cur.fetchall()
                    #Then add non existent
                    if not rows :
                        request = "INSERT INTO domains(domain,record,recordtype,updatedate) VALUES(\""+domain+"\",\""+str(ip_list)+"\",\"A\","+str(epochdate)+")"
                        try:
                            cur.execute(request)
                        except:
                            print("Problem executing Query")
                
                try:
                    answersMX = dns.resolver.query(domain,'MX')
                    for answer in answersMX: 
                        #print(str(answer).split(" ")[1])
                        #if it worked
                        mx = str(answer).split(" ")[1]
                        mx_list.append(mx)
                        mx_list.sort()
                except:
                    print("error in MX resolver block - maybe no MX record ?")
                if mx_list:
                    #Before need to check if already exists
                    request = "SELECT * FROM domains WHERE domain=\""+domain+"\""
                    cur.execute(request)
                    rows = cur.fetchall()
                    #Then add non existent
                    if rows :
                        request = "INSERT INTO domains(domain,record,recordtype,updatedate) VALUES(\""+domain+"\",\""+str(mx_list)+"\",\"MX\","+str(epochdate)+")"
                        try:
                            cur.execute(request)
                        except:
                            print("Problem executing Query")
                #For NS records
                try:
                    answersNS = dns.resolver.query(domain,'NS')
                    for answer in answersNS: 
                    #if it worked
                        ns = str(answer)
                        print(domain+" "+ns)
                        ns_list.append(ns)
                        ns_list.sort()
                except:
                    print("error in NS resolver block - maybe no NS record?")
                if ns_list:
                    #Before need to check if already exists
                    request = "SELECT * FROM domains WHERE domain=\""+domain+"\""
                    cur.execute(request)
                    rows = cur.fetchall()
                    #Then add non existent
                    if rows :
                        request = "INSERT INTO domains(domain,record,recordtype,updatedate) VALUES(\""+domain+"\",\""+str(ns_list)+"\",\"NS\","+str(epochdate)+")"
                        try:
                            cur.execute(request)
                        except:
                            print("Problem executing Query")
                
            domainFile.close()							

def checkChange(hosts_file,database_file,es_host):
    if es_host != False:
        es = Elasticsearch([{'host': es_host, 'port': 9200}])
        daytime = datetime.datetime.now().strftime("%Y-%m-%d")
        es_index_name = "domainchecker-"+daytime
        create_index(es,es_index_name)
    epochdate = int(datetime.datetime.now().timestamp())
    connect = lite.connect(database_file)
    with connect:
        connect.row_factory = lite.Row
        cur = connect.cursor()
        with open(hosts_file, 'r') as domainFile:
            for domain in domainFile:
                domain = domain[:-1]
                ip_list=list()
                mx_list=list()
                ns_list=list()
                #For A records 
                try:
                    answersA = dns.resolver.query(domain, 'A')
                    for answer in answersA:		
                        ip = str(answer)
                        ip_list.append(ip)
                except:
                    print("error in A resolver block - maybe no A record ?")
                if ip_list :
                        #Before need to check if  exists
                        request = "SELECT domain,record,recordtype,updatedate FROM domains WHERE domain=\""+domain+"\" AND recordtype = \"A\""
                        cur.execute(request)
                        rows = cur.fetchall()
                        for row in rows:
                                #for each host to check
                                #print ("{} {} {} {}".format(row["domain"], row["record"], row["recordtype"], row["updatedate"]))
                                if str(ip_list) not in row["record"] :
                                        logging = {}
                                        logging = {'domain':domain, 'record_old': row["record"], 'record_new':str(ip_list),'last_seen':row['updatedate'], 'timestamp':str(epochdate), 'recordtype': row["recordtype"]}
                                        #print(json.dumps(logging))
                                        record = json.dumps(logging)
                                        if es_host != False:
                                            store_record(es,es_index_name,record)
                                        #print("Change detected on \""+domain+"\" - New IP is : \""+str(ip_list)+"\" - Record updated")
                                        #Now need to update IP
                                        request = "UPDATE domains SET record =\""+str(ip_list)+"\"  WHERE domain = ? AND recordtype = ?"
                                        cur.execute(request,(domain,"A"))
                                        request = "UPDATE domains SET updatedate =\""+str(epochdate)+"\"  WHERE domain = ? AND recordtype = ?"
                                        cur.execute(request,(domain,"A"))
                try:
                    answersMX = dns.resolver.query(domain,'MX')
                    for answer in answersMX: 
                        #print(str(answer).split(" ")[1])
                        #if it worked
                        mx = str(answer).split(" ")[1]
                        mx_list.append(mx)
                        mx_list.sort()
                except:
                    print("error in MX resolver block- maybe no MX record ?")
                if mx_list :
                        #Before need to check if  exists
                        request = "SELECT domain,record,recordtype,updatedate FROM domains WHERE domain=\""+domain+"\" AND recordtype = \"MX\""
                        cur.execute(request)
                        rows = cur.fetchall()
                        for row in rows:
                                #for each host to check
                                #print ("{} {} {} {}".format(row["domain"], row["record"], row["recordtype"], row["updatedate"]))
                                if str(mx_list) not in row["record"] :
                                        logging = {}
                                        logging = {'domain':domain, 'record_old': row["record"], 'record_new':str(mx_list),'last_seen':row['updatedate'], 'timestamp':str(epochdate), 'recordtype': row["recordtype"]}
                                        #print(json.dumps(logging))
                                        record = json.dumps(logging)
                                        if es_host != False:
                                            store_record(es,es_index_name,record)
                                        #print("Change detected on \""+domain+"\" - New MX is : \""+str(mx_list)+"\" - Record updated")
                                        #Now need to update IP
                                        request = "UPDATE domains SET record =\""+str(mx_list)+"\"  WHERE domain = ? AND recordtype = ?"
                                        cur.execute(request,(domain,"MX"))
                                        request = "UPDATE domains SET updatedate =\""+str(epochdate)+"\"  WHERE domain = ? AND recordtype = ?"
                                        cur.execute(request,(domain,"MX"))
                #For NS records
                try:
                    answersNS = dns.resolver.query(domain,'NS')
                    for answer in answersNS: 
                    #if it worked
                        ns = str(answer)
                        ns_list.append(ns)
                        ns_list.sort()
                except:
                    print("error in NS resolver block - maybe no NS record ?")
                if ns_list :
                        #Before need to check if  exists
                        request = "SELECT domain,record,recordtype,updatedate FROM domains WHERE domain=\""+domain+"\" AND recordtype = \"NS\""
                        cur.execute(request)
                        rows = cur.fetchall()
                        for row in rows:
                                #for each host to check
                                #print ("{} {} {} {}".format(row["domain"], row["record"], row["recordtype"], row["updatedate"]))
                                if str(ns_list) not in row["record"] :
                                        logging = {}
                                        logging = {'domain':domain, 'record_old': row["record"], 'record_new':str(ns_list),'last_seen':row['updatedate'], 'timestamp':str(epochdate), 'recordtype': row["recordtype"]}
                                        #print(json.dumps(logging))
                                        record = json.dumps(logging)
                                        if es_host != False:
                                            store_record(es,es_index_name,record)
                                        #print("Change detected on \""+domain+"\" - New IP is : \""+str(ns_list)+"\" - Record updated")
                                        #Now need to update IP
                                        request = "UPDATE domains SET record =\""+str(ns_list)+"\"  WHERE domain = ? AND recordtype = ?"
                                        cur.execute(request,(domain,"NS"))
                                        request = "UPDATE domains SET updatedate =\""+str(epochdate)+"\"  WHERE domain = ? AND recordtype = ?"
                                        cur.execute(request,(domain,"NS"))
            domainFile.close()



if __name__ == "__main__":
    
    arguments = dict()
    

    parser = optparse.OptionParser()
    parser.add_option("-f", "--host-file", dest = 'hosts_file', help = "Hosts to monitor", metavar = "FILE", default = False)
    parser.add_option("-c", "--create-db-in-file", dest = 'create_db', help = "Create DB in specified file if first run", metavar = "DB", default = False)
    parser.add_option("-b", "--database", dest = 'database', help = "DB file to use for checking", metavar = "DB", default = False)
    parser.add_option("-o", "--output", dest= 'output', help="Precise Elasticsearch host if wanted or don't use this option -", metavar="output", default=False) 

    options,args = parser.parse_args()

    if options.hosts_file != False:
        arguments["hosts_file"] = options.hosts_file
    if options.create_db != False:
        arguments["create_db"] = options.create_db
    if options.database != False:
        arguments["database"] = options.database
    if options.output != False:
        arguments["output"] = options.output
    elif options.output == False:
        arguments["output"] = False

    if len(sys.argv)==1:
        parser.print_help()
        exit()
    else:
        if options.create_db != False:
            createDB(arguments["hosts_file"],arguments["create_db"])
            exit()
        elif ((options.database != False) and (options.hosts_file != False)):
            checkChange(arguments["hosts_file"],arguments["database"],arguments["output"])
            exit()
        else :
            print("Usage : python3 domainchecker.py [options]")
            print("Usage : python3 domainchecker.py -f hosts.txt -b database.txt")
            print("Please read README.MD if first launch to set databases")
            exit()

