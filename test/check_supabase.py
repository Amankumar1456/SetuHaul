from dotenv import load_dotenv
load_dotenv()
import os
from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
print("URL:", url)
print("KEY starts with:", key[:20] if key else None)

c = create_client(url, key)
print("Connected OK")
print(c.table("shipments").select("*").limit(1).execute())