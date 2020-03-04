#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from collections import defaultdict
import os
from datetime import date, timedelta
from slack import WebClient
import argparse
# from random import randrange
from bisect import bisect_right
import hashlib
 
# Example:
# python relayscheduler.py
#

post_to_slack = True
# update_link = True
slacktoken_file = 'slack_token'

lookback_weeks = 8
min_grace = 3 # days: 4の場合、木曜までなら翌週月曜から、それ以後なら翌々週。
relaydays = [0, 1, 2, 3, 4] # cronとは曜日番号が違うので注意。
# 平日に投稿、水曜に発表、月曜にリマインド、を想定。

weekdays = ['月', '火', '水', '木', '金', '土', '日']
year_first_day =  104 # 1月4日から
year_last_day = 1223 # 12月23日まで

channel_name = 'python会-リレー投稿'
appdir = '/var/relaytools/'
base_dir = os.environ['HOME'] + appdir
history_dir = base_dir + 'history/'
#memberlist_file = 'memberlist.txt'
ts_file = 'ts-relay'
history_file_format = 'week-%d.txt' # week ID.
week_str = ['今週', '来週', '来々週']
post_format = {
    'post_header_format' : '＊【%sのリレー投稿 担当者のお知らせ】＊',
    'post_line_format' : '%d月%d日(%s)：<@%s> さん', # month, day, weekday, writer
    'post_nobody' : '執筆予定者はいません。',
    'post_footer' : '\nよろしくお願いします！ :sparkles:', # winner
}
post_format_reminder = {
    'post_header_format' : '*【%sのリレー投稿 リマインダ】*',
}

def get_channel_list(client, limit=200):
    params = {
        'exclude_archived': 'true',
        'types': 'public_channel',
        'limit': str(limit),
        }
    channels = client.api_call('conversations.list', params=params)
    if channels['ok']:
        return channels['channels']
    else:
        return None

def get_channel_id(client, channel_name):
    channels = filter(lambda x: x['name']==channel_name , get_channel_list(client))
    target = None
    for c in channels:
        if target is not None:
            break
        else:
            target = c
    if target is None:
        return None
    else:
        return target['id']

def next_writers(members, n, lastwriter):
    def hashf(key):
        return hashlib.sha256(key.encode()).hexdigest()
    hashed_members = [ (hashf(m),m) for m in members ]
    hashed_members.sort()
    N = len(members)
    hashed_lastwriter = (hashf(lastwriter), lastwriter)
    s = bisect_right(hashed_members, hashed_lastwriter)
    return [ hashed_members[(s+i) % N][1] for i in range(n) ]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--noslack', help='do not post to slack.',
                        action='store_true')
    parser.add_argument('-r', '--reminder', help='remind.',
                        action='store_true')
    parser.add_argument('--mute', help='post in thread without showing on channel.',
                        action='store_true')
    parser.add_argument('-c', '--channel', default=channel_name,
                        help='slack channel to read & post.')
    parser.add_argument('-o', '--outchannel', default=None,
                        help='slack channel to post.')
    parser.add_argument('--slacktoken', default=None,
                        help='slack bot token.')
    args = parser.parse_args()

    if args.noslack:
        post_to_slack = False
    channel_name = args.channel

    # memberlist_file_path = base_dir + memberlist_file
    slacktoken_file_path = base_dir + slacktoken_file
    history_file_path_format = history_dir + history_file_format

    today = date.today()
    ADfirst = date(1,1,1) # AD1.1.1 is Monday
    today_id = (today-ADfirst).days
    thisweek_id = today_id // 7
    startday = today + timedelta(min_grace)
    startday += timedelta((7-startday.weekday())%7)
    date_id = (startday-ADfirst).days
    week_id = date_id // 7
    history_file_path = history_file_path_format % week_id

    if os.path.exists(history_file_path):
        args.reminder = True
    if args.reminder:
        #update_link = False
        for k, v in post_format_reminder.items():
            post_format[k] = v
    for k, v in post_format.items():
        globals()[k] = v

    # read the previous record
    recent_writers = []
    for i in range(-lookback_weeks, 0):
        past_id = week_id + i
        hf = history_file_path_format % past_id
        if os.path.exists(hf):
            with open(hf, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    date, person = line.rstrip().split()[:2]
                    recent_writers.append(person)
    if recent_writers:
        last_writer = recent_writers[-1]
    else:
        last_writer = ''

    if args.slacktoken:
        token = args.slacktoken
    else:
        with open(slacktoken_file_path, 'r') as f:
            token = f.readline().rstrip()
    web_client = WebClient(token=token)
    channel_id = get_channel_id(web_client, channel_name)
    my_id = web_client.api_call('auth.test')['user_id']

    writers_dict = dict()
    if args.reminder:
        while week_id >= thisweek_id:
            hf = history_file_path_format % week_id
            if os.path.exists(hf):
                with open(hf, 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        date, person = line.rstrip().split()[:2]
                        date = int(date)
                        writers_dict[date-date_id] = person
                break
            else:
                week_id -= 1
                date_id -= 7
        else:
            exit()
    else:
        channel_info = web_client.api_call('channels.info', params={'channel':channel_id})['channel']
        # ensure I am a member of the channel.
        # if not channel_info['is_member']:
        #     return
        members = set(channel_info['members'])
        members.discard(my_id)
        writers = next_writers(members, len(relaydays), last_writer)
        lastwriter = writers[-1]
        for i, d in enumerate(relaydays):
            writers_dict[d] = writers[i]
        # write the new history
        with open(history_file_path, 'w') as f:
            for d, u in writers_dict.items():
                print(date_id + d, u, file=f)

    post_lines = [post_header_format % week_str[week_id - thisweek_id]]
    if writers_dict:
        for d, writer in writers_dict.items():
            date = startday + timedelta(d)
            post_lines.append(post_line_format % (date.month, date.day, weekdays[d], writer))
        post_lines.append(
            post_footer
        )
    else:
        post_lines.append(post_nobody)
    message = '\n'.join(post_lines)

    if post_to_slack:
        if args.outchannel:
            channel_id = get_channel_id(web_client, args.outchannel)
        params={
            'channel': channel_id,
            'text': message,
        }
        os.chdir(history_dir)
        if os.path.isfile(ts_file):
            with open(ts_file, 'r') as f:
                ts = f.readline().rstrip()
                params['thread_ts'] = ts
                if not args.mute:
                    params['reply_broadcast'] = 'True'
        else:
            ts = None
        response = web_client.api_call(
            'chat.postMessage',
            params=params
        )
        posted_data = response.data
        if ts is None:
            ts = posted_data['ts']
            with open(ts_file, 'w') as f:
                print(ts, file=f)
        # elif os.path.isfile(ts_file):
        #     os.remove(ts_file)
    else:
        print('App ID:', my_id)
        print(message)
