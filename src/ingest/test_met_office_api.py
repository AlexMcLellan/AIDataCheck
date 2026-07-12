import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('MET_OFFICE_CLIENT_ID')

latitude = 51.5
longitude = -1.0

url = f"https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest?lat={latitude}&lon={longitude}"

print(f"Trying {url}...")
try:
    res = requests.get(url, headers={"apikey": api_key, "accept": "application/json"})
    print(res.status_code)
    if res.status_code == 200:
        print("SUCCESS! Data:")
        data = res.json()
        print(data)
        if data:
            geohash = data[0]['geohash']
            obs_url = f"https://data.hub.api.metoffice.gov.uk/observation-land/1/{geohash}"
            print(f"\nTrying {obs_url}...")
            obs_res = requests.get(obs_url, headers={"apikey": api_key, "accept": "application/json"})
            print(obs_res.status_code)
            if obs_res.status_code == 200:
                print(obs_res.json())
            else:
                print(obs_res.text[:500])
    else:
        print(res.text[:500])
except Exception as e:
    print(e)

# Try with apikey vs x-ibm-client-id
try:
    res = requests.get(url, headers={"x-ibm-client-id": api_key, "accept": "application/json"})
    print("With x-ibm-client-id:", res.status_code)
    if res.status_code == 200:
        print("SUCCESS! Data:")
        print(res.json())
    else:
        print(res.text[:500])
except Exception as e:
    print(e)
