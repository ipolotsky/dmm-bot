from firebase_admin.db import Reference
from telegram import TelegramError

from models.base_products import BaseProduct
from persistence.firebase_persistence import FirebasePersistence
from utils import helper

store = FirebasePersistence()


class Ticket(BaseProduct):

    PAID_TYPE = "paid"
    FREE_TYPE = "free"

    @classmethod
    def ref(cls) -> Reference:
        return store.tickets

    @property
    def increase_step(self):
        return helper.safe_list_get(self._data, "increase_step", 0)

    @increase_step.setter
    def increase_step(self, increase_step: int):
        raise TelegramError("Increase step is being changed only via Firebase store")

    # Functions

    def increase_price(self):
        # self._data["price"] = self.price + self.increase_step
        self.save()

    @staticmethod
    def by_type(_type: str):
        return list(filter(lambda ticket: ticket.type == _type, Ticket.all()))
