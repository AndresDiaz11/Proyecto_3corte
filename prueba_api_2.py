import os, requests
from dotenv import load_dotenv
load_dotenv()
k = os.environ.get("GEMINI_API_KEY")
print(repr(k))  # mira que no tenga espacios o comillas
r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                headers={"x-goog-api-key": k})
print(r.status_code)