import os
import json
from utils import helper


class Settings:

    IS_TEST = False

    @staticmethod
    def max_invites():
        from persistence.firebase_persistence import FirebasePersistence
        settings = FirebasePersistence().settings.get()
        return helper.safe_list_get(settings, "max_invites", 5)

    @staticmethod
    def enable_merch():
        from persistence.firebase_persistence import FirebasePersistence
        settings = FirebasePersistence().settings.get()
        return helper.safe_list_get(settings, "enable_merch", False)

    @staticmethod
    def fb_creds():
        with open(f"FB_CREDS{'_TEST' if Settings.IS_TEST else ''}.json") as file:
            return json.load(file)

    @staticmethod
    def db_url():
        return os.environ[f"FB_DB_URL{'_TEST' if Settings.IS_TEST else ''}"]

    @staticmethod
    def bot_token():
        return os.environ[f"BOT_TOKEN{'_TEST' if Settings.IS_TEST else ''}"]

    @staticmethod
    def provider_token():
        return os.environ[f"BOT_PAYMENT_PROVIDER_TOKEN{'_TEST' if Settings.IS_TEST else ''}"]

    @staticmethod
    def bot_name() -> str:
        return "dmmbot" if Settings.IS_TEST else "dmmbot"
