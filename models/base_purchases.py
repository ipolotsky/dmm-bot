import collections
import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from firebase_admin.db import Reference
from telegram import TelegramError

from utils import helper


class BasePurchase(ABC):

    def __init__(self):
        self._id = None
        self._data = {}
        self.status = None

    @classmethod
    @abstractmethod
    def ref(cls) -> Reference:
        pass

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, _id: int):
        self._id = _id

    # Currency
    @property
    def currency(self):
        return helper.safe_list_get(self._data, "currency", None)

    @currency.setter
    def currency(self, currency: str):
        self._data["currency"] = currency

    # Total_amount
    @property
    def total_amount(self):
        return helper.safe_list_get(self._data, "total_amount", None)

    @total_amount.setter
    def total_amount(self, total_amount: int):
        self._data["total_amount"] = total_amount

    # Phone_number
    @property
    def phone_number(self):
        return helper.safe_list_get(self._data, "phone_number", None)

    @phone_number.setter
    def phone_number(self, phone_number: str):
        self._data["phone_number"] = phone_number

    # Customer name
    @property
    def customer_name(self):
        return helper.safe_list_get(self._data, "customer_name", None)

    @customer_name.setter
    def customer_name(self, customer_name: str):
        self._data["customer_name"] = customer_name

    # email
    @property
    def email(self):
        return helper.safe_list_get(self._data, "email", None)

    @email.setter
    def email(self, email: str):
        self._data["email"] = email

    # telegram_payment_charge_id
    @property
    def telegram_payment_charge_id(self):
        return helper.safe_list_get(self._data, "telegram_payment_charge_id", None)

    @telegram_payment_charge_id.setter
    def telegram_payment_charge_id(self, telegram_payment_charge_id: str):
        self._data["telegram_payment_charge_id"] = telegram_payment_charge_id

    # provider_payment_charge_id
    @property
    def provider_payment_charge_id(self):
        return helper.safe_list_get(self._data, "provider_payment_charge_id", None)

    @provider_payment_charge_id.setter
    def provider_payment_charge_id(self, provider_payment_charge_id: str):
        self._data["provider_payment_charge_id"] = provider_payment_charge_id

    # created
    @property
    def created(self):
        timestamp = helper.safe_list_get(self._data, "created")
        if timestamp:
            return datetime.fromtimestamp(timestamp).strftime(
                '%Y-%m-%d %H:%M:%S')

    @created.setter
    def created(self, created: float):
        self._data["created"] = created

    def save(self):
        self.ref().child(self._id).update(self._data)

    def tech_data(self):
        return self._data

    # Functions

    def load(self):
        if not self._id:
            raise TelegramError(f"Отсутстует id")

        _data = self.ref().child(str(self._id)).get()
        if not _data:
            raise TelegramError(f"Нет данных по покупке с id: {self._id}")

        self._data = _data

    @classmethod
    def get(cls, _id: str, data=None):
        # if not cls.exists(_id):
        #     raise TelegramError(f"Нет покупки с id {_id}")
        purchase = cls()
        purchase.id = _id
        if data:
            purchase._data = data
        else:
            purchase.load()

        return purchase

    @classmethod
    def exists(cls, _id: str):
        return bool(cls.ref().child(_id).get())

    @classmethod
    def create_new(cls, _id: str):
        if cls.exists(_id):
            raise TelegramError(f"Попытка создать покупку с существующем id {_id}")

        cls.ref().child(_id).update({
            'id': _id,
            'created': datetime.now().timestamp()
        })

        purchase = cls()
        purchase.id = _id
        purchase._data = cls.ref().child(_id).get()
        return purchase

    @classmethod
    def all(cls, sort: str = "created", reverse=True):
        fb_purchases = cls.ref().order_by_child(sort).get() if sort else cls.ref().get()
        fb_purchases = fb_purchases if fb_purchases else collections.OrderedDict()

        fb_purchases = collections.OrderedDict(reversed(list(fb_purchases.items()))) if reverse else fb_purchases
        return [cls.get(fb_purchase, fb_purchases[fb_purchase]) for fb_purchase in fb_purchases]