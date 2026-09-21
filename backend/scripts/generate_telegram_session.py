import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

if not API_ID or not API_HASH:
    print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in backend/.env")
    exit(1)

print("Starting Telegram Client...")
print("If this is your first time, you will be prompted to enter your phone number and the login code sent to your Telegram app.")

with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
    session_string = client.session.save()
    print("\n" + "="*50)
    print("SUCCESS! Here is your TELEGRAM_SESSION string:")
    print("="*50 + "\n")
    print(session_string)
    print("\n" + "="*50)
    print("Copy the string above and paste it into your backend/.env file like this:")
    print(f"TELEGRAM_SESSION={session_string[:15]}...")
    print("="*50)
