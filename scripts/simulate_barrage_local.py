"""
在同一进程内使用 Flask test_client 模拟弹幕交互，避免网络套接字问题。
此脚本会：
  - 创建会话（POST /api/session）
  - 循环发送若干条弹幕（POST /api/bullet-screen）
  - 每发送一条立即调用 /api/chat 并打印 AI 响应

用法：
  python scripts/simulate_barrage_local.py --count 10
"""
import time
import random
import argparse
import os
import importlib.util

# 动态加载顶层 app 模块，避免模块导入路径问题
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('app', os.path.join(ROOT, 'app.py'))
app_mod = importlib.util.module_from_spec(spec)
# 将项目根目录加入 sys.path，以便 app.py 的相对导入生效
import sys
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
spec.loader.exec_module(app_mod)
app = getattr(app_mod, 'app')

def random_msg():
    msgs = ['这件怎么卖？','有优惠吗？','能讲一下产地吗？','能试吃吗？','包装怎样？','色泽不错，多少钱一斤？','主播介绍一下吧']
    return random.choice(msgs)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--count', type=int, default=10)
    args = p.parse_args()

    with app.test_client() as c:
        # 创建会话
        resp = c.post('/api/session', json={'host_name':'本地模拟','live_theme':'测试专场','products':[{'name':'示例','price':10}]})
        if resp.status_code != 200:
            print('创建会话失败', resp.status_code, resp.data.decode())
            return
        data = resp.get_json()
        session_id = data.get('session_id')
        print('创建会话:', session_id)

        for i in range(args.count):
            who = f'观众{random.randint(100,999)}'
            msg = random_msg()
            # 发送弹幕
            r = c.post('/api/bullet-screen', json={'session_id': session_id, 'username': who, 'message': msg})
            print(f'[{i+1}] 发送: {who} -> {msg}  状态:{r.status_code}')
            # 直接调用 /api/chat
            cr = c.post('/api/chat', json={'session_id': session_id, 'message': msg})
            try:
                cj = cr.get_json()
            except Exception:
                cj = {'error': '无响应'}
            print('    AI 返回:', cr.status_code, cj.get('response') or cj.get('error'))
            time.sleep(0.3)

if __name__ == '__main__':
    main()
