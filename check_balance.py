import os
from dotenv import load_dotenv
import requests  # Install if needed: pip install requests python-dotenv

load_dotenv('secure_key.env')
address = os.getenv('ADDRESS')
if not address:
    raise ValueError("ADDRESS not found in env")

response = requests.get(f"http://localhost:5000/balance?address={address}")
print(response.json())
