"""
AI服务模块 - 处理与DeepSeek API的交互
"""
import requests
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class AIService:
    """AI服务类 - 封装DeepSeek API调用"""
    
    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY
        self.api_url = Config.DEEPSEEK_API_URL
        self.model = Config.DEEPSEEK_MODEL
    
    def call_api(self, prompt, session_context=None):
        """
        调用DeepSeek API
        
        Args:
            prompt: 用户问题
            session_context: 会话上下文（主播、主题、商品等）
            
        Returns:
            AI回复内容，失败返回None
        """
        try:
            # 构建系统提示词
            system_prompt = self._build_system_prompt(session_context)
            
            # 构建请求
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            payload = {
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.7,
                'max_tokens': 500
            }
            
            logger.info(f"调用AI API - 模型: {self.model}")
            
            # 发送请求
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # 提取回复
            if 'choices' in result and len(result['choices']) > 0:
                ai_response = result['choices'][0]['message']['content']
                logger.info(f"✅ AI API调用成功")
                return ai_response
            else:
                logger.error(f"AI API响应格式异常: {result}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("AI API调用超时")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"AI API请求失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"AI API调用异常: {str(e)}", exc_info=True)
            return None
    
    def _build_system_prompt(self, session_context):
        """构建系统提示词"""
        if not session_context:
            return (
                "你是直播销售助手“小聚”。请使用第一人称自然口语表达，语气亲切专业；"
                "不必每次说明“我是小聚”，只有在首次问候或被用户询问身份时，才简短自我介绍；"
                "回答简洁、分句清楚，适合直播口播；如不确定，请提示以主播口径为准。"
            )
        
        host_name = session_context.get('host_name', '主播')
        live_theme = session_context.get('live_theme', '直播')
        products = session_context.get('products', [])

        prompt = f"""你是直播销售助手“小聚”，正在协助{host_name}进行“{live_theme}”直播。

请遵循：
1. 使用第一人称，语气亲切、专业、自然口语化；不必每次强调“我是小聚”；
2. 只有在首次问候或被询问身份时，才简短自我介绍；
3. 内容简洁、分句清楚，适合直播口播；
4. 涉及价格或规格以已知信息为准，不确定则提示以主播口径为准；
5. 注意品牌与适用人群的合规表述，避免医疗/夸大承诺；
"""

        if products:
            prompt += "本次直播的商品清单：\n"
            for product in products:
                name = product.get('product_name', '')
                price = product.get('price', '')
                unit = product.get('unit', '元')
                product_type = product.get('product_type', '')

                prompt += f"- {name}：{price}{unit}"
                if product_type:
                    prompt += f"（{product_type}）"
                prompt += "\n"

        return prompt

# 单例
ai_service = AIService()
