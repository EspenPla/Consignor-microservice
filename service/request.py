import requests
import xmltodict
import json
import sys
from flask import Flask, request, Response
from requests.exceptions import Timeout
from sesamutils import VariablesConfig, sesam_logger
import logging
from datetime import datetime, timedelta
import os
from sesamutils.flask import serve

app = Flask(__name__)

required_env_vars = ["username", "password"]
optional_env_vars = [("LOG_LEVEL", "INFO")]

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

@app.route("/GetShipmentsByOrderNumber", methods=["POST"])
def GetShipmentsByOrderNumber():
    entities = request.get_json()
    logger.info("Receiving entities")
    

    if not isinstance(entities,list):
        entities = [entities]
    for entity in entities:
        try:
            referenceNumber = entity['referenceNumber']
            # logger.info(referenceNumber)
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
                # logger.info("\n" + body)
                jsonString = json.dumps(xmltodict.parse(r.text, process_namespaces=True,  namespaces={'http://schemas.datacontract.org/2004/07/EdiSoft.Common.Domain.ExportDomain':None}), indent=4)
                jsonload = json.loads(jsonString)
                rmparents = (jsonload['http://schemas.xmlsoap.org/soap/envelope/:Envelope']['http://schemas.xmlsoap.org/soap/envelope/:Body']['http://edisoftwebservices.com/:GetShipmentsByOrderNumberResponse']['http://edisoftwebservices.com/:GetShipmentsByOrderNumberResult']['Shipment'])
                # logger.info(rmparents)
            except Exception as e :
                logger.error("failure, error:")
                logger.error(e)
            return Response(json.dumps(rmparents), mimetype='application/json')
        except:
            logger.info(entity)
    return ""   

def GetShipmentsByDateRange(since=since): 
    try:
        headers = {'content-type': 'text/xml; charset=utf-8','SOAPAction': 'http://edisoftwebservices.com/IPortalData/GetShipmentsByDateRange'}
        pageIndex = 0
        totalCount = 0
        # delta = datetime.now() - timedelta(minutes=5)
        # since = delta.isoformat()
        # since = "2019-11-21T11:33:00.000"
        theend = datetime.now()
        theend = theend.isoformat()
        logger.info("since: " + since)
        logger.info("end: " + theend)

        try: 
            while True:
                body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:edis="http://edisoftwebservices.com/" xmlns:arr="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
            <soapenv:Header/>
            <soapenv:Body>
                <edis:GetShipmentsByDateRange>
                    <edis:userName>{config.username}</edis:userName>
                    <edis:password>{config.password}</edis:password>
                    <edis:startDateTime>{since}</edis:startDateTime>
                    <edis:endDateTime>{theend}</edis:endDateTime>
                    <edis:pageIndex>{pageIndex}</edis:pageIndex>
                </edis:GetShipmentsByDateRange>
            </soapenv:Body>
        </soapenv:Envelope>"""
                r = requests.post(url,data=body,headers=headers)
                jsonString = json.dumps(xmltodict.parse(r.text, process_namespaces=True,  namespaces={'http://schemas.datacontract.org/2004/07/EdiSoft.Common.Domain.ExportDomain':None}), indent=4)
                jsonload = json.loads(jsonString)
                logger.info(f"GetShipmentsByDateRange request sent!\nstartDateTime: {since}\npageIndex: {pageIndex}")
                pageIndex += 1
                count = 0
                try: 
                    rmparents = (jsonload['http://schemas.xmlsoap.org/soap/envelope/:Envelope']['http://schemas.xmlsoap.org/soap/envelope/:Body']['http://edisoftwebservices.com/:GetShipmentsByDateRangeResponse']['http://edisoftwebservices.com/:GetShipmentsByDateRangeResult']['Shipment'])
                    try:
                        for item in rmparents:
                            i = dict(item)
                            i["_id"] = item["Number"] #not all events have the OrderNumber, to get all Events we´ll use the Barcode
                            submitdate = item["SubmitDate"]
                            i["_updated"] = submitdate[:-6]
                            #to_transit_datetime(datetime.datetime.fromtimestamp(i[date] / 1e3))
                            # i["last event"] = item["Events"]["Event"][-1]["ServerDate"]
                            count += 1
                            totalCount += 1
                            yield(i)
                        logger.info(f"Found {count} new shipments.")
                    except:
                        logger.error("the new events is missing either Barcode/ServerDate.")
                except:
                    break
                    # logger.info("there is no new shipments")
                
        except:
            logger.info("request failure :(:(")
        logger.info(f"Found totally {totalCount} new shipments. Total pages: {pageIndex}")
    except Exception as e:
        logger.info(f"since value: {since}\n error: {e}")
        logger.info(f"end value: {theend}\n error: {e}")

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
            logger.info(f"Sending request...\n----------eventDateTimeStart: {since}")
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


@app.route('/<method>')
def entities(method):
    try: 
        if (method == "GetShipmentsByDateRange"):
            method = GetShipmentsByDateRange
        elif (method == "GetEvents"): 
            method = GetEvents
        else:
            logger.error(f"Method ({method}) not found!")
            return (f"Method ({method}) not found!")

        if request.args.get('since') is None:
            delta = datetime.now() - timedelta(days=1) #Decides how far back you´ll go if no since value is sent from sesam.
            since = delta.isoformat()
            logger.debug(f"since value set from ms(-1 week): {since}")
        else: 
            since = request.args.get('since')
        return Response(stream_as_json(method(since)), mimetype='application/json')
    except Timeout as e:
        logger.error(f"Timeout issue while fetching entities {e}")
    except ConnectionError as e:
        logger.error(f"ConnectionError issue while fetching entities {e}")
    except Exception as e:
        logger.error(f"Issue while fetching entities: {e}")

if __name__ == '__main__':

    logger = sesam_logger('Consignor Service')

    with open("banner.txt", 'r', encoding='utf-8') as banner:
        logger.info('Initialisation...  v.0.03\n\n' + banner.read() + '\n')
    try:
        logger.info("LOG_LEVEL = %s" % logger.level)
    except: 
        logger.error("Could not print log level")

    logger.info("Starting Cherrypy...")
    serve(app)