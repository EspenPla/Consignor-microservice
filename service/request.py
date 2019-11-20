import requests
import xmltodict
import json
import sys
from flask import Flask, request, Response
from requests.exceptions import Timeout
from sesamutils import VariablesConfig
import logging
import paste.translogger
from datetime import datetime, timedelta
import os
import cherrypy

app = Flask(__name__)

logger = logging.getLogger("Consignor-Service")

required_env_vars = ["username", "password"]
optional_env_vars = [("LOG_LEVEL", "INFO")]

with open("banner.txt", 'r') as banner:
    for line in banner:
        logger.error(repr(line))  

config = VariablesConfig(required_env_vars, optional_env_vars=optional_env_vars)
if not config.validate():
    sys.exit(1)

url="http://customer-api.consignorportal.com/PortalData/PortalData.svc"
since = "9999-12-31T23:59:59"

def stream_as_json(generator_function):
    first = True
    yield '['
    for item in generator_function:
        if not first:
            yield ','
        else:
            first = False
        yield json.dumps(item)
    yield ']'

@app.route('/test', methods=["POST"])
def postrequest():  
    try:
        entities = request.get_json()
        logger.info("(test) Receiving entities")
    

        if not isinstance(entities,list):
            entities = [entities]
        for entity in entities:
            try:
                referenceNumber = entity['referenceNumber']
                logger.info("(test) fetching data from: " + str(referenceNumber))
            except:
                logger.info(entity)
        return ""  
    except Exception as e: 
        logger.error(f"Something went wrong with the test: {e}")

@app.route("/GetShipmentsByOrderNumber", methods=["POST"])
def GetShipmentsByOrderNumber():
    entities = request.get_json()
    logger.info("Receiving entities")
    

    if not isinstance(entities,list):
        entities = [entities]
    for entity in entities:
        try:
            referenceNumber = entity['referenceNumber']
            logger.info(referenceNumber)
            headers = {'content-type': 'text/xml; charset=utf-8','SOAPAction': 'http://edisoftwebservices.com/IPortalData/GetShipmentsByOrderNumber'}
            body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:edis="http://edisoftwebservices.com/" xmlns:arr="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
    <soapenv:Header/>
    <soapenv:Body>
        <edis:GetShipmentsByOrderNumber>
            <edis:userName>{config.username}</edis:userName>
            <edis:password>{config.password}</edis:password>
            <edis:referenceNumber>{referenceNumber}</edis:referenceNumber>
        </edis:GetShipmentsByOrderNumber>
    </soapenv:Body>
</soapenv:Envelope>"""
            try: 
                r = requests.post(url,data=body,headers=headers)
                logger.info("\n" + body)
                jsonString = json.dumps(xmltodict.parse(r.text, process_namespaces=True,  namespaces={'http://schemas.datacontract.org/2004/07/EdiSoft.Common.Domain.ExportDomain':None}), indent=4)
                jsonload = json.loads(jsonString)
                rmparents = (jsonload['http://schemas.xmlsoap.org/soap/envelope/:Envelope']['http://schemas.xmlsoap.org/soap/envelope/:Body']['http://edisoftwebservices.com/:GetShipmentsByOrderNumberResponse']['http://edisoftwebservices.com/:GetShipmentsByOrderNumberResult']['Shipment'])
                logger.info(rmparents)
            except:
                logger.error("failure :(:(")
            return Response(json.dumps(rmparents), mimetype='application/json')
        except:
            logger.info(entity)
    return ""   

def GetEvents(since=since):    
    try:
        headers = {'content-type': 'text/xml; charset=utf-8','SOAPAction': 'http://edisoftwebservices.com/IPortalData/GetEvents'}
        body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:edis="http://edisoftwebservices.com/" xmlns:arr="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
    <soapenv:Header/>
    <soapenv:Body>
        <edis:GetEvents>
            <edis:userName>{config.username}</edis:userName>
            <edis:password>{config.password}</edis:password>
            <edis:eventDateTimeStart>{since}</edis:eventDateTimeStart>
            <edis:eventDateTimeEnd>9999-12-31T23:59:59</edis:eventDateTimeEnd>
        </edis:GetEvents>
    </soapenv:Body>
</soapenv:Envelope>"""
        try: 
            r = requests.post(url,data=body,headers=headers)
            logger.info("\n" + body)
            jsonString = json.dumps(xmltodict.parse(r.text, process_namespaces=True,  namespaces={'http://schemas.datacontract.org/2004/07/EdiSoft.Common.Domain.ExportDomain':None}), indent=4)
            jsonload = json.loads(jsonString)
            count = 0
            try: 
                rmparents = (jsonload['http://schemas.xmlsoap.org/soap/envelope/:Envelope']['http://schemas.xmlsoap.org/soap/envelope/:Body']['http://edisoftwebservices.com/:GetEventsResponse']['http://edisoftwebservices.com/:GetEventsResult']['Event'])
                try:
                    for item in rmparents:
                        i = dict(item)
                        # i["_id"] = item["Parent"]["OrderNumber"]
                        i["_id"] = item["Parent"]["Barcode"] #not all events have the OrderNumber, to get all Events we´ll use the Barcode
                        i["_updated"] = item["ServerDate"]
                        yield(i)
                        count += 1        
                    logger.info(f"Found {count} new events")                
                except:
                    logger.error("the new events is missing either Barcode/ServerDate.")
            except:
                logger.info("there is no new events")
        except:
            logger.error("failure :(:(")
    except Exception as e:
        logger.info(f"since value: {since}\n error: {e}")


@app.route('/GetEvents')
def entities():
    try: 
        if request.args.get('since') is None:
            delta = datetime.utcnow() + timedelta(minutes=55) #Remember to set this to correct time. Suggestion: last 7 days
            since = delta.isoformat()
            logger.debug(f"since value set from ms(-1 week): {since}")
        else: 
            since = request.args.get('since')
        return Response(stream_as_json(GetEvents(since)), mimetype='application/json')
    except Timeout as e:
        logger.error(f"Timeout issue while fetching entities {e}")
    except ConnectionError as e:
        logger.error(f"ConnectionError issue while fetching entities {e}")
    except Exception as e:
        logger.error(f"Issue while fetching entities: {e}")

if __name__ == '__main__':
    format_string = '%(name)s - %(levelname)s - %(message)s'
    # Log to stdout, change to or add a (Rotating)FileHandler to log to a file
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(logging.Formatter(format_string))
    logger.addHandler(stdout_handler)

    # Comment these two lines if you don't want access request logging
    app.wsgi_app = paste.translogger.TransLogger(app.wsgi_app, logger_name=logger.name,
                                                 setup_console_handler=False)
    app.logger.addHandler(stdout_handler)

    logger.propagate = False
    log_level = logging.getLevelName(os.environ.get('LOG_LEVEL', 'INFO'))  # default log level = INFO
    logger.setLevel(level=log_level)
    cherrypy.tree.graft(app, '/')
    # Set the configuration of the web server to production mode
    cherrypy.config.update({
        'environment': 'production',
        'engine.autoreload_on': False,
        'log.screen': True,
        'server.socket_port': 5000,
        'server.socket_host': '0.0.0.0'
    })

    # Start the CherryPy WSGI web server
    cherrypy.engine.start()
    cherrypy.engine.block()