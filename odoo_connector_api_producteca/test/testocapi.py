
import requests
import json
import sys
import pprint
pp = pprint.PrettyPrinter(indent=4)

access_token = False
if len(sys.argv)<2:
    print("Need at least one argument, run like this: python3 testocapi.py https://www.mysite.com producteca")

baseurl = sys.argv[1]
connector = sys.argv[2]
client_id = sys.argv[3]
secret_key = sys.argv[4]
sale_json_file = sys.argv[5]
tests = sys.argv[6] or "auth,catalog,pricestock,pricelist,sales"

_url = baseurl+"/ocapi/"+connector
access_token = None

if 1==1 or "auth" in tests:
    params = {
        'params': {
            'client_id': client_id,
            'secret_key': secret_key
        }
    }
    url = _url+"/auth"
    print(url)
    print(params)
    #headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    r = requests.post(url=url, json=dict(params))
    print(r.content)

    rjson = r.json()
    #print(rjson)
    pp.pprint(rjson)

    if "result" in rjson and rjson["result"]:
        result = rjson["result"][0]
        if "access_token" in result:
            access_token = result["access_token"]

    if not access_token:
        exit(1)

#################################################################
if "cataog" in tests:

    params = {
        'params': {
            'access_token': access_token,
        }
    }
    url = _url+"/catalog"
    print(url)
    print(params)

    r = requests.post(url=url, json=dict(params))
    print(r.content)

    rjson = r.json()
    #print(rjson)
    pp.pprint(rjson)

#################################################################
if "pricestock" in tests:
    params = {
        'params': {
            'access_token': access_token,
        }
    }
    url = _url+"/pricestock"
    print(url)
    print(params)

    r = requests.post(url=url, json=dict(params))
    print(r.content)

    rjson = r.json()
    #print(rjson)
    pp.pprint(rjson)

#################################################################
if "pricelist" in tests:
    params = {
        'params': {
            'access_token': access_token,
        }
    }
    url = _url+"/pricelist"
    print(url)
    print(params)

    r = requests.post(url=url, json=dict(params))
    print(r.content)

    rjson = r.json()
    #print(rjson)
    pp.pprint(rjson)

#################################################################
if "stock" in tests:
    params = {
        'params': {
            'access_token': access_token,
        }
    }
    url = _url+"/stock"
    print(url)
    print(params)

    r = requests.post(url=url, json=dict(params))
    print(r.content)

    rjson = r.json()
    #print(rjson)
    pp.pprint(rjson)

#################################################################

if "sales" in tests:
    import json
    data = []
    with open(sale_json_file) as json_file:
        data = json.load(json_file)

    pp.pprint(data)

    params = {
        'params': {
            'access_token': access_token,
            'sales': [data],
        }
    }
    url = _url+"/sales"
    print(url)
    print(params)

    r = requests.post(url=url, json=dict(params))
    print(r.content)

    rjson = r.json()
    #print(rjson)
    pp.pprint(rjson)
