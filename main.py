#!/usr/bin/env python
# pylint: disable=C0116
import json
import logging
import random
import re
import time
from datetime import datetime

import requests
from emoji import emojize
from typing import Optional
from telegram import ReplyKeyboardMarkup, Update, ParseMode, TelegramError, ReplyKeyboardRemove, LabeledPrice
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from models.ticket_purchases import TicketPurchase
from settings import Settings
from models.tickets import Ticket
from models.users import User
from handlers.error_handler import error_handler
from persistence.firebase_persistence import FirebasePersistence
from utils import helper
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackQueryHandler,
    CallbackContext, PreCheckoutQueryHandler,
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
QRCODE_SERVICE_API_URL = 'http://api.qrserver.com/v1/read-qr-code/'
BULK_SEND_SLEEP_STEP = 25

CONVERSATION_NAME = "user_states_conversation"
CONVERSATION_ADMIN_NAME = "admin_states_conversation"

store = FirebasePersistence()

# Conversation states
STARTING, WAITING_NAME, WAITING_VK, WAITING_PAYMENT, READY_DASHBOARD, ADMIN_DASHBOARD, ADMIN_CHECKIN = range(1, 8)

state_texts = dict([
    (STARTING, 'Привет! Это бот ДММ 2022. Что тебя ждет: познакомимся, '
               'а потом сделаем покупку билета на ДММ 2022 прямо тут! \n\nНапиши, плиз, как тебя зовут?'),
    (WAITING_NAME, 'Такс, давай знакомиться! Пара вопросов, чтобы мы узнали, кто ты такой(ая). \nКак тебя зовут?'),
    (WAITING_VK, 'А теперь ссылку на свой vk'),
    (WAITING_PAYMENT, "Супер! Теперь ты можешь покупать билет, жамкай на кнопулю"),
    (READY_DASHBOARD, "Успех! У тебя есть билет на ДММ 2022!\n"),
])

# Bot buttons

BUTTON_BACK = "Спина"
BUTTON_ADMIN_STATS = "Статистика"
BUTTON_ADMIN_CSV = "Покупки CSV"
BUTTON_ADMIN_ALL = "Все пользователи"
CALLBACK_BUTTON_REALNAME = "Realname"
BUTTON_TICKETS = "Билеты"
BUTTON_MY_TICKET = "Мой билет"
BUTTON_INFO = "Про ДММ2022"
BUTTON_STATUS = "Как у меня дела"
CALLBACK_BUTTON_GIFT_TICKET = "Gift"
BUTTON_ADMIN_CHECKIN = "Регистрация"


# Telegram bot keyboards functions

def admin_keyboard(buttons=None):
    if buttons is None:
        buttons = []
    buttons.append([str(BUTTON_ADMIN_CSV), str(BUTTON_ADMIN_STATS), str(BUTTON_ADMIN_CHECKIN)])
    buttons.append([str(BUTTON_ADMIN_ALL), str(BUTTON_BACK)])
    return buttons


def get_default_keyboard_bottom(user: User, buttons=None, is_admin_in_convs=True):
    convs = store.get_conversations(str(CONVERSATION_NAME))
    state = convs.get(tuple([user.id]))

    if buttons is None:
        buttons = []

    if state in [WAITING_PAYMENT]:
        buttons.append([str(BUTTON_TICKETS)])

    if state in [READY_DASHBOARD]:
        buttons.append([str(BUTTON_MY_TICKET)])

    key_board = [str(BUTTON_STATUS), str(BUTTON_INFO)]

    if user.admin:
        in_admin_convs = store.get_conversations(str(CONVERSATION_ADMIN_NAME)).get(tuple([user.id]))
        if is_admin_in_convs and in_admin_convs:
            return admin_keyboard(buttons)

        key_board.append("Admin")

    buttons.append(key_board)
    return buttons


# Helpers


def create_new_user(_id: int, _data: dict, status):
    user = User.create_new(_id)
    user.set_data(_data)
    user.status = status
    user.save()
    return user


# User actions (changes conversation state)

def action_start(update: Update, context: CallbackContext) -> None:
    reply_text = state_texts[STARTING]

    user = create_new_user(update.effective_user.id, update.effective_user.to_dict(), User.STATUS_WELCOME)
    update.message.reply_text(
        reply_text,
        reply_markup=ReplyKeyboardMarkup(get_default_keyboard_bottom(user),
                                         resize_keyboard=True), disable_web_page_preview=True, )

    return WAITING_NAME


