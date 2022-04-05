import firebase_admin
from firebase_admin import db
from telegram.ext import BasePersistence
from ast import literal_eval
from collections import defaultdict
from typing import Dict
from settings import Settings

cred = firebase_admin.credentials.Certificate(Settings.fb_creds())
firebase_admin.initialize_app(cred, {"databaseURL": Settings.db_url()})


class FirebasePersistence(BasePersistence):

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(FirebasePersistence, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        # cred = firebase_admin.credentials.Certificate(credentials)
        # self.app = app
        self.fb_user_data = db.reference("user_data")
        self.users = db.reference("users")

        self.purchases = db.reference("ticket_purchases")
        self.tickets = db.reference("tickets")

        self.settings = db.reference("settings")
        self.fb_chat_data = db.reference("chat_data")
        self.fb_bot_data = db.reference("bot_data")
        self.fb_conversations = db.reference("conversations")
        super().__init__(
            store_user_data=False,
            store_chat_data=False,
            store_bot_data=False,
        )

    def get_user_data(self):
        data = self.fb_user_data.get() or {}
        output = self.convert_keys(data)
        return defaultdict(dict, output)

    def get_chat_data(self):
        data = self.fb_chat_data.get() or {}
        output = self.convert_keys(data)
        return defaultdict(dict, output)

    def get_bot_data(self):
        return defaultdict(dict, self.fb_bot_data.get() or {})

    def get_conversations(self, name):
        res = self.fb_conversations.child(name).get() or {}
        res = {literal_eval(k): v for k, v in res.items()}
        return res

    def update_conversation(self, name, key, new_state):
        if new_state:
            self.fb_conversations.child(name).child(str(key)).set(new_state)
        else:
            self.fb_conversations.child(name).child(str(key)).delete()

    def update_user_data(self, user_id, data):
        self.fb_user_data.child(str(user_id)).update(data)

    def update_chat_data(self, chat_id, data):
        self.fb_chat_data.child(str(chat_id)).update(data)

    def update_bot_data(self, data):
        self.fb_bot_data = data

    @staticmethod
    def convert_keys(data: Dict):
        output = {}
        for k, v in data.items():
            if k.isdigit():
                output[int(k)] = v
            else:
                output[k] = v
        return output
