import json

import requests
from django.http import HttpResponse
from utils.responseContentUtil import *

AI_BACKEND = "http://127.0.0.1:7551/{}/intelligent/"


def getUnitSearchData(param, ):
    url = AI_BACKEND.format("unit-management-v2") + "unit-data-search"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps(param), headers=headers)
    return response.json()

def getUnitDimensionSearchData():
    url = AI_BACKEND.format("unit-management-v2") + "unit-dimension-search"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps({}), headers=headers)
    return response.json()

def getBasicUnitSearchData():
    url = AI_BACKEND.format("unit-management-v2") + "basic-unit-search"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps({}), headers=headers)
    return response.json()