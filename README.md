# 乡聚助农 · 小聚AI助手

一个面向直播电商/助农场景的全栈应用：左侧配置直播信息与商品，右侧即时生成自然、不生硬的直播话术。内置 FAQ 命中统计、问答缓存归一化与 FAQ 推荐，支持商品类型感知的快捷建议与键盘快捷键。

---

## 功能亮点

- 话术生成
  - 商品类型感知的快捷建议（水果/蔬菜/肉类/杂粮/加工食品/手工艺品，文案与语气自动调整）
  - 问答缓存（问题归一化 + 哈希）提升复用率
  - FAQ 白名单优先返回与命中统计
  - 自动 FAQ 推荐（基于高频未覆盖的问答）
- 语音合成（TTS）
  - 百度语音（Baidu TTS）。
    - 若要接入百度，请把新的 TTS 实现放在 `services/` 下并在 `.env` 中配置相应密钥与参数。
- 前端体验
  - 固定头尾、可折叠侧栏，浮动按钮与键盘快捷键（Alt+L、Alt+1..5）
  - 商品自动编号与选择器，快捷建议精确到第几号商品

---

## 目录结构

小聚AI方案三/
├─ app.py                # 应用入口（注册蓝图、静态资源、健康检查）
├─ config.py             # 配置管理（.env）
├─ routes/               # Flask Blueprints（聊天/FAQ/会话/统计）
├─ services/             # AI 服务封装与系统提示词（persona：小聚）
# 小聚AI助手（精简版）

## 快速开始（Windows / PowerShell）

1. 激活虚拟环境：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
. .\.venv\Scripts\Activate.ps1
```

2. 安装依赖（若尚未安装）：

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
```

3. 配置环境变量：在项目根目录编辑 `.env`（示例已存在）。必须至少填写：

- `DEEPSEEK_API_KEY`（或其它 AI 服务凭证）
- 数据库连接 `DB_HOST/DB_USER/DB_PASSWORD/DB_NAME`（若使用默认 sqlite 则可跳过）
- Baidu TTS：`BAIDU_TTS_API_KEY` 和 `BAIDU_TTS_SECRET_KEY`（如需语音合成）

4. 启动服务：

```powershell
Set-Location -Path "${PWD}"
$env:PYTHONPATH = (Get-Location).Path
.venv\Scripts\python app.py
```

5. 打开浏览器查看：

http://127.0.0.1:5000/static/live_sim.html

（或直接使用 API: POST `/api/session` / POST `/api/chat` - 示例见下）

## 测试 Baidu TTS（无需启动 Flask）

示例：在激活虚拟环境后直接运行：

```powershell
.venv\Scripts\python .\scripts\run_baidu_demo.py
```

成功时会在 `static/audio/` 生成一个 `.wav` 文件。

## 演示 `/api/chat` 集成（in-process）

有一个方便的内置演示脚本，会在内部使用 Flask 的 `test_client`：

```powershell
.venv\Scripts\python .\scripts\demo_chat_with_tts.py
```

该脚本会创建会话、向 `/api/chat` 发起一次请求，并打印返回 JSON（包含 `audio_url`）以及是否在磁盘上生成了音频。

## 静态直播模拟页面

- 页面：`static/live_sim.html` （在浏览器打开 `http://127.0.0.1:5000/static/live_sim.html`）
- 脚本：`scripts/simulate_barrage.py`（向运行中的服务发送弹幕）

## 恢复或启用 WebSocket 实时推送

项目包含一个可选的广播模块 `services/bullet_ws.py`，默认不在 `app.py` 启动时自动运行（以避免在部分 Windows 环境下的 asyncio 线程问题）。若你希望启用：

1. 在 `.venv` 中确保安装 `websockets`：
```powershell
.venv\Scripts\pip install websockets
```
2. 编辑 `app.py` 将 `bullet_ws = None` 的行替换回原始导入逻辑并重启服务。启动后前端会尝试连接 WebSocket：`ws://127.0.0.1:6789`。

## 常见命令一览

激活虚拟环境（PowerShell）：
```powershell
. .\.venv\Scripts\Activate.ps1
```
启动服务：
```powershell
.venv\Scripts\python app.py
```
运行 Baidu TTS demo：
```powershell
.venv\Scripts\python .\scripts\run_baidu_demo.py
```
内置演示（会话 + chat + TTS）：
```powershell
.venv\Scripts\python .\scripts\demo_chat_with_tts.py
```

## 联系与贡献

如需扩展 Baidu TTS 参数（音色/编码/采样率），请修改 `services/baidu_tts.py` 并在 `.env` 中添加/调整对应键。

欢迎在本仓库基础上继续改进前端体验、引入持久化队列或替换 AI 模型后端。
