import collections
from datetime import datetime
from itertools import groupby

from telegram import TelegramError

from persistence.firebase_persistence import FirebasePersistence
from utils import helper

store = FirebasePersistence()


class User:
    STATUS_WELCOME = 'just_open_bot'
    STATUS_APPROVED = 'approved'
    STATUS_READY = 'ready'

    @staticmethod
    def status_to_pretty():
        return dict([
            (User.STATUS_WELCOME, "только открыл/а бота"),
            (User.STATUS_APPROVED, "подтвержден/ена, но не оплатил/а билет"),
            (User.STATUS_READY, "уже с билетом"),
        ])

    @staticmethod
    def status_to_buttons():
        return dict([
            (User.STATUS_WELCOME, "Открыл бота"),
            (User.STATUS_APPROVED, "Подтвержден, без билета"),
            (User.STATUS_READY, "Есть билет"),
        ])

    def __init__(self):
        self._id = None
        self._data = {}
        self.status = None

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, _id: int):
        self._id = _id

    @property
    def admin(self):
        return helper.safe_list_get(self._data, "admin", False)

    @admin.setter
    def admin(self, admin: bool):
        raise TelegramError("Нельзя устанавливать пользователя в админа")

    @property
    def god(self):
        return helper.safe_list_get(self._data, "god", False)

    @god.setter
    def god(self, god: bool):
        raise TelegramError("Нельзя устанавливать пользователя в бога")

    @property
    def status(self):
        return helper.safe_list_get(self._data, "status")

    @status.setter
    def status(self, status: str):
        self._data["status"] = status

    @property
    def first_name(self):
        return helper.safe_list_get(self._data, "first_name")

    @first_name.setter
    def first_name(self, first_name: str):
        self._data["first_name"] = first_name

    @property
    def last_name(self):
        return helper.safe_list_get(self._data, "last_name")

    @last_name.setter
    def last_name(self, last_name: str):
        self._data["last_name"] = last_name

    @property
    def username(self):
        return f"@{helper.safe_list_get(self._data, 'username', 'no_username')}"

    @username.setter
    def username(self, username: str):
        self._data["username"] = username

    @property
    def real_name(self):
        return helper.safe_list_get(self._data, "real_name")

    @real_name.setter
    def real_name(self, real_name: str):
        self._data["real_name"] = real_name

    @property
    def insta(self):
        return helper.safe_list_get(self._data, "insta")

    @insta.setter
    def insta(self, insta: str):
        self._data["insta"] = insta

    @property
    def vk(self):
        return helper.safe_list_get(self._data, "vk")

    @vk.setter
    def vk(self, vk: str):
        self._data["vk"] = vk

    @property
    def purchase_id(self):
        return helper.safe_list_get(self._data, "purchase_id")

    @purchase_id.setter
    def purchase_id(self, purchase_id: str):
        self._data["purchase_id"] = purchase_id

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
        store.users.child(str(self._id)).update(self._data)

    def full_name(self):
        if self.real_name:
            return self.real_name

        return f"{self.first_name} {self.last_name}"

    def tech_data(self):
        return self._data

    # Functions

    def set_data(self, data: dict):
        if "first_name" in data:
            self.first_name = data["first_name"]
        if "last_name" in data:
            self.last_name = data["last_name"]
        if "username" in data:
            self.username = data["username"]

    def load(self):
        if not self._id:
            raise TelegramError(f"Отсутстует id")

        _data = store.users.child(str(self._id)).get()
        if not _data:
            raise TelegramError(f"Нет данных по пользователю с id: {self._id}")

        self._data = _data

    def pretty_html(self, index: int = None):
        return "<b>{}{}</b> => {}\n" \
               "Data: {} ({}) / <a href='tg://user?id={}'>{}</a>\n" \
               "<a href='{}'>vk</a>\n" \
               "\n".format(str(index) + ". " if index else "",
                           self.real_name,
                           User.status_to_pretty()[self.status],
                           self.full_name(),
                           self.id,
                           self.id,
                           self.username,
                           self.vk)

    @staticmethod
    def get(_id: int, data=None):
        # if not User.exists(_id):
        #     raise TelegramError(f"Нет пользователя с id {_id}")
        user = User()
        user.id = _id
        if data:
            user._data = data
        else:
            user.load()

        return user

    @staticmethod
    def exists(_id: int):
        return bool(store.users.child(str(_id)).get())

    @staticmethod
    def create_new(_id: int):
        if User.exists(_id):
            raise TelegramError(f"Попытка создать пользователя с существующем id {_id}")

        store.users.child(str(_id)).update({
            'id': _id,
            'created': datetime.now().timestamp()
        })

        user = User()
        user.id = _id
        user._data = store.users.child(str(_id)).get()
        return user

    @staticmethod
    def all(sort: str = "created", reverse=False):
        fb_users = store.users.order_by_child(sort).get() if sort else store.users.get()
        fb_users = fb_users if fb_users else []

        fb_users = collections.OrderedDict(reversed(list(fb_users.items()))) if reverse else fb_users
        return list(map(lambda fb_user: User.get(fb_user, fb_users[fb_user]), fb_users))

    @staticmethod
    def gods():
        return list(filter(lambda user: user.god, User.all()))

    @staticmethod
    def admins():
        return list(filter(lambda user: user.admin, User.all()))

    @staticmethod
    def by_status(_status: str):
        return list(filter(lambda user: user.status == _status, User.all()))

    @staticmethod
    def group_by_status():
        groups = collections.defaultdict(list)
        for obj in User.all():
            groups[obj.status].append(obj)
        return groups

    @staticmethod
    def statistics():
        groups = User.group_by_status()
        result = ""
        for group in groups:
            result += User.status_to_pretty()[group].capitalize() + ": " + str(len(groups[group])) + "\n"

        return result
