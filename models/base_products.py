import collections
from abc import ABC, abstractmethod
from firebase_admin.db import Reference
from telegram import TelegramError
from utils import helper


class BaseProduct(ABC):

    def __init__(self):
        self._id = None
        self._data = {}

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

    @property
    def photo(self):
        return helper.safe_list_get(self._data, "photo")

    @photo.setter
    def photo(self, photo: str):
        raise TelegramError("Photo is being changed only via Firebase store")

    @property
    def description(self):
        return helper.safe_list_get(self._data, "description")

    @description.setter
    def description(self, description: str):
        raise TelegramError("Description is being changed only via Firebase store")

    @property
    def price(self):
        return helper.safe_list_get(self._data, "price")

    @price.setter
    def price(self, price: int):
        raise TelegramError("Price is being changed only via Firebase store")

    @property
    def order(self):
        return helper.safe_list_get(self._data, "order")

    @order.setter
    def order(self, order: int):
        raise TelegramError("Order is being changed only via Firebase store")

    @property
    def type(self):
        return helper.safe_list_get(self._data, "type")

    @type.setter
    def type(self, _type: str):
        raise TelegramError("Type is being changed only via Firebase store")

    def save(self):
        self.ref().child(self._id).update(self._data)

    def tech_data(self):
        return self._data


    # Functions

    @type.setter
    def type(self, _type: str):
        raise TelegramError("Type is being changed only via Firebase store")

    def load(self):
        if not self._id:
            raise TelegramError(f"Отсутстует id товара")

        _data = self.ref().child(str(self._id)).get()
        if not _data:
            raise TelegramError(f"Нет данных по товару с id: {self._id}")

        self._data = _data

    def pretty_html(self, index: int = None):
        return "<b>{}{}</b>\n{}".format(str(index) + ". " if index else "", self.id, self.description)

    @classmethod
    def exists(cls, _id: str):
        return bool(cls.ref().child(_id).get())

    @classmethod
    def create_new(cls, _id: int):
        if cls.exists(str(_id)):
            raise TelegramError(f"Попытка создать товар id {_id}")

    @classmethod
    def get(cls, _id: str, data=None):
        # if not cls.exists(_id):
        #     raise TelegramError(f"Нет товара с id {_id}")
        instance = cls()
        instance.id = _id
        if data:
            instance._data = data
        else:
            instance.load()

        return instance

    @classmethod
    def all(cls, sort: str = "order", reverse=True):
        fb_goods = cls.ref().order_by_child(sort).get() if sort else cls.ref().get()
        fb_goods = fb_goods if fb_goods else []

        fb_goods = collections.OrderedDict(reversed(list(fb_goods.items()))) if reverse else fb_goods
        return [cls.get(ticket, fb_goods[ticket]) for ticket in fb_goods]