def action_set_name(update: Update, context: CallbackContext) -> int:
    user = User.get(update.effective_user.id)
    text = update.message.text
    user.real_name = text.strip()
    user.save()

    reply_text = (
        f"Приветы, {user.real_name}! Сначала скинь, как тебя найти в VK"
        f"Не забудь проверить, что у тебя открытый профиль!"
    )
    update.message.reply_text(
        reply_text, reply_markup=ReplyKeyboardMarkup(
            get_default_keyboard_bottom(user), resize_keyboard=True,
        ), disable_web_page_preview=True)

    return WAITING_VK


def action_set_name_callback(update: Update, context: CallbackContext) -> int:
    user = User.get(update.effective_user.id)
    real_name = update.callback_query.data.split(':')[1]
    user.real_name = real_name.strip()
    user.save()

    reply_text = (
        f"Приветы, {user.real_name}! Сначала скинь, как тебя найти в VK"
        f"Не забудь проверить, что у тебя открытый профиль!"
    )

    update.callback_query.answer()
    update.callback_query.delete_message()

    context.bot.send_message(chat_id=user.id, text=reply_text, disable_web_page_preview=True)

    return WAITING_VK


# 1111 1111 1111 1026, 12/22, CVC 000.


def action_set_vk(update: Update, context: CallbackContext) -> Optional[int]:
    user = User.get(update.effective_user.id)
    text = update.message.text.strip()

    vk_link = helper.get_vk(text)
    if not vk_link:
        replay_text = "Хах, это не VK! Cкинь, как тебя найти в VK (имя профиля или ссылка, " \
                      f"например, https://vk.com/badfest/)\n" \
                      f"Не забудь проверить, что у тебя открытый профиль!"
        update.message.reply_text(
            replay_text, reply_markup=ReplyKeyboardMarkup(
                get_default_keyboard_bottom(user),
                resize_keyboard=True), disable_web_page_preview=True, )
        return None

    user.vk = vk_link

    if user.status == User.STATUS_WELCOME:
        user.status = User.STATUS_APPROVED

    user.save()

    update_conversation(str(CONVERSATION_NAME), user, WAITING_PAYMENT)

    reply_text = state_texts[WAITING_PAYMENT]
    update.message.reply_text(
        reply_text, reply_markup=ReplyKeyboardMarkup(
            get_default_keyboard_bottom(user),
            resize_keyboard=True,
        ), disable_web_page_preview=True)

    for admin in User.admins():
        message = "Новая регистрация: " + user.pretty_html() + "\n"
        context.bot.send_message(chat_id=admin.id, text=message, parse_mode=ParseMode.HTML)

    return WAITING_PAYMENT


def action_successful_payment_callback(update: Update, context: CallbackContext) -> None:
    payment = update.message.successful_payment

    try:
        Ticket.get(payment.invoice_payload)
        return process_successful_ticket(update, context)
    except:
        raise TelegramError(f"Пришла оплата на хер пойми что: {str(payment)}")


def process_successful_ticket(update: Update, context: CallbackContext):
    payment = update.message.successful_payment
    user = User.get(update.effective_user.id)
    ticket = Ticket.get(payment.invoice_payload)
    purchase = TicketPurchase.create_new(update.message.successful_payment.provider_payment_charge_id)
    purchase.currency = payment.currency
    purchase.total_amount = payment.total_amount
    purchase.set_ticket_info(ticket)
    purchase.user = user
    purchase.phone_number = helper.safe_list_get(payment.order_info, "phone_number")
    purchase.email = helper.safe_list_get(payment.order_info, "email")
    purchase.customer_name = helper.safe_list_get(payment.order_info, "name")
    purchase.telegram_payment_charge_id = payment.telegram_payment_charge_id
    purchase.provider_payment_charge_id = payment.provider_payment_charge_id
    purchase.save()

    try:
        purchase.create_image()
    except:
        print("error")

    # ticket.increase_price()

    user.status = User.STATUS_READY
    user.purchase_id = purchase.id
    user.save()

    update_conversation(str(CONVERSATION_NAME), user, READY_DASHBOARD)

    update.message.reply_text(state_texts[READY_DASHBOARD], reply_markup=ReplyKeyboardMarkup(
        get_default_keyboard_bottom(user), resize_keyboard=True),
                              disable_web_page_preview=True,
                              parse_mode=ParseMode.HTML)

    reply_html = purchase.pretty_html()
    context.bot.send_message(
        user.id,
        text=reply_html,
        disable_web_page_preview=True)

    try:
        with open(f'images/{purchase.id}.png', 'rb') as f:
            context.bot.send_photo(user.id, photo=f, timeout=50)
    except:
        logging.log(logging.ERROR, "File not found")

    for admin in User.admins():
        message = emojize(":money_bag:", use_aliases=True) + f" {user.real_name} ({user.username})" \
                                                             f" купил(а) билет '{purchase.ticket_name}' за {purchase.total_amount / 100} р."
        context.bot.send_message(chat_id=admin.id, text=message)

    return READY_DASHBOARD


