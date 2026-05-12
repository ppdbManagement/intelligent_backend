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

def getCompoundSearchData(query,query_type):
    url = AI_BACKEND.format("basic_component_related_management") + "component-uuid-search"
    headers = {'Content-Type': 'application/json'}
    data = {
        "query": query,
        "query_type": query_type
    }
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return response.json()

def getPropertySearchByUnit(query):
    url = AI_BACKEND.format("basic_component_related_management") + "property-search-by-unit"
    headers = {'Content-Type': 'application/json'}
    data = {
        "query": query
    }
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return response.json()

def getVariableSearchByUnit(query):
    url = AI_BACKEND.format("basic_component_related_management") + "variable-search-by-unit"
    headers = {'Content-Type': 'application/json'}
    data = {
        "query": query
    }
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return response.json()

def getPhaseSearch():
    url = AI_BACKEND.format("basic_component_related_management") + "phase-search"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps({}), headers=headers)
    return response.json()

def getAlignedShowNameByUUID(query):
    url = AI_BACKEND.format("basic_component_related_management") + "aligned-show-name-by-uuid"
    headers = {'Content-Type': 'application/json'}
    data = {
        "query": query
    }
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return response.json()

def dataStotagePost(data):
    url = AI_BACKEND.format("literature") + "data-storage-post"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return response.json()

def literatureDatasetGet(query):
    url = AI_BACKEND.format("literature") + "get-literature-dataset"
    headers = {'Content-Type': 'application/json'}
    data = {
        "query": query
    }
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return response.json()