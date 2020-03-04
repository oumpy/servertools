#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from collections import defaultdict
import os
from datetime import date, timedelta
from slack import WebClient
import argparse
import random
from bisect import bisect_left

# Example:
# python relayscheduler.py
#

post_to_slack = True
# update_link = True
slacktoken_file = 'slack_token'

min_interval_weeks = 4
min_grace = 3 # days: 4の場合、木曜までなら翌週月曜から、それ以後なら翌々週。
relaydays = [0, 1, 2, 3, 4] # cronとは曜日番号が違うので注意。
# 平日に投稿、水曜に発表、月曜にリマインド、を想定。

weekdays = ['月', '火', '水', '木', '金', '土', '日']
year_start_day =  104 # 1月4日から
year_final_day = 1223 # 12月23日まで

# relative probs
class_probs = [1.0, 0.5, 0.5] # regulars, OBs, accosiates

channel_name = 'python会-リレー投稿'
appdir = '/var/relaytools/'
base_dir = os.environ['HOME'] + appdir
history_dir = base_dir + 'history/'
memberlist_file = 'memberlist.txt'
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

def choose_writer(members, probs):
    members = list(members)
    accum_prob = []
    s = 0
    for m in members:
        s += probs[m]
        accum_prob.append(s)
    p = random.random() * accum_prob[-1]
    n = bisect_left(accum_prob, p)
    return members[n]

def next_writers(members, probs, n):
    if len(members) < n:
        return list(members) # buggy.
    else:
        ret = []
        for _ in range(n):
            w = choose_writer(members, probs)
            ret.append(w)
            members.remove(w)
        return ret

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--noslack', help='do not post to slack.',
                        action='store_true')
    parser.add_argument('-r', '--reminder', help='remind.',
                        action='store_true')
    parser.add_argument('--mute', help='post in thread without showing on channel.',
                        action='store_true')
    parser.add_argument('-c', '--channel', default=channel_name,
                        help='slack channel to post.')
    parser.add_argument('--slacktoken', default=None,
                        help='slack bot token.')
    args = parser.parse_args()

    if args.noslack:
        post_to_slack = False
    channel_name = args.channel

    memberlist_file_path = base_dir + memberlist_file
    history_file_path_format = history_dir + history_file_format
    slacktoken_file_path = base_dir + slacktoken_file

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
    done_users = set()
    for i in range(min_interval_weeks):
        past_id = week_id - 1 - i
        hf = history_file_path_format % past_id
        if os.path.exists(hf):
            with open(hf, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    date, person = line.rstrip().split()[:2]
                    done_users.add(person)

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
        # read member prob list
        member_probs = defaultdict(lambda: 1)
        if os.path.exists(memberlist_file_path):
            with open(memberlist_file_path, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    nickname, slackid, kind = line.rstrip().split('\t')[:3]
                    member_probs[slackid] = class_probs[int(kind)]

        channel_info = web_client.api_call('channels.info', params={'channel':channel_id})['channel']
        # ensure I am a member of the channel.
        # if not channel_info['is_member']:
        #     return
        members = set(channel_info['members']) - done_users
        members.discard(my_id)
        writers = next_writers(members, member_probs, len(relaydays))
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
        print(message)
