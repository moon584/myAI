"""
简单的弹幕模拟脚本：向本地后端 `/api/bullet-screen` 周期性发送随机弹幕，用于压力或功能演示。
使用方法（PowerShell）：
  $env:API_BASE='http://127.0.0.1:5000'; python scripts/simulate_barrage.py --session <session_id>
如果未提供 session，会尝试创建一个临时会话（需要 /api/session 可用）。
"""
import time
import random
import argparse
import requests

DEFAULT_API = 'http://127.0.0.1:5000'

def random_msg():
    msgs = ['这件怎么卖？','有优惠吗？','能讲一下产地吗？','能试吃吗？','包装怎样？','色泽不错，多少钱一斤？','主播介绍一下吧']
    return random.choice(msgs)

def create_session(api_base, host='模拟主播', theme='模拟专场'):
    url = api_base.rstrip('/') + '/api/session'
    payload = {'host_name': host, 'live_theme': theme, 'products':[{'name':'示例商品','price':10}]}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()['session_id']

def send_bullet(api_base, session_id, username, text):
    url = api_base.rstrip('/') + '/api/bullet-screen'
    payload = {'session_id': session_id, 'username': username, 'message': text}
    r = requests.post(url, json=payload, timeout=5)
    return r.status_code == 200

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--api', default=None)
    p.add_argument('--session', default=None)
    p.add_argument('--interval', type=float, default=1.5)
    p.add_argument('--count', type=int, default=0, help='发送次数，0 为无限')
    args = p.parse_args()
    api = args.api or DEFAULT_API
    session = args.session
    if not session:
        try:
            session = create_session(api)
            print('已创建临时 session:', session)
        except Exception as e:
            print('创建会话失败，请先手动创建会话或指定 --session', e)
            return

    i = 0
    try:
        while True:
            if args.count and i >= args.count:
                break
            who = '观众%03d' % random.randint(1,999)
            m = random_msg()
            ok = send_bullet(api, session, who, m)
            print(i+1, who, m, 'OK' if ok else 'FAIL')
            i += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('已停止')

if __name__ == '__main__':
    main()