# User show data functions:

def show_info(update: Update, context: CallbackContext):
    update.message.reply_html(
        "<b>ДММ 2022</b>\n\n"
        "Новости @dmmnews \n", disable_web_page_preview=True, disable_notification=True)


def show_my_ticket(update: Update, context: CallbackContext):
    user = User.get(update.effective_user.id)
    purchases = TicketPurchase.by_user(user)

    for purchase in purchases:
        reply_html = purchase.pretty_html()
        update.message.reply_html(
            text=reply_html,
            disable_web_page_preview=True)
        try:
            with open(f'images/{purchase.id}.png', 'rb') as f:
                pass
        except:
            purchase.create_image()

        with open(f'images/{purchase.id}.png', 'rb') as f:
            context.bot.send_photo(user.id, photo=f, timeout=50, reply_markup=ReplyKeyboardMarkup(
                get_default_keyboard_bottom(user), resize_keyboard=True), )


def show_tickets(update: Update, context: CallbackContext):
    user = User.get(update.effective_user.id)
    if user.status != User.STATUS_APPROVED:
        update.message.reply_text("Рано еще!")
        return None

    index = 1
    update.message.reply_html(
        text="Выбирай билет и покупай прямо тут в телеграме (да, так уже можно, начиная с апреля этого года)\n"
             "Продолжая покупку, ты соглашаешься с <a href='https://badbar.ru/policy'>"
             "политикой конфеденциальности</a> и <a href='https://vk.com/@badfest-manifest'>прочей лабудой</a>,"
             " которая нам, к сожалению, нужна:\n\n",
        disable_web_page_preview=True)

    for ticket in Ticket.by_type(Ticket.PAID_TYPE):
        payload = ticket.id
        provider_token = Settings.provider_token()
        currency = "RUB"
        prices = [LabeledPrice(ticket.id, ticket.price * 100)]

        context.bot.send_invoice(
            chat_id=user.id, title=emojize(":admission_tickets:", use_aliases=True) + ticket.id,
            description=ticket.description, payload=payload, provider_token=provider_token,
            currency=currency, prices=prices,
            photo_url=ticket.photo, photo_width=500, photo_height=500, need_name=True,
            need_email=True, need_phone_number=True, max_tip_amount=2000000,
            suggested_tip_amounts=[int(ticket.price * 10), int(ticket.price * 100), int(ticket.price * 300)]
        )

        index += 1


def precheckout_callback(update: Update, _: CallbackContext) -> None:
    query = update.pre_checkout_query

    if not query.invoice_payload:
        query.answer(ok=False, error_message=f"Payload какой-то не такой... пустой, нет его")
        return None

    ticket = None
    merch = None
    error_text = ""

    try:
        ticket = Ticket.get(query.invoice_payload)
    except:
        # query.answer(ok=False, error_message=f"Нет билета с таким id:{query.invoice_payload}")
        error_text = f"Нет билета с таким id:{query.invoice_payload}"

    if (not ticket) and (not merch):
        query.answer(ok=False, error_message=error_text)
        return None

    if ticket:
        if ticket.type != Ticket.PAID_TYPE:
            query.answer(ok=False, error_message=f"Билет то уже не актуальный, ты чо")
            return None

        try:
            user = User.get(query.from_user.id)

            if user.status == User.STATUS_READY:
                query.answer(ok=False, error_message=f"Ты уже купил(а) билет на себя. "
                                                     f"Если просто хочешь донатить нам - напиши ограм, "
                                                     f"мы будем счастливы!")
                return None

            if user.status != User.STATUS_APPROVED:
                query.answer(ok=False, error_message=f"Так так... Пользователь {user.real_name} с id {user.id} "
                                                     f"и статусом {user.status} не подтвержден для покупки.")
                return None
        except:
            # answer False pre_checkout_query
            query.answer(ok=False, error_message=f"Нет пользователя с таким id:{query.from_user.id}")
            return None

    query.answer(ok=True)


