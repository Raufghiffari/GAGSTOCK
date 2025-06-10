from telethon import TelegramClient
from fuzzywuzzy import fuzz
import firebase_admin
from firebase_admin import credentials, db
import asyncio
import re
import logging
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
phone = os.getenv('PHONE')
group_id = int(os.getenv('GROUP_ID'))

important_gear = os.getenv('GEAR_TRIGGER', '').split(',')
important_seeds = os.getenv('SEED_TRIGGER', '').split(',')

# Inisialisasi Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")  # ← Unduh dari Firebase Console
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://gagstock-default-rtdb.firebaseio.com/'  # Ganti dengan Firebase kamu
})

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

client = TelegramClient('session', api_id, api_hash)
last_message_id = None

def match_item(item, target_list, threshold=80):
    for target in target_list:
        if fuzz.partial_ratio(item.lower(), target.lower()) >= threshold:
            return target
    return None

def parse_message(text):
    logging.info("🔍 Memindai pesan...")
    seeds_section = re.search(r"(?i)seeds stock([\s\S]+?)(\n\n|⚙️|🥚|🐝)", text)
    gear_section = re.search(r"(?i)gear stock([\s\S]+?)(\n\n|🌱|🥚|🐝)", text)

    found_seeds = []
    found_gear = []

    if seeds_section:
        seed_lines = seeds_section.group(1).strip().split("\n")
        for line in seed_lines:
            cleaned = line.lstrip("-").strip()
            name = cleaned.split("x")[0].strip()
            if match_item(name, important_seeds):
                found_seeds.append(cleaned)

    if gear_section:
        gear_lines = gear_section.group(1).strip().split("\n")
        for line in gear_lines:
            cleaned = line.lstrip("-").strip()
            name = cleaned.split("x")[0].strip()
            if match_item(name, important_gear):
                found_gear.append(cleaned)

    return found_gear, found_seeds

def send_to_firebase(gear, seeds):
    data = {
        'gear': gear,
        'seeds': seeds
    }
    try:
        db.reference('/grow_updates/latest').set(data)
        logging.info(f"✅ Data dikirim ke Firebase: {data}")
    except Exception as e:
        logging.error(f"❌ Gagal kirim ke Firebase: {e}")

async def auto_check():
    global last_message_id
    logging.info(f"📡 Memantau grup: {group_id}")
    while True:
        try:
            messages = await client.get_messages(group_id, limit=1)
            if messages:
                msg = messages[0]
                if msg.id != last_message_id:
                    logging.info(f"📥 Pesan baru (ID: {msg.id})")
                    gear, seeds = parse_message(msg.text)
                    if gear or seeds:
                        send_to_firebase(gear, seeds)
                    else:
                        logging.info("🟡 Tidak ada item penting ditemukan.")
                    last_message_id = msg.id
        except Exception as e:
            logging.error(f"❌ Error saat membaca pesan: {e}")
        await asyncio.sleep(5)

async def main():
    await client.start(phone)
    logging.info("✅ Login Telegram berhasil.")
    await auto_check()

client.loop.run_until_complete(main())
