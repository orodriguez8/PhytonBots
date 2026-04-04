
import requests
import json

try:
    print("Requesting API...")
    r = requests.get('http://127.0.0.1:5000/api/run')
    print(f"Status Code: {r.status_code}")
    if r.status_code == 500:
        print("Response Text:")
        print(r.text)
    else:
        # Success
        print("JSON length:", len(r.text))
        res = r.json()
        print("Success! Keys in response:", res.keys())
except Exception as e:
    print(f"Connection failed: {e}")
