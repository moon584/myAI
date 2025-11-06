"""
聊天路由 - 处理AI对话
"""
from flask import Blueprint, request, jsonify
import uuid
import json
from database import db
from services import ai_service
from utils.logger import get_logger
import os
from services import bullet_ws as _bullet_ws
from services import baidu_tts

logger = get_logger(__name__)

chat_bp = Blueprint('chat', __name__, url_prefix='/api')



@chat_bp.route('/chat', methods=['POST'])
def chat():
    """与AI对话"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "请求数据不能为空"}), 400
        
        session_id = data.get('session_id')
        message = data.get('message')
        
        # 验证session_id格式
        if not session_id:
            return jsonify({"error": "会话ID不能为空"}), 400
        
        try:
            uuid.UUID(session_id)
        except ValueError:
            return jsonify({"error": "无效的会话ID格式"}), 400
        
        # 验证消息
        if not message or not isinstance(message, str):
            return jsonify({"error": "消息不能为空"}), 400
        
        message = message.strip()
        if not message:
            return jsonify({"error": "消息不能为空"}), 400
        
        if len(message) > 500:
            return jsonify({"error": "消息长度不能超过500字符"}), 400
        
        logger.info(f"收到聊天请求 - 会话: {session_id}, 消息长度: {len(message)}")
        
        # ========== 第一步：检查敏感词 ==========
        is_sensitive, matched_words = db.check_sensitive_words(message)
        if is_sensitive:
            logger.warning(f"⚠️ 消息包含敏感词: {matched_words}")
            return jsonify({
                "error": "您的消息包含不当内容，请文明用语。",
                "sensitive": True
            }), 400
        
        # ========== 第二步：检查FAQ白名单 ==========
        faq_answer = db.get_whitelist_answer(session_id, message)
        if faq_answer:
            logger.info(f"✅ 返回FAQ答案 - 会话: {session_id}")
            db.cache_qa(session_id, message, faq_answer)
            db.save_conversation(session_id, message, faq_answer)
            # 语音模块已移除，保持字段兼容返回 null
            audio_url = None
            return jsonify({"response": faq_answer, "faq": True, "audio_url": audio_url})
        
        # ========== 第三步：检查问答缓存 ==========
        cached_answer = db.get_cached_answer(session_id, message)
        if cached_answer:
            logger.info(f"✅ 返回缓存答案 - 会话: {session_id}")
            db.save_conversation(session_id, message, cached_answer)
            # 语音模块已移除，保持字段兼容返回 null
            audio_url = None
            return jsonify({"response": cached_answer, "cached": True, "audio_url": audio_url})
        
        # ========== 第四步：调用AI API ==========
        # 获取会话信息
        session = db.get_session(session_id)
        if not session:
            return jsonify({"error": "会话不存在"}), 404
        
        logger.info(f"调用AI API - 会话: {session_id}")
        ai_response = ai_service.call_api(message, session)
        
        if not ai_response:
            return jsonify({"error": "AI服务暂时不可用，请稍后重试"}), 503
        
        logger.info(f"✅ AI响应成功 - 会话: {session_id}")
        
        # ========== 第五步：缓存问答对 ==========
        db.cache_qa(session_id, message, ai_response)
        db.save_conversation(session_id, message, ai_response)

        # ====== 新增：调用百度 TTS 合成短语音，并保留 audio_url 字段 ======
        audio_url = None
        try:
            # 保存到 static/audio 目录，文件名基于 uuid
            out_dir = os.path.join(os.getcwd(), 'static', 'audio')
            os.makedirs(out_dir, exist_ok=True)
            filename = f"tts_{uuid.uuid4().hex}.wav"
            out_path = os.path.join(out_dir, filename)
            baidu_tts.synthesize(ai_response, out_path=out_path)
            # 返回给前端的可访问 URL（Flask 静态路由下）
            audio_url = f"/static/audio/{filename}"
        except Exception as e:
            logger.warning(f'Baidu TTS 合成失败: {e}', exc_info=True)
            audio_url = None

        return jsonify({
            "response": ai_response,
            "status": "success",
            "audio_url": audio_url
        })
        
    except Exception as e:
        logger.error(f"聊天处理异常: {str(e)}", exc_info=True)
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


@chat_bp.route('/bullet-screen', methods=['POST'])
def add_bullet_screen():
    """添加弹幕"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "请求数据不能为空"}), 400
        
        session_id = data.get('session_id')
        username = data.get('username')
        message = data.get('message')
        
        if not session_id or not username or not message:
            return jsonify({"error": "缺少必要参数"}), 400
        
        # 验证session_id格式
        try:
            uuid.UUID(session_id)
        except ValueError:
            return jsonify({"error": "无效的会话ID"}), 400
        
        logger.info(f"收到弹幕 - 会话: {session_id}, 用户: {username}")
        
        # 检查是否在黑名单（兼容 db.is_blacklisted 返回 bool 或 (bool, reason)）
        try:
            res = db.is_blacklisted(session_id, username, message)
            if isinstance(res, (list, tuple)):
                is_blocked, reason = res[0], (res[1] if len(res) > 1 else None)
            else:
                is_blocked, reason = bool(res), None
        except Exception as e:
            logger.warning(f"检查黑名单时出错: {e}")
            is_blocked, reason = False, None

        if is_blocked:
            logger.warning(f"⚠️ 弹幕被拦截 - 原因: {reason}")
            return jsonify({"status": "blocked", "reason": reason})
        
        # 添加弹幕
        if db.add_bullet_screen(session_id, username, message):
            # 广播到 WebSocket 客户端（若已启用）以实现实时推送
            try:
                if _bullet_ws:
                    _bullet_ws.broadcast({
                        'type': 'bullet',
                        'session_id': session_id,
                        'username': username,
                        'message': message
                    })
            except Exception:
                logger.warning('弹幕广播失败', exc_info=True)
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "添加弹幕失败"}), 500
            
    except Exception as e:
        logger.error(f"添加弹幕异常: {str(e)}", exc_info=True)
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500

@chat_bp.route('/bullet-screen/pending', methods=['GET'])
def get_pending_bullet_screens():
    """获取待处理的弹幕"""
    try:
        session_id = request.args.get('session_id')
        limit = request.args.get('limit', 10, type=int)
        
        if not session_id:
            return jsonify({"error": "缺少session_id参数"}), 400
        
        # 验证session_id格式
        try:
            uuid.UUID(session_id)
        except ValueError:
            return jsonify({"error": "无效的会话ID"}), 400
        
        logger.info(f"获取待处理弹幕 - 会话: {session_id}, 限制: {limit}")
        
        # 获取弹幕
        bullet_screens = db.get_pending_bullet_screens(session_id, limit)
        
        return jsonify({
            "session_id": session_id,
            "bullet_screens": bullet_screens,
            "count": len(bullet_screens)
        })
        
    except Exception as e:
        logger.error(f"获取弹幕异常: {str(e)}", exc_info=True)
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


# 语音模块已移除：/api/tts 文件与状态端点不再提供。
