import base64
import json
from dotenv import load_dotenv
import os

load_dotenv()
key = os.getenv("SUPABASE_KEY")

payload = key.split(".")[1]
payload += "=" * (-len(payload) % 4)
print(json.loads(base64.urlsafe_b64decode(payload)))