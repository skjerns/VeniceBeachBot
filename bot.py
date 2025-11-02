# -*- coding: utf-8 -*-
"""
Created on Wed Dec 28 06:13:15 2022

@author: Simon Kern
"""
import os
import time
import telebot
import telegram_send
from telebot.types import InputFile, ForceReply
from telebot.util import escape, extract_arguments
from telebot import apihelper
import logging
from logging.handlers import RotatingFileHandler

import utils
import plotting
from utils import forward_exception
from polling import get_checked_in_users, get_ids
from templates import TEMPLATE_HELP, TEMPLATE_SUPPORT, TEMPLATE_NO_GROUP
from templates import TEMPLATE_STATUS, TEMPLATE_NEW_STUDIO
from templates import format_user
apihelper.ENABLE_MIDDLEWARE = True

#bot = telebot.TeleBot(None)  # dummy bot so functions don't fail

if __name__=='__main__':
    print('Starting bot')
    logging.info('Starting bot')
    os.chdir(os.path.dirname(__file__))
    os.makedirs('./data/', exist_ok=True)
    os.makedirs('./users/', exist_ok=True)
    settings = utils.load_settings()
    token = settings['token']
    admin = settings['admin']
    bot = telebot.TeleBot(token, parse_mode='html')
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')

    handler = RotatingFileHandler('bot.log', mode='a', maxBytes=20*1024**2,
                                 backupCount=2, encoding=None, delay=0)
    handler.setFormatter(log_formatter)
    handler.setLevel(logging.INFO)
    telebot.logger.addHandler(handler)
    telebot.logger.setLevel(logging.INFO)


def get_formatted_studios():
    reply = '<b>Bitte wähle dein Studio:</b>\n\n'
    studios = utils.load_studios()
    for id, name in sorted(studios.items(), key=lambda x:x[1]):
       reply += f'{name} - /set_{id}\n'
    return reply


@bot.middleware_handler(update_types=['message'])
@forward_exception
def lowercase_command(bot_instance, message):
    if message.text and message.text.startswith('/'):
         cmd = message.text.split(' ', 1)
         message.text = ' '.join(([cmd[0].lower()] + cmd[1:]))

@bot.message_handler(chat_types=['group', 'superchat'])
@forward_exception
def no_group_mode(message):
    bot.reply_to(message, TEMPLATE_NO_GROUP)

@bot.message_handler(commands=['start', 'help'])
@forward_exception
def command_start(message):
    utils.update_user(message)
    user = format_user(message.from_user)
    bot.reply_to(message, TEMPLATE_HELP.format(user=user))
    if 'start' in message.text:
        bot.send_message(admin, f"{user} activated the bot")

@bot.message_handler(regexp=r"/set( |_)[0-9]{1,4}")
@forward_exception
def command_set_full(message):
    utils.update_user(message)
    studio = message.text[5:].strip()
    if studio.isdigit():
        studio_id = int(studio)
        # active_ids = get_ids()
        # if studio_id in active_ids:
        bot.reply_to(message, f"Deine Studio-ID wurde auf '{studio_id}' gestellt. "\
                               "Drücke /graph um den aktuellen Stand angezeigt zu bekommen.")
        # else:
        #     bot.reply_to(message, f"Deine Studio-ID wurde auf '{studio_id}' gestellt. "\
        #                            "Du bist der Erste der dieses Studio aktiviert. "\
        #                            "Deshalb werden Daten erst ab jetzt aufgezeichnet, d.h. "\
        #                            "es dauert eine Woche bis dir die Daten richtig angezeigt werden.")
        utils.update_user(message, fields={'studio':studio_id})
        if not os.path.exists(f'./data/studio_{studio_id}.csv'):
            bot.reply_to(message, TEMPLATE_NEW_STUDIO)
            get_checked_in_users(ids=[studio_id])
    elif studio=='':
        bot.reply_to(message, "ID muss angegeben werden: '/set ID'")
    else:
        bot.reply_to(message, f"ID darf nur aus Zahlen bestehen. => {studio}")

@bot.message_handler(commands=['studios'])
@forward_exception
def command_studios(message):
    reply = get_formatted_studios()
    bot.reply_to(message, reply)

@bot.message_handler(commands=['support'])
@forward_exception
def command_request_support(message):
    """forward message to admin of this bot"""
    # first reply to user
    utils.update_user(message)
    user = format_user(message.from_user)
    text = escape(extract_arguments(message.text))
    if text=='':
        bot.reply_to(message, "Was willst du dem Ersteller mitteilen?", reply_markup=ForceReply())
    else:
        bot.reply_to(message, TEMPLATE_SUPPORT)
        bot.send_message(admin, f"Nachricht von {user}:\n<code>{text}</code>")

@bot.message_handler(commands=['graph'])
@forward_exception
def command_graph(message):
    utils.update_user(message)
    user = utils.load_user(message.from_user)
    studio_id = user.get('studio', None)
    if studio_id is None:
        bot.reply_to(message, "Keine Studio-ID eingestellt.")
        reply = get_formatted_studios()
        bot.reply_to(message, reply)
        return
    msg = bot.reply_to(message, "Graph wird erstellt. Dies kann ein paar Sekunden dauern.")
    try:
        png_file = plotting.make_plot(studio_id)
    except Exception as e:
        bot.reply_to(message, 'Es gab einen Fehler beim Erstellen des Graphs.')
        raise e
    file = InputFile(png_file)
    bot.send_photo(message.chat.id, file)
    bot.delete_message(msg.chat.id, msg.message_id)

@bot.message_handler(commands=['status'])
@forward_exception
def command_status(message):
    utils.update_user(message)
    user = format_user(message.from_user)
    data = utils.load_user(message.from_user)
    studios = utils.load_studios()
    studio = data.get('studio', 'NOT SET')
    studio_str = f'{studio} - "{studios.get(str(studio), "NOT SET")}"'
    n_access = data['n_access']
    bot.reply_to(message, TEMPLATE_STATUS.format(user=user, studio=studio_str,
                                                 n_access=n_access))

@bot.message_handler(func=lambda x: x.reply_to_message and x.reply_to_message.text=='Was willst du dem Ersteller mitteilen?')
@forward_exception
def forward_support(message):
    user = format_user(message.from_user)
    text = escape(message.text)
    bot.reply_to(message, TEMPLATE_SUPPORT)
    bot.send_message(admin, f"Nachricht von {user}:\n<code>{text}</code>")

@bot.message_handler(func=lambda x:(str(x.from_user.id)==admin) & (x.text.startswith('/message')))
@bot.message_handler(commands=['message'])
@forward_exception
def command_broadcast(message):
    if str(message.from_user.id)!=admin:
        return
    users = utils.load_users()
    two_month = time.time() - 3600*24*60
    active = [user for user in users if user.get('access', [0])[-1]>two_month]

    text = message.text.replace('/message', '')
    text = escape(message.text)

    errs = []
    for user in active:
        try:
            bot.send_message(user['id'], text)
        except Exception as e:
            errs.append(f'Cannot send to {user}: {e} {repr(e)}')
    users = ', '.join([format_user() for user in users])
    response = f'Sent to {len(active)-len(errs)} users : {users}'
    bot.reply_to(message, escape(response))

    if len(errs)>0:
        bot.reply_to(message, escape(str(errs)))
        logging.error(str(errs))

@bot.message_handler(func=lambda x:(str(x.from_user.id)==admin) & (x.text.startswith('/stats')))
@bot.message_handler(commands=['stats'])
@forward_exception
def admin_statistics(message):
    users = utils.load_users()
    weeks4 = time.time() - (60*60*24*7*4)

    users_weeks4 = []
    for user in users:
        user['access'] = access = [dt for dt in user['access'] if dt>weeks4]
        if access:
            users_weeks4 += [user]

    users_sorted = sorted(users_weeks4, key=lambda x:len(x['access']), reverse=True)

    s =  f'<code>Users total: {len(users)}\n'
    s += f'Users last 4 weeks: {len(users_weeks4)}\n'
    for i in range(min(10, len(users_sorted))):
        user = users_sorted[i]
        s += f'{i+1:2d}. {format_user(user)} ({len(user["access"])})\n'
    s += '</code>'
    bot.reply_to(message, s)


@bot.message_handler(func=lambda x:str(x.from_user.id)==admin)
@forward_exception
def parse_admin_commands(message):
    """Admin messages are processed separately."""
    cmd = message.text.lower()
    if cmd=='fetch':
        import polling
        bot.reply_to(message, "fetching studios")
        polling.fetch_studios(force=True)
    else:
        bot.reply_to(message, "nothing to do")


@bot.message_handler(func=lambda m: True)
@forward_exception
def echo_all(message):
    print(message)
    user = format_user(message.from_user)
    bot.send_message(admin, f"Nachricht von {user}:\n<code>{message.text}</code>")
    bot.reply_to(message, "Sorry, no idea what you mean... click /help to get more infos")


if __name__=='__main__':
    bot.set_my_commands([
        telebot.types.BotCommand("/graph", "Zeige momentane Auslastung"),
        telebot.types.BotCommand("/studios", "Zeige alle verfügbaren Studios"),
        # telebot.types.BotCommand("/status", "Zeige deine Einstellungen"),
        telebot.types.BotCommand("/help", "Zeige alle Bot-Befehle"),
    ])


    try:
        print('Starting loop. Loop running...')
        logging.info('Engaging infinity poll')
        bot.infinity_polling()
    except Exception as e:
        telegram_send.send(messages = [f'VeniceBot stopped: {e} {repr(e)}'], format='html')
        print('bot stopped', e)
        raise e
