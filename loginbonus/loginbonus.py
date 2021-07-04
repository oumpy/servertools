#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from datetime import date, timedelta
import calendar
from slack_sdk import WebClient
import argparse
import subprocess
import re
from collections import defaultdict
import gzip

# Example:
# python loginbonus.py
#

post_to_slack = True
slacktoken_file = 'slack_token'

excluded_members = set()

channel_name = '自動アナウンス'
appdir = 'var/loginbonus/'
base_dir = os.path.join(os.environ['HOME'], appdir)
history_dir = os.path.join(base_dir, 'history/')
history_file_format = '{}.txt' # date
ts_file = 'ts-loginbonus'
excluded_members_file = 'excluded_members.txt'
post_format = {
    'post_header_format' : '＊【{}のログインボーナス】＊',
    'post_line_format' : '<@{}> さん', # member
    'post_nobody' : 'ログインした人はいません。',
    'post_footer' : '\n以上の方にログインボーナスが付与されます。\nおめでとうございます！ :sparkles:',
}
N_ranking = 5
post_format_ranking = {
    'post_header_format' : '＊【{}のログインボーナス ベスト{}】＊',
    'post_line_format' : '<@{}> さん', # member
    'post_line_format' : '{}位：{}<@{}> さん ({}ポイント)', # rank, mark, slackid, point
    'post_remain_format' : 'その他2ポイント以上：{}',
    'rank_marks' : [':first_place_medal:',':second_place_medal:',':third_place_medal:'],
    'other_mark' : ':sparkles:',
    'post_nobody' : 'ログインした人はいませんでした :scream:',
    'post_footer' : '\nおめでとうございます！ :tada:',
}
post_format_list = {
    'post_header_format' : '＊【現在の利用者一覧】＊',
    'post_footer' : '以上、{}名です。 :sparkles:',
}

loginname_format = re.compile(r'u[0-9]{6}[a-z]')

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

def auth_logins(day):
    authlogs = (
        ['/var/log/auth.log']
        + ['/var/log/auth.log.{}'.format(i) for i in range(1,10)]
        + ['/var/log/auth.log.{}.gz'.format(i) for i in range(1,10)]
    )
    auth_lines = []
    for authlog in authlogs:
        if os.path.isfile(authlog):
            if authlog[-3:] == '.gz':
                f = gzip.open(authlog, 'rt')
            else:
                f = open(authlog)
            auth_lines.extend(f.readlines())            
            f.close()
    logins = set()
    month_str = day.strftime('%b')
    day_str = str(int(day.strftime('%d')))
    regex = re.compile(r'\s*Accepted publickey for (\S+) from')
    for line in auth_lines:
        m, d = line.split()[:2]
        if m == month_str and d == day_str:
            hit = regex.match(line.split(':')[3])
            if hit:
                logins.add(hit.groups()[0])
    return logins

def login_members(members, name, day, auth):
    daystr = day.strftime('%Y%m%d')
    since = daystr + '000000'
    till = daystr + '235959'
    last_out = subprocess.run(
                    ['last', '-s', since, '-t', till],
                    encoding='utf-8', stdout=subprocess.PIPE,
                    ).stdout.splitlines()[:-2]
    logins = { line.split()[0] for line in last_out }
    if auth:
        logins |= auth_logins(day)
    ret = set()
    for m in members:
        m_name = name[m].strip()
        if not m_name:
            continue
        m_loginname = m_name.split('_')[-1]
        if loginname_format.fullmatch(m_loginname) and m_loginname in logins:
            groups = subprocess.run(
                    ['groups', m_loginname],
                    encoding='utf-8', stdout=subprocess.PIPE,
                    ).stdout.split()[2:]
            if 'users' in groups:
                ret.add(m)

    return ret

