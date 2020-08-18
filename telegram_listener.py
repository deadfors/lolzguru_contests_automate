from telethon import TelegramClient
from userdata import API_ID, API_HASH

client = TelegramClient('session_name', API_ID, API_HASH)


def get_last_message():
    for message in client.iter_messages('lolzteam_alert_bot'):
        return message.text.split()[6]
