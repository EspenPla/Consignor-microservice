import requests
import xmltodict
import json
import sys
from flask import Flask, request, Response
from sesamutils import VariablesConfig
import logging
import paste.translogger
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

headers = {'content-type': 'text/xml; charset=utf-8','SOAPAction': 'http://edisoftwebservices.com/IPortalData/GetShipmentsByOrderNumber'}
url="http://customer-api.consignorportal.com/PortalData/PortalData.svc"

@app.route('/getShipment')
def postrequest():  #This is not in use for now
    try:
        if request.args.get('ref') is None:
            logger.info("referenceNumber not found")
            referenceNumber = 12345
        else:
            referenceNumber = request.args.get("ref")
            logger.info(f"referenceNumber {referenceNumber} is sent from Sesam")
    except Exception as e:
        logger.error(f"Issue: {e}")

    #a:Shipment
    r = requests.post(url,data=body,headers=headers)
    jsonString = json.dumps(xmltodict.parse(r.text, process_namespaces=True,  namespaces={'http://schemas.datacontract.org/2004/07/EdiSoft.Common.Domain.ExportDomain':None}), indent=4)
    jsonload = json.loads(jsonString)
    rmparents = (jsonload['http://schemas.xmlsoap.org/soap/envelope/:Envelope']['http://schemas.xmlsoap.org/soap/envelope/:Body']['http://edisoftwebservices.com/:GetShipmentsByOrderNumberResponse']['http://edisoftwebservices.com/:GetShipmentsByOrderNumberResult']['Shipment'])

    # result = json.dumps(rmparents)
    return Response(json.dumps(rmparents), mimetype='application/json')

@app.route("/ref", methods=[ "POST"])
def postreceiver():
    entities = request.get_json()
    logger.info("Receiving entities")
    
    response_list = []
    statuscode = None
    if not isinstance(entities,list):
        entities = [entities]
    for entity in entities:
        try:
            referenceNumber = entity['referenceNumber']
            logger.info(referenceNumber)
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
                logger.info(body)
                jsonString = json.dumps(xmltodict.parse(r.text, process_namespaces=True,  namespaces={'http://schemas.datacontract.org/2004/07/EdiSoft.Common.Domain.ExportDomain':None}), indent=4)
                jsonload = json.loads(jsonString)
                rmparents = (jsonload['http://schemas.xmlsoap.org/soap/envelope/:Envelope']['http://schemas.xmlsoap.org/soap/envelope/:Body']['http://edisoftwebservices.com/:GetShipmentsByOrderNumberResponse']['http://edisoftwebservices.com/:GetShipmentsByOrderNumberResult']['Shipment'])
                logger.info(rmparents)
            except:
                logger.info("failure :(:(")
            return Response(json.dumps(rmparents), mimetype='application/json')
        except:
            logger.info(entity)


    return ""   


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