def login_days(members, name, endofmonth, auth):
    year = endofmonth.year
    month = endofmonth.month
    days = endofmonth.day
    scores = defaultdict(int)
    for day in range(1,days+1):
        for m in login_members(members, name, date(year,month,day), auth):
            scores[m] += 1

    return sorted(scores.items(), key=lambda x: -x[1])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--noslack', help='do not post to slack.',
                        action='store_true')
    parser.add_argument('--mute', help='post in thread without showing on channel.',
                        action='store_true')
    parser.add_argument('--solopost',
                        help='post an idependent message out of the thread, not destroying previous thread info',
                        action='store_true')
    parser.add_argument('--list', help='list all the members.',
                        action='store_true')
    parser.add_argument('-c', '--channel', default=channel_name,
                        help='slack channel to read & post.')
    parser.add_argument('-o', '--outchannel', default=None,
                        help='slack channel to post.')
    parser.add_argument('--slacktoken', default=None,
                        help='slack bot token.')
    parser.add_argument('--oncemore', action='store_true',
                        help='execute even if it has been already done for the day.')
    parser.add_argument('--day', default=None,
                        help='specify a day in %%Y%%m%%d format.')
    parser.add_argument('--ranking', action='store_true',
                        help='show monthly ranking.')
    parser.add_argument('--auth', action='store_true',
                        help='Use auth.log, in addition to wtmp.log.')
    args = parser.parse_args()

    if args.noslack:
        post_to_slack = False
    channel_name = args.channel

    slacktoken_file_path = os.path.join(base_dir, slacktoken_file)
    history_file_path_format = os.path.join(history_dir, history_file_format)
    excluded_members_file_path = os.path.join(base_dir, excluded_members_file)

    if args.day and isinstance(args.day,str) and len(args.day)>=8:
        year = int(args.day[:4])
        month = int(args.day[4:6])
        day = int(args.day[6:8])
        today = date(year, month, day)
    else:
        today = date.today() - timedelta(days=1) # actually yesterday
    ADfirst = date(1,1,1) # AD1.1.1 is Monday
    today_id = (today-ADfirst).days
    history_file_path = history_file_path_format.format(today_id)

    if (not args.list and not args.ranking) and (not args.oncemore) and os.path.exists(history_file_path):
        exit()
    if args.list:
        post_format.update(post_format_list)
    elif args.ranking:
        post_format.update(post_format_ranking)
    for k, v in post_format.items():
        globals()[k] = v

    if args.slacktoken:
        token = args.slacktoken
    else:
        with open(slacktoken_file_path, 'r') as f:
            token = f.readline().rstrip()
    web_client = WebClient(token=token)
    channel_id = get_channel_id(web_client, channel_name)
    my_id = web_client.api_call('auth.test')['user_id']

    logins = set()
    if os.path.exists(excluded_members_file_path):
        with open(excluded_members_file_path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                excluded_members.add(line.rstrip().split()[1])
    members_info = web_client.api_call('users.list')['members']
    name = dict()
    for member in members_info:
        display_name = member['profile']['display_name']
        real_name = member['profile']['real_name']
        if display_name:
            name[member['id']] = display_name
        else:
            name[member['id']] = real_name
    members = set([ member['id'] for member in members_info if not member['deleted']]) - excluded_members
    members.discard(my_id)
    N_members = len(members)
    if args.list:
        header_data = (None,)
        logins = set(members)
    elif args.ranking:
        thismonth_days = calendar.monthrange(today.year, today.month)[1]
        thismonthend = date(today.year, today.month, thismonth_days)
        prev_n, prev_s = -1, 50
        ranking = login_days(members, name, thismonthend, args.auth)
        logins = []
        remain_str_list = []
        for n, r in enumerate(ranking):
            m, s = r
            if s == prev_s:
                if prev_n < len(rank_marks):
                    mark = rank_marks[prev_n]
                else:
                    mark = other_mark
                logins.append((prev_n+1, mark, m, s))
            elif n < N_ranking:
                if n < len(rank_marks):
                    mark = rank_marks[n]
                else:
                    mark = other_mark
                prev_n, prev_s = n, s
                logins.append((n+1, mark, m, s))
            elif s >= 2:
                remain_str_list.append('<@{}>'.format(m))
            else:
                break
        if remain_str_list:
            post_footer =  post_remain_format.format('、'.join(remain_str_list)) + '\n' + post_footer
        header_data = ('{}月'.format(today.month), N_ranking)
    else:
        logins = login_members(members, name, today, args.auth)
        # write the new history
        with open(history_file_path, 'w') as f:
            for m in logins:
                print(m, file=f)
        header_data = ('{}月{}日'.format(today.month, today.day),)

    post_lines = [post_header_format.format(*header_data)]
    if logins:
        for m in logins:
            if isinstance(m, tuple):
                post_lines.append(post_line_format.format(*m))
            else:
                post_lines.append(post_line_format.format(m))
        post_lines.append(
            post_footer.format(N_members)
        )
    else:
        post_lines.append(post_nobody)
    message = '\n'.join(post_lines)

    if not post_to_slack:
        print('App ID:', my_id)
        print(message)
    elif len(post_lines) > 2:
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
                if not args.solopost:
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