def show_status(update: Update, context: CallbackContext) -> None:
    user = User.get(update.effective_user.id)
    update.message.reply_html(
        f"Все, что знаем о тебе\n\n{user.pretty_html()}",
        reply_markup=ReplyKeyboardMarkup(
            get_default_keyboard_bottom(user),
            resize_keyboard=True,
        )
    )


def show_state_text(update: Update, context: CallbackContext):
    convs = store.get_conversations(str(CONVERSATION_NAME))
    state = convs.get(tuple([update.effective_user.id]))
    if state:
        update.message.reply_text(
            state_texts[state] + f"\nИспользуй кнопочки снизу, если что-то хочешь.", reply_markup=ReplyKeyboardMarkup(
                get_default_keyboard_bottom(User.get(update.effective_user.id)),
                resize_keyboard=True,
            ), disable_web_page_preview=True, parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text("Жамкни /start")

    return None


# Admin actions:

def admin_action_dashboard(update: Update, context: CallbackContext):
    user = User.get(update.effective_user.id)
    if not user or not user.admin:
        update.message.reply_text("Ну-ка! Куда полез!?")
        return None

    update.message.reply_text(
        'Милорд!',
        reply_markup=ReplyKeyboardMarkup(admin_keyboard(), resize_keyboard=True,
                                         ), disable_web_page_preview=True, )

    return ADMIN_DASHBOARD


def admin_action_checkin_photo_code(update: Update, context: CallbackContext):
    update.message.reply_text("Начинаю распознование...")

    user = User.get(update.effective_user.id)
    if not user or not user.admin:
        update.message.reply_text("Ну-ка! Куда полез!?")
        return None

    file = context.bot.getFile(update.message.photo[-1].file_id)
    response = requests.post(url=QRCODE_SERVICE_API_URL, params={'fileurl': file.file_path})
    json_response = json.loads(response.content)
    if response.status_code != 200:
        update.message.reply_text(f"Чет не получилось тут qr-код найти, попробуй еще разок сфоткать.")
        return None

    try:
        if json_response[0]['symbol'][0]['error']:
            update.message.reply_text(
                f"Чет не получилось тут qr-код найти, попробуй еще разок сфоткать. Детали: {json_response[0]['symbol'][0]['error']}")
            return None

        code = json_response[0]['symbol'][0]['data'].strip()
        admin_function_check_code(update, code)

    except:
        update.message.reply_text(
            f"Чет не получилось тут qr-код найти, попробуй еще разок сфоткать")


def admin_action_checkin_text_code(update: Update, context: CallbackContext):
    update.message.reply_text("Такс, начинаю сверять билет, в яме и песках это может быть не быстро...")
    user = User.get(update.effective_user.id)
    if not user or not user.admin:
        update.message.reply_text("Ну-ка! Куда полез!?")
        return None

    code = update.message.text.strip()
    admin_function_check_code(update, code)


def admin_function_check_code(update: Update, code: str):
    try:
        ticket_purchase = TicketPurchase.get(code)
        if ticket_purchase.activated:
            update.message.reply_text(f"УЖЕ ЗАРЕГИСТРИРОВАН! НЕ ПОДДАВАТЕСЬ НА РАЗГОВОРЫ С МОШЕННИКАМИ!\n\n" +
                                      ticket_purchase.pretty_detailed_html())
        else:
            ticket_purchase.activated = datetime.now().timestamp()
            ticket_purchase.save()
            update.message.reply_html(f"<b>ФУК ЕЕЕЕЕ! Успешно зареган!</b>\n\n"
                                      f"Выдай участнику маску, попшикай на руки, скажи, что ковид и вот это вот все."
                                      f"\n\n" +
                                      ticket_purchase.pretty_detailed_html())

    except:
        update.message.reply_text("Хмм... какая-то хуита. Нет такого билета.")


def admin_action_back_to_dashboard(update: Update, context: CallbackContext):
    user = User.get(update.effective_user.id)
    if not user or not user.admin:
        update.message.reply_text("Ну-ка! Куда полез!?")
        return None
    update.message.reply_text(
        'Кк',
        reply_markup=ReplyKeyboardMarkup(admin_keyboard(), resize_keyboard=True,
                                         ), disable_web_page_preview=True)
    return ADMIN_DASHBOARD


def admin_action_registration(update: Update, context: CallbackContext):
    user = User.get(update.effective_user.id)
    if not user or not user.admin:
        update.message.reply_text("Ну-ка! Куда полез!?")
        return None

    update.message.reply_text(
        'Отправь фотку билета или сам код (если распознаешь обычной камерой и у тебя не старый андроид)',
        reply_markup=ReplyKeyboardMarkup([[str(BUTTON_BACK)]], resize_keyboard=True, ), disable_web_page_preview=True)
    return ADMIN_CHECKIN


def admin_action_back(update: Update, context: CallbackContext):
    user = User.get(update.effective_user.id)
    if not user or not user.admin:
        update.message.reply_text("Ну-ка! Куда полез!?")
        return None

    update.message.reply_text(
        'Возвращайтесь, админка ждет своего господина!', reply_markup=ReplyKeyboardMarkup(
            get_default_keyboard_bottom(user, None, False),
            resize_keyboard=True,
        ), disable_web_page_preview=True)
    return -1


# Admin show data functions:

def admin_show_stats(update: Update, context: CallbackContext):
    user = User.get(update.effective_user.id)
    if not user or not user.admin:
        update.message.reply_text("Ну-ка! Куда полез!?")
        return None

    update.message.reply_text("Статистика")
    update.message.reply_text("Пользователи: \n" + User.statistics())
    update.message.reply_text("Покупки: \n" + TicketPurchase.statistics())


def admin_show_csv(update: Update, context: CallbackContext):
    user = User.get(update.effective_user.id)
    if not user or not user.admin:
        update.message.reply_text("Ну-ка! Куда полез!?")
        return None

    TicketPurchase.statistics_csv()
    with open(f'purchases.csv', 'rb') as f:
        update.message.reply_document(document=f)


def admin_show_list(update: Update, context: CallbackContext):
    user = User.get(update.effective_user.id)
    if not user or not user.admin:
        update.message.reply_text("Ну-ка! Куда полез!?")
        return None

    if not len(context.matches):
        update.message.reply_text("Неверная команда")
        return None

    users = User.all()

    i = 1
    result = ""
    for user in users:
        if len(str(result + user.pretty_html(i))) > 4000:
            update.message.reply_html(result, disable_web_page_preview=True)
            result = user.pretty_html(f"/{str(user.id)} {i}")
            continue
        result = result + user.pretty_html(f"/{str(user.id)} {i}") + "\n"
        i += 1

    update.message.reply_html(
        f"{result}\n\nВсего пользователей: " + str(len(users)), reply_markup=ReplyKeyboardMarkup(
            admin_keyboard(),
            resize_keyboard=True,
        ), disable_web_page_preview=True, )
    return None


def admin_show_one_user(update: Update, context: CallbackContext):
    pattern = re.compile(r'^\/([0-9]+)$')
    id = pattern.search(update.message.text).group(1)
    user = User.get(int(id))
    reply_html = user.pretty_html()

    markup_buttons = []
    if not user.purchase_id and (user.status in [User.STATUS_APPROVED]):
        markup_buttons.append([
            InlineKeyboardButton(
                text='Выдать билет', callback_data=f"{str(CALLBACK_BUTTON_GIFT_TICKET)}:" + str(user.id))
        ])

    if user.purchase_id:
        reply_html = emojize(":admission_tickets:", use_aliases=True) + " " + reply_html

        purchase = TicketPurchase.get(user.purchase_id)
        reply_html += f"\nБилет: {purchase.ticket_name} {purchase.total_amount / 100} р." \
                      f"\nВремя покупки: {purchase.created}"

    update.message.reply_html(
        text=reply_html,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(markup_buttons))


# User functions:


# Admin functions:


def admin_gift(update: Update, context: CallbackContext) -> None:
    admin_user = User.get(update.effective_user.id)
    if not admin_user or not admin_user.admin:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text="Ну-ка! Куда полез!?", parse_mode=ParseMode.HTML)
        return None

    string_user_id = update.callback_query.data.split(':')[1]
    user = User.get(int(string_user_id))

    if not (user.status in [User.STATUS_APPROVED]):
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=f"Статус пользователя {user.status} не позволяет выдать билет.",
                                                parse_mode=ParseMode.HTML)
        return None

    if user.purchase_id:
        reply_text = emojize(":man_detective:",
                             use_aliases=True) + " Возможно другой админ уже выдал билет " + user.pretty_html()
    else:
        purchase = TicketPurchase.create_new_gift(admin_user)
        purchase.user = user
        purchase.save()

        purchase.create_image()

        user.status = User.STATUS_READY
        user.purchase_id = purchase.id
        user.save()

        update_conversation(str(CONVERSATION_NAME), user, READY_DASHBOARD)

        context.bot.send_message(user.id, state_texts[READY_DASHBOARD], reply_markup=ReplyKeyboardMarkup(
            get_default_keyboard_bottom(user),
            resize_keyboard=True,
        ),
                                 disable_web_page_preview=True,
                                 parse_mode=ParseMode.HTML)

        reply_text = emojize(":admission_tickets:", use_aliases=True) + " БИЛЕТ ВЫДАН " + user.pretty_html()

    update.callback_query.answer()
    update.callback_query.edit_message_text(text=reply_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    return None


conv_admin_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^Admin$'), admin_action_dashboard)],
    states={
        ADMIN_DASHBOARD: [
            MessageHandler(Filters.regex(f'^{str(BUTTON_ADMIN_ALL)}'), admin_show_list),
            MessageHandler(Filters.regex(f'^{str(BUTTON_ADMIN_CSV)}'), admin_show_csv),
            MessageHandler(Filters.regex(f'^{str(BUTTON_ADMIN_STATS)}'), admin_show_stats),
            MessageHandler(Filters.regex(f'^{str(BUTTON_ADMIN_CHECKIN)}$'), admin_action_registration),
            MessageHandler(Filters.regex(f'^{str(BUTTON_BACK)}$'), admin_action_back),
            CallbackQueryHandler(admin_gift, pattern=rf'^({str(CALLBACK_BUTTON_GIFT_TICKET)}.*$)'),
            MessageHandler(Filters.regex(f'^\/[0-9]+$'), admin_show_one_user)
        ],
        ADMIN_CHECKIN: [
            MessageHandler(Filters.regex(f'^{BUTTON_BACK}'), admin_action_back_to_dashboard),
            MessageHandler(Filters.photo, admin_action_checkin_photo_code),
            MessageHandler(Filters.text, admin_action_checkin_text_code),
        ]
    },
    fallbacks=[],
    name=str(CONVERSATION_ADMIN_NAME),
    persistent=True,
    per_chat=False,
    per_message=False
)
# Conversations


conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('start', action_start),
    ],
    states={
        WAITING_NAME: [
            MessageHandler(
                Filters.text, action_set_name
            ),
            CallbackQueryHandler(action_set_name_callback, pattern=rf'^{CALLBACK_BUTTON_REALNAME}:.*$'),
        ],
        WAITING_VK: [
            MessageHandler(
                Filters.text, action_set_vk,
            )
        ],
        WAITING_PAYMENT: [
            MessageHandler(Filters.regex(f'^{BUTTON_TICKETS}$'), show_tickets),
            PreCheckoutQueryHandler(precheckout_callback),
            MessageHandler(Filters.successful_payment, action_successful_payment_callback),
        ],
        READY_DASHBOARD: [
            MessageHandler(Filters.regex(f'^{BUTTON_MY_TICKET}$'), show_my_ticket),
        ]
    },
    fallbacks=[],
    name=str(CONVERSATION_NAME),
    persistent=True,
    per_chat=False,
    per_message=False
)


def update_conversation(conversation_name: str, user: User, state: int):
    store.update_conversation(conversation_name, tuple([user.id]), state)
    refresh_conversations(conv_handler)


def refresh_conversations(handler: ConversationHandler):
    handler.conversations = store.get_conversations(str(CONVERSATION_NAME))


# Main endpoint

def main() -> None:
    updater = Updater(Settings.bot_token(), persistence=store)
    dispatcher = updater.dispatcher

    # Add handlers
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^{str(BUTTON_STATUS)}$'), show_status))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^{str(BUTTON_INFO)}'), show_info))

    dispatcher.add_handler(conv_admin_handler)
    dispatcher.add_handler(conv_handler)

    dispatcher.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dispatcher.add_handler(MessageHandler(Filters.successful_payment, action_successful_payment_callback))
    dispatcher.add_handler(MessageHandler(Filters.text, show_state_text))
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
