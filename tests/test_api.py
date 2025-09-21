import requests
import json

url = "http://localhost:8001/chat"
payload = {"question": "Lãi suất tiết kiệm VietComBank hiện nay là bao nhiêu?"}
headers = {"Content-Type": "application/json"}

response = requests.post(url, json=payload, headers=headers)
print("Status code:", response.status_code)
try:
    print("Response:", json.dumps(response.json(), indent=2, ensure_ascii=False))
except:
    print("Raw response:", response.text)