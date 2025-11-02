# -*- coding: utf-8 -*-
"""
Created on Wed Dec 28 06:16:57 2022

@author: Simon Kern
"""
import os
import time
import json
import traceback
import telegram_send
from functools import wraps
from telebot.util import escape

def forward_exception(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            tb = traceback.format_exc()
            print("SENDING STACK VIA TELEGRAM")
            msg = escape(f'VeniceBot Error: ```\n{e}: {repr(e)}</code>\n<code>{tb}\n```')
            print('---\n', tb, '\n---\nMSG:\n\n', msg, '\n---')

            telegram_send.send(messages = [msg])
            raise e
    return wrapped

@forward_exception
def load_settings():
    with open('settings.json', 'r') as f:
        settings = json.load(f)
    required = ['admin', 'token', 'email', 'password', 'client_secret']
    for key in required:
        assert key in settings, f'"{key}" not found in settings.json'
    return settings

@forward_exception
def write_settings(settings):
    with open('settings.json', 'w') as f:
        settings = json.dump(settings, f, indent=4)
    return True

@forward_exception
def load_user(user):
    if isinstance(user, dict):
        user_id = user['id']
    elif isinstance(user, (int, str)):
        user_id = int(user)
    else:
        user_id = user.id

    try:
        json_file = f'./users/{user_id}.json'
        with open(json_file, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        return {}

@forward_exception
def load_users():
    """
    loads all users

    Returns
    -------
    users : list
        list of users.
    """
    users_files = os.listdir('./users/')
    users_files = [f for f in users_files if f.endswith('json')]
    users = [load_user(os.path.splitext(user)[0]) for user in users_files]
    return users

@forward_exception
def update_user(message, fields=None):
    """
    Parameters
    ----------
    message : telebot.Message
        message from user to save to
    fields : dict, optional
        dictionary with fields to update. The default is None.

    """
    user = message.from_user
    if fields is None:
        fields = {}

    json_file = f'./users/{user.id}.json'
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            data = json.load(f)
        data = data | fields
        data['access'] += [int(time.time())]
        data['n_access'] += 1
    else:
        data = user.to_dict() | {'registered':  [int(time.time())],
                                 'access': [int(time.time())],
                                 'n_access': 0}

    with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)

@forward_exception
def load_studios():
    with open('studios.json', 'r') as f:
        return json.load(f)

@forward_exception
def write_studios(studios):
    with open('studios.json', 'w') as f:
        json.dump(studios, f, indent=4)