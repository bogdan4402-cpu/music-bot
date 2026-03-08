import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN  = os.environ["BOT_TOKEN"]
DB_PATH    = os.environ.get("DB_PATH", "music.db")
ADMIN_ID   = 1106966008
