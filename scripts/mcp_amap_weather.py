# -*- coding: utf-8 -*-
"""
基于 Qwen Agent（MCP SDK）的示例脚本：调用阿里云百炼 MCP 的 Amap Maps 服务查询杭州天气。
依赖：
  pip install -U "qwen-agent[gui,rag,cli]"
  （或最小安装：pip install -U qwen-agent）

环境变量：
  DASHSCOPE_API_KEY=<你的阿里云DashScope密钥>

用法（PowerShell）：
  $env:DASHSCOPE_API_KEY = "<你的Key>"
  python scripts/mcp_amap_weather.py
"""
import os
from typing import List, Dict, Any

try:
    from qwen_agent.agents import Assistant  # type: ignore
except Exception as e:
    raise SystemExit("缺少依赖 qwen-agent，请先安装：pip install -U \"qwen-agent[gui,rag,cli]\"") from e

try:
    # 便于本地从 .env 读取 Key
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


def query_hangzhou_weather() -> None:
    api_key = os.getenv('DASHSCOPE_API_KEY') or os.getenv('ALI_DASHSCOPE_API_KEY')
    if not api_key:
        print("错误：请先设置环境变量 DASHSCOPE_API_KEY（或 ALI_DASHSCOPE_API_KEY）")
        return
    # 若仅配置了 ALI_DASHSCOPE_API_KEY，则同步给 DASHSCOPE_API_KEY 以满足 qwen-agent 内部校验
    if not os.getenv('DASHSCOPE_API_KEY') and os.getenv('ALI_DASHSCOPE_API_KEY'):
        os.environ['DASHSCOPE_API_KEY'] = os.getenv('ALI_DASHSCOPE_API_KEY') or ''

    llm_cfg: Dict[str, Any] = {'model': 'qwen-max'}
    system = (
        '你是一个天气查询智能体。你将调用名为 amap-maps 的 MCP 服务来查询天气信息。'
        '请优先调用工具获取结构化的天气数据，并对天气情况做简明解释。'
    )

    # 使用 mcp 单数路径（部分环境下 mcps 会 404）
    tools: List[Dict[str, Any]] = [{
        "mcpServers": {
            "amap-maps": {
                "url": "https://dashscope.aliyuncs.com/api/v1/mcp/amap-maps/sse",
                "headers": {"Authorization": f"Bearer {api_key}"}
            }
        }
    }]

    bot = Assistant(
        llm=llm_cfg,
        name='天气查询智能体',
        description='天气信息查询',
        system_message=system,
        function_list=tools,
    )

    messages: List[Dict[str, Any]] = []
    query = "今天是几号？查询杭州今日的天气情况"
    messages.append({'role': 'user', 'content': query})

    print("正在查询杭州今日天气...")
    print("=" * 50)

    all_responses: List[Any] = []
    for response in bot.run(messages):
        all_responses.append(response)

    final_content = ""
    if all_responses:
        last_response = all_responses[-1]
        if isinstance(last_response, list):
            for item in last_response:
                if isinstance(item, dict) and item.get('role') == 'assistant' and 'content' in item:
                    final_content = item['content']
        elif isinstance(last_response, dict) and 'content' in last_response:
            final_content = last_response['content']

    if final_content:
        print(final_content)
    else:
        print("未能获取到天气信息")


if __name__ == '__main__':
    query_hangzhou_weather()
