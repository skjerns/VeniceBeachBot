# -*- coding: utf-8 -*-
"""
Created on Wed Dec 15 10:27:21 2021

This script polls the current user count of a Venice Beach Studio
every 5 minutes and writes it to a csv

@author: Simon Kern
"""
import os
import time
import datetime
import traceback
from filelock import Timeout, FileLock
import threading
import utils
import requests
from utils import forward_exception
import bs4
from requests.structures import CaseInsensitiveDict
import telegram_send
from multiprocessing import pool
import logging
from logging.handlers import RotatingFileHandler

log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')

handler = RotatingFileHandler('bot.log', mode='a', maxBytes=20*1024**2,
                             backupCount=2, encoding=None, delay=0)
handler.setFormatter(log_formatter)
handler.setLevel(logging.INFO)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

@forward_exception
def get_studio_id_venice(uri):
    try:
        res = requests.get(f'https://www.venicebeach-fitness.de/{uri}')
        soup = bs4.BeautifulSoup(res.content, features="lxml")
        studio_id = soup.find('actinate-classes-widget')['data-studioid']
        studio_name = soup.find('title').text.split('|')[0].strip()
        studio_type = soup.find('small', {'class':'subtitle'}).text.split(' ')[0]
        logging.info('Fetched {studio_id}: {studio_name} {studio_type}')
    except Exception as e:
        logging.error(f'error while fetching studio from {uri=}, {e}')
        return None
    return {studio_id: f'{studio_name} {studio_type}'}

@forward_exception
def get_studio_id_fitbase(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
    url = f'https://fitbase.fitness/{url}'
    try:
        res = requests.get(url, headers=headers)
        soup = bs4.BeautifulSoup(res.content, features="lxml")
        studio_id = soup.find('actinate-classes-widget')['data-studioid']
        studio_name = soup.find('title').text.split('|')[0].strip()
        studio_name = studio_name.replace('- Dein Fitnessstudio in ', '')
        studio_name = studio_name.replace(' - FITBASE', '')
        logging.info('Fetched {studio_id}: {studio_name}')
    except Exception as e:
        logging.error(f'error while fetching studio from {url=}, {e}')
        return None
    return {studio_id: f'{studio_name}'}


@forward_exception
def fetch_studios(force=False):
    if not force and (os.path.exists('studios.json') and
       (time.time()-os.path.getmtime('studios.json')<24*60*60*7)):
        logging.info('Not fetching, as last fetch is < one week')
        return
    logging.info('Fetching studios')
    # fake browser
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

    # first fetch all venice beach locations
    locations_venice = requests.get('https://www.venicebeach-fitness.de')
    soup = bs4.BeautifulSoup(locations_venice.content, features="lxml")
    studios_html = soup.findAll('a', {'class':"dropdown-item"})
    studios_urls = [html['href'] for html in studios_html]
    studios_urls = [url for url in studios_urls if 'club' in url]
    threads = pool.ThreadPool(len(studios_urls)+1)
    res1 = threads.map(get_studio_id_venice, studios_urls)
    res1 = [x for x in res1 if not x is None]

    # now fetch all fitbase locations
    locations_fitbase = requests.get('https://fitbase.fitness', headers=headers)
    soup = bs4.BeautifulSoup(locations_fitbase.content, features="lxml")
    studios_html = soup.findAll('a', {'class':"nav-link nav-link-second-level mx-2"})
    studios_urls = [html['href'] for html in studios_html if 'studios' in html['href']]
    threads = pool.ThreadPool(len(studios_urls)+1)
    res2 = threads.map(get_studio_id_fitbase, studios_urls)
    res2 = [x for x in res2 if not x is None]

    try:
        res1 = sorted(res1, key=lambda x:int(list(x.keys())[0]))
        res2 = sorted(res2, key=lambda x:int(list(x.keys())[0]))
    except:
        pass
    studios = {}
    for studio in res1 + res2:
        if studio is None: continue
        studios.update(studio)
    utils.write_studios(studios)

@forward_exception
def get_ids():
    ids = set()
    ids = list(utils.load_studios())
    return ids
    # alternative: load only active studios
    users =  [f for f in os.listdir('./users/') if f.endswith('.json')]
    for user in users:
        data = utils.load_user(user[:-5])
        last_access = data.get('access', [0])[-1]
        delta_days = (time.time()-last_access)//(24*60*60)
        studio = data.get('studio')

        if studio and delta_days<30:
            ids.add(studio)
    return ids

@forward_exception
def get_checked_in_users(ids=None):
    url = "https://venicebeach.api.actinate.com/gym/v1/studios/{id}?lang=de"

    settings = utils.load_settings()
    email = settings['email']
    password = settings['password']
    if ids is None:
        ids = get_ids()
        if len(ids)==0:
            return
        ids = set([int(id) for id in ids])


    headers = {
        'Host': 'oauth.actinate.com',
        'accept': '*/*',
        'content-type': 'application/x-www-form-urlencoded',
        'user-agent': 'VeniceBeach/12929 CFNetwork/1498.700.2 Darwin/23.6.0',
        'accept-language': 'de-DE,de;q=0.9',
    }

    data = {
        'grant_type': 'password',
        'username': email,
        'password': password,
        'client_id': 'venicebeachV2',
        'client_secret': settings['client_secret'],
        'app_version': '6.5.0',
        'os_version': '17.6.1',
        'os': 'ios',
    }

    # this data will be used to login
    response = requests.post('https://oauth.actinate.com/v6/oauth/token', headers=headers, params=(('lang', 'de'),), data=data)
    assert response.ok, f'login response was not ok, was {response.status_code}'

    # this is your bearer token, we need it to log in
    token = response.json()['access_token']

    headers = CaseInsensitiveDict()
    headers["Host"] = "venicebeach.api.actinate.com"
    headers["accept"] = "*/*"
    headers["user-agent"] = "VeniceBeach/7114 CFNetwork/1325.0.1 Darwin/21.1.0"
    headers["accept-language"] = "de-DE,de;q=0.9"
    headers["authorization"] = f"Bearer {token}"

    # now request the current studio status
    for id in ids:
        errors = 0
        while errors<3:
            try:
                logging.info(f'fetching {id}')
                csv_file = f'./data/studio_{id}.csv'
                resp = requests.get(url.format(id=id), headers=headers)
                assert resp.ok, f'fetch response was not ok, was {resp.status_code}'
                n_curr = resp.json()['studio']['checkedInUsers']['current']
                n_max = resp.json()['studio']['checkedInUsers'].get('max', 250)
                # print(resp.json()['studio']['checkedInUsers'])

                with open(csv_file, 'a') as f:
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f'{now};{n_curr};{n_max}\n')
                time.sleep(5)  # sleep 5 seconds for good measures
                break
            except:
                errors += 1
                time.sleep(15)  # sleep 15 seconds for good measures
                continue
        if errors>=3:
            msg = f'Could not load Studio {id}: <code>Code: {resp.status_code}\n{resp.text[:2000]}</code>'
            telegram_send.send(messages = [msg], parse_mode='html')

    return


class MemberCountPoller(threading.Thread):

    def __init__(self):
        fetcher = threading.Thread(target=fetch_studios)
        fetcher.start()
        os.makedirs('./data/', exist_ok=True)
        os.makedirs('./users/', exist_ok=True)
        self.wait = 5
        super().__init__()


    def run(self):
        # prevent thread from running twice
        self.lock = FileLock('./data/lock')
        self.lock.acquire(1)
        while True:
            try:
                get_checked_in_users()
            except Exception as e:
                pass
            for _ in range(self.wait*60):
                time.sleep(1)
