import mysql.connector
from mysql.connector import Error
from mysql.connector import pooling
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.user = os.getenv('DB_USER', 'root')
        self.password = os.getenv('DB_PASSWORD', '')
        self.database = os.getenv('DB_NAME', 'live_assistant')
        
        # 使用连接池
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="mypool",
                pool_size=5,
                pool_reset_session=True,
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                ssl_disabled=True
            )
            logger.info("✅ 数据库连接池创建成功")
            self.init_tables()
        except Error as e:
            logger.error(f"❌ 数据库连接池创建失败: {e}")
            self.pool = None

        # 文件路径（优先读取，回退到数据库）
        self.blacklist_file = os.path.join(os.path.dirname(__file__), 'data', 'blacklist.json')
        self.whitelist_file = os.path.join(os.path.dirname(__file__), 'data', 'whitelist.json')

    def _load_json_file(self, path):
        try:
            if not os.path.exists(path):
                return {}
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"无法加载 JSON 文件 {path}: {e}")
            return {}

    def get_connection(self):
        """从连接池获取连接"""
        try:
            if self.pool:
                return self.pool.get_connection()
            else:
                # 如果池不存在，创建临时连接
                return mysql.connector.connect(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    ssl_disabled=True
                )
        except Error as e:
            logger.error(f"❌ 获取数据库连接失败: {e}")
            return None

    def init_tables(self):
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return
                
            cursor = conn.cursor()
            
            # 创建会话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id VARCHAR(36) PRIMARY KEY,
                    host_name VARCHAR(255) NOT NULL,
                    live_theme VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            
            # 创建商品表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(36),
                    product_name VARCHAR(255) NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    unit VARCHAR(20) DEFAULT '元',
                    product_type VARCHAR(50),
                    attributes JSON,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # 如果旧表没有新字段，则尝试添加（兼容已有表结构）
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = %s AND table_name = 'products' AND column_name = 'unit'",
                    (self.database,)
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("ALTER TABLE products ADD COLUMN unit VARCHAR(20) DEFAULT '元'")
                
                # 检查并添加 product_type 字段
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = %s AND table_name = 'products' AND column_name = 'product_type'",
                    (self.database,)
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("ALTER TABLE products ADD COLUMN product_type VARCHAR(50)")
                
                # 检查并添加 attributes 字段
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = %s AND table_name = 'products' AND column_name = 'attributes'",
                    (self.database,)
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("ALTER TABLE products ADD COLUMN attributes JSON")
                    
            except Exception as e:
                # 忽略以保持兼容性，但打印调试信息
                logger.warning(f"⚠️ 无法确保 products 表字段完整: {e}")
            
            # 创建对话历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(36),
                    user_message TEXT,
                    ai_response TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)
            
            # 创建弹幕队列表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bullet_screen_queue (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(36),
                    username VARCHAR(255),
                    message TEXT NOT NULL,
                    category VARCHAR(50) DEFAULT 'unknown',
                    priority INT DEFAULT 0,
                    is_processed BOOLEAN DEFAULT FALSE,
                    confidence_score FLOAT DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                    INDEX idx_session_processed (session_id, is_processed),
                    INDEX idx_created (created_at)
                )
            """)
            
            # 黑名单与白名单表：用于弹幕处理流水线
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(36),
                    pattern VARCHAR(255) NOT NULL,
                    type VARCHAR(20) DEFAULT 'message', -- 'message' 或 'username'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                    INDEX idx_session_type (session_id, type)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whitelist (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(36),
                    pattern VARCHAR(255) NOT NULL,
                    answer TEXT NOT NULL,
                    priority INT DEFAULT 0,
                    product_types VARCHAR(255),
                    hit_count INT DEFAULT 0,
                    last_hit_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                    INDEX idx_session_pattern (session_id),
                    INDEX idx_hit_count (hit_count)
                )
            """)
            
            # 为已存在的 whitelist 表添加缺失的字段（如果不存在）
            try:
                # 检查并添加 priority 字段
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = %s AND table_name = 'whitelist' AND column_name = 'priority'",
                    (self.database,)
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("ALTER TABLE whitelist ADD COLUMN priority INT DEFAULT 0 AFTER answer")
                    logger.info("✅ 已添加 whitelist.priority 字段")
                
                # 检查并添加 product_types 字段
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = %s AND table_name = 'whitelist' AND column_name = 'product_types'",
                    (self.database,)
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("ALTER TABLE whitelist ADD COLUMN product_types VARCHAR(255) AFTER priority")
                    logger.info("✅ 已添加 whitelist.product_types 字段")
                
                # 检查并添加 hit_count 字段
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = %s AND table_name = 'whitelist' AND column_name = 'hit_count'",
                    (self.database,)
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("ALTER TABLE whitelist ADD COLUMN hit_count INT DEFAULT 0 AFTER product_types")
                    logger.info("✅ 已添加 whitelist.hit_count 字段")
                
                # 检查并添加 last_hit_at 字段
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = %s AND table_name = 'whitelist' AND column_name = 'last_hit_at'",
                    (self.database,)
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("ALTER TABLE whitelist ADD COLUMN last_hit_at TIMESTAMP NULL AFTER hit_count")
                    logger.info("✅ 已添加 whitelist.last_hit_at 字段")
            except Exception as e:
                logger.warning(f"⚠️ 无法添加 whitelist 字段: {e}")

            # FAQ模板表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS faq_templates (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    product_type VARCHAR(50) NOT NULL,
                    pattern VARCHAR(255) NOT NULL,
                    answer_template VARCHAR(500) NOT NULL,
                    placeholder VARCHAR(100),
                    priority INT DEFAULT 80,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_product_type (product_type)
                )
            """)
            
            # 问答缓存表（DeepSeek回答缓存）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS qa_cache (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(36),
                    question TEXT NOT NULL,
                    question_hash VARCHAR(64) NOT NULL,
                    answer TEXT NOT NULL,
                    hit_count INT DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                    INDEX idx_session_hash (session_id, question_hash),
                    INDEX idx_last_used (last_used_at)
                )
            """)

            conn.commit()            # 初始化FAQ模板数据（如果表为空）
            cursor.execute("SELECT COUNT(*) FROM faq_templates")
            if cursor.fetchone()[0] == 0:
                self._init_faq_templates(cursor)
                conn.commit()
            
            logger.info("✅ 数据库表初始化成功")
            
        except Error as e:
            logger.error(f"❌ 数据库表初始化失败: {e}")
        finally:
            if conn:
                conn.close()
    
    def _init_faq_templates(self, cursor):
        """初始化FAQ模板数据"""
        templates = [
            # 水果类模板
            ('fruit', '甜不甜', '我们的{name}甜度是{sweetness}，口感很好哦~', '甜度（如：9分甜）', 90),
            ('fruit', '甜度', '{name}的甜度是{sweetness}，非常适合喜欢吃甜的朋友！', '甜度（如：9分甜）', 90),
            ('fruit', '口感', '{name}的口感{texture}，吃起来特别满足！', '口感（如：多汁软糯）', 85),
            ('fruit', '产地', '我们的{name}来自{origin}，品质有保证！', '产地（如：云南）', 80),
            ('fruit', '哪里的', '{name}来自{origin}，品质有保证！', '产地（如：云南）', 80),
            ('fruit', '什么时候最好', '{name}在{season}最好吃，现在正是时候！', '季节（如：春季）', 75),
            
            # 蔬菜类模板
            ('vegetable', '新鲜吗', '绝对新鲜！{freshness}，当天采摘！', '新鲜度（如：当天现摘）', 90),
            ('vegetable', '怎么做', '这个{name}适合{cooking}，简单又好吃！', '烹饪方法（如：清炒或做汤）', 85),
            ('vegetable', '怎么吃', '推荐{cooking}，营养美味！', '烹饪方法（如：清炒或做汤）', 85),
            ('vegetable', '哪里的', '{name}来自{origin}，生态种植！', '产地（如：本地农场）', 80),
            ('vegetable', '产地', '来自{origin}，生态种植！', '产地（如：本地农场）', 80),
            
            # 肉类模板
            ('meat', '怎么养的', '我们的{name}是{raising}，肉质鲜美！', '养殖方式（如：山地散养）', 90),
            ('meat', '养殖方式', '{raising}，保证品质！', '养殖方式（如：山地散养）', 90),
            ('meat', '肉质', '{name}的肉质{texture}，口感一流！', '肉质（如：紧实弹牙）', 85),
            ('meat', '口感', '肉质{texture}，口感一流！', '肉质（如：紧实弹牙）', 85),
            ('meat', '怎么煮', '建议{cooking_time}，味道最佳！', '烹饪时间（如：炖煮2小时）', 80),
            
            # 五谷类模板
            ('grain', '什么品种', '这是{variety}，品质优良！', '品种（如：东北大米）', 85),
            ('grain', '怎么吃', '{cooking}，营养健康！', '食用方法（如：煮粥或蒸饭）', 85),
            ('grain', '怎么做', '建议{cooking}，营养健康！', '食用方法（如：煮粥或蒸饭）', 85),
            ('grain', '哪里产的', '来自{origin}，原产地直供！', '产地（如：东北）', 80),
            ('grain', '产地', '{origin}，原产地直供！', '产地（如：东北）', 80),
            
            # 手工艺品模板
            ('handicraft', '什么材料', '使用{material}材质，天然环保！', '材料（如：纯棉）', 85),
            ('handicraft', '怎么做的', '采用{craft}工艺，纯手工制作！', '工艺（如：传统编织）', 85),
            ('handicraft', '做多久', '每件需要{making_time}，匠心之作！', '制作时间（如：3天）', 80),
            
            # 加工食品模板
            ('processed', '什么原料', '原料是{ingredients}，健康放心！', '原料（如：纯天然水果）', 85),
            ('processed', '保质期', '保质期{shelf_life}，请放心购买！', '保质期（如：12个月）', 90),
            ('processed', '什么味道', '{flavor}风味，好吃不腻！', '风味（如：香甜可口）', 85),
        ]
        
        for product_type, pattern, answer_template, placeholder, priority in templates:
            cursor.execute(
                "INSERT INTO faq_templates (product_type, pattern, answer_template, placeholder, priority) VALUES (%s, %s, %s, %s, %s)",
                (product_type, pattern, answer_template, placeholder, priority)
            )
        
        logger.info(f"✅ 已初始化 {len(templates)} 条FAQ模板")

    def create_session(self, session_id, host_name, live_theme, products):
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # 插入会话
            cursor.execute(
                "INSERT INTO sessions (id, host_name, live_theme) VALUES (%s, %s, %s)",
                (session_id, host_name, live_theme)
            )
            
            # 插入商品
            for product in products:
                # 兼容字段名：type/product_type
                ptype = product.get('product_type') or product.get('type')
                cursor.execute(
                    "INSERT INTO products (session_id, product_name, price, unit, product_type, attributes) VALUES (%s, %s, %s, %s, %s, %s)",
                    (session_id, product.get('name', ''), float(product.get('price', 0)), product.get('unit', '元'), 
                     ptype, json.dumps(product.get('attributes', {}), ensure_ascii=False))
                )
            
            conn.commit()
            logger.info(f"会话创建成功 - ID: {session_id}, 商品数量: {len(products)}")
            
            return True
        except Error as e:
            logger.error(f"❌ 创建会话失败: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def get_faq_templates(self, product_type):
        """获取指定商品类型的FAQ模板
        
        Args:
            product_type: 商品类型 (fruit/vegetable/meat/grain/handicraft/processed)
        
        Returns:
            list: FAQ模板列表，每个模板包含 pattern, answer_template, placeholder, priority
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return []
            
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT pattern, answer_template, placeholder, priority FROM faq_templates WHERE product_type = %s AND is_active = TRUE ORDER BY priority DESC",
                (product_type,)
            )
            templates = cursor.fetchall()
            
            logger.info(f"获取 {product_type} 类型的FAQ模板，共 {len(templates)} 条")
            return templates
        except Error as e:
            logger.error(f"❌ 获取FAQ模板失败: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def apply_faq_template(self, session_id, product_type, faq_values):
        """应用FAQ模板 - 主播填写值后调用
        
        Args:
            session_id: 会话ID
            product_type: 商品类型
            faq_values: 主播填写的值，dict格式
                例如: {'name': '草莓', 'sweetness': '9分甜', 'origin': '云南', 'texture': '多汁软糯', 'season': '春季'}
        
        Returns:
            int: 成功应用的FAQ数量
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return 0
            
            cursor = conn.cursor(dictionary=True)
            
            # 获取模板
            cursor.execute(
                "SELECT pattern, answer_template, priority FROM faq_templates WHERE product_type = %s AND is_active = TRUE",
                (product_type,)
            )
            templates = cursor.fetchall()
            
            applied_count = 0
            skipped_count = 0
            
            for template in templates:
                try:
                    # 使用主播提供的值格式化答案
                    answer = template['answer_template'].format(**faq_values)
                    
                    # 检查是否已存在相同pattern
                    cursor.execute(
                        "SELECT COUNT(*) as cnt FROM whitelist WHERE session_id = %s AND pattern = %s",
                        (session_id, template['pattern'])
                    )
                    if cursor.fetchone()['cnt'] > 0:
                        continue  # 已存在，跳过
                    
                    # 插入FAQ
                    cursor.execute(
                        "INSERT INTO whitelist (session_id, pattern, answer, priority, product_types) VALUES (%s, %s, %s, %s, %s)",
                        (session_id, template['pattern'], answer, template['priority'], product_type)
                    )
                    applied_count += 1
                    
                except KeyError as e:
                    # 模板需要的值未提供，跳过这个FAQ
                    skipped_count += 1
                    logger.debug(f"FAQ模板缺少参数 {e}，跳过: {template['pattern']}")
                    continue
            
            conn.commit()
            logger.info(f"✅ 为会话 {session_id} 应用了 {applied_count} 条FAQ，跳过 {skipped_count} 条（缺少参数）")
            
            return applied_count
            
        except Error as e:
            logger.error(f"❌ 应用FAQ模板失败: {e}")
            return 0
        finally:
            if conn:
                conn.close()

    def _get_session_product_types(self, session_id):
        """获取会话的所有商品类型集合
        
        Returns:
            set: 商品类型集合，如 {'fruit', 'vegetable'}
        """
        session = self.get_session(session_id)
        if not session or 'products' not in session:
            return set()
        
        product_types = set()
        for product in session['products']:
            product_type = product.get('product_type')
            if product_type:
                product_types.add(product_type)
        
        return product_types
    
    def _check_product_type_match(self, item_types, session_product_types):
        """检查白名单条目的商品类型是否与会话商品类型匹配
        
        Args:
            item_types: 白名单条目的 product_types 字段（字符串，逗号分隔或单个类型，或空）
            session_product_types: 会话的商品类型集合
        
        Returns:
            bool: True 如果匹配或为通用FAQ，False 如果不匹配
        """
        # 如果 item_types 为空或 None，表示这是通用 FAQ，适用于所有类型
        if not item_types:
            return True
        
        # 如果没有会话商品类型，也允许通过（边缘情况）
        if not session_product_types:
            return True
        
        # 检查是否有任意一个类型匹配
        # item_types 可能是 "fruit" 或 "fruit,vegetable" 格式
        item_type_list = [t.strip() for t in item_types.split(',')]
        
        # 只要有一个类型匹配就返回 True
        for item_type in item_type_list:
            if item_type in session_product_types:
                return True
        
        return False

    def get_session(self, session_id):
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return None
                
            cursor = conn.cursor(dictionary=True)
            
            # 获取会话信息
            cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
            session = cursor.fetchone()
            
            if session:
                # 获取商品信息
                cursor.execute("SELECT * FROM products WHERE session_id = %s", (session_id,))
                products = cursor.fetchall()
                session['products'] = products
                
                # 获取对话历史
                cursor.execute("SELECT * FROM conversations WHERE session_id = %s ORDER BY created_at", (session_id,))
                conversations = cursor.fetchall()
                session['conversations'] = conversations
            
            return session
        except Error as e:
            logger.error(f"❌ 获取会话失败: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def save_conversation(self, session_id, user_message, ai_response):
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (session_id, user_message, ai_response) VALUES (%s, %s, %s)",
                (session_id, user_message, ai_response)
            )
            conn.commit()
            logger.debug(f"对话已保存 - 会话ID: {session_id}")
            return True
        except Error as e:
            logger.error(f"❌ 保存对话失败: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def add_bullet_screen(self, session_id, username, message, category='unknown', priority=0):
        """添加弹幕到队列"""
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return None
                
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO bullet_screen_queue (session_id, username, message, category, priority) VALUES (%s, %s, %s, %s, %s)",
                (session_id, username, message, category, priority)
            )
            conn.commit()
            return cursor.lastrowid
        except Error as e:
            logger.error(f"❌ 添加弹幕失败: {e}")
            return None
        finally:
            if conn:
                conn.close()

    # ============ 黑白名单相关方法 ============
    def is_blacklisted(self, session_id, username, message):
        """检查弹幕是否命中黑名单（基于用户名或消息内容的简单子串匹配）"""
        # 先从文件读取（若配置了文件），文件格式: { session_id: [ {"pattern":"...","type":"message"}, ... ] }
        try:
            data = self._load_json_file(self.blacklist_file)
            session_list = data.get(session_id) or []
            for item in session_list:
                p = item.get('pattern')
                t = item.get('type', 'message')
                if t == 'username' and p == username:
                    return True
                if t == 'message' and p and p.lower() in (message or '').lower():
                    return True
        except Exception:
            # 如果文件读取异常，继续回退到数据库查询
            logger.debug("黑名单文件读取异常，回退到数据库查询")

        # 回退到数据库查询
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return False
            cursor = conn.cursor()
            # 检查按用户名的黑名单
            cursor.execute("SELECT COUNT(*) FROM blacklist WHERE session_id = %s AND type = 'username' AND pattern = %s", (session_id, username))
            if cursor.fetchone()[0] > 0:
                return True

            # 检查按消息内容的模式（逐行比对）
            cursor.execute("SELECT pattern FROM blacklist WHERE session_id = %s AND type = 'message'", (session_id,))
            rows = cursor.fetchall()
            if rows:
                for (pattern,) in rows:
                    if pattern and pattern.lower() in (message or '').lower():
                        return True

            return False
        except Error as e:
            logger.error(f"❌ 检查黑名单失败: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_whitelist_answer(self, session_id, message):
        """尝试从白名单匹配一个答案（按优先级和最长匹配），只返回与会话商品类型匹配的答案"""
        
        # 首先获取会话的商品类型列表
        session_product_types = self._get_session_product_types(session_id)
        
        # 先从文件读取（若存在）文件格式: { session_id: [ {"pattern":"...","answer":"...","priority":100,"product_types":"fruit"}, ... ] }
        try:
            data = self._load_json_file(self.whitelist_file)
            session_list = data.get(session_id) or []
            best = None
            best_score = (-1, -1)  # (priority, pattern_length)
            for item in session_list:
                pattern = item.get('pattern')
                answer = item.get('answer')
                priority = item.get('priority', 0)
                item_types = item.get('product_types', '')
                
                if not pattern:
                    continue
                
                # 检查商品类型匹配
                if not self._check_product_type_match(item_types, session_product_types):
                    continue
                
                if pattern.lower() in (message or '').lower():
                    score = (int(priority), len(pattern))
                    if score > best_score:
                        best = answer
                        best_score = score

            if best:
                return best
        except Exception:
            logger.debug("白名单文件读取异常，回退到数据库查询")

        # 回退到数据库查询
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return None
            cursor = conn.cursor(dictionary=True)
            # 取出所有 pattern/answer/priority/product_types/id
            cursor.execute("SELECT id, pattern, answer, priority, product_types FROM whitelist WHERE session_id = %s", (session_id,))
            rows = cursor.fetchall()
            if not rows:
                return None

            # 根据优先级和匹配长度选择最佳答案：优先级越大越先匹配；若优先级相同则以最长 pattern 为准
            best = None
            best_score = (-1, -1)  # (priority, pattern_length)
            best_id = None
            
            for row in rows:
                pattern = row['pattern']
                answer = row['answer']
                priority = row['priority']
                item_types = row['product_types']
                faq_id = row['id']
                
                if not pattern:
                    continue
                
                # 检查商品类型匹配
                if not self._check_product_type_match(item_types, session_product_types):
                    continue
                
                if pattern.lower() in (message or '').lower():
                    score = (int(priority or 0), len(pattern))
                    if score > best_score:
                        best = answer
                        best_score = score
                        best_id = faq_id
            
            # 如果找到匹配，更新命中统计
            if best and best_id:
                try:
                    cursor.execute(
                        "UPDATE whitelist SET hit_count = hit_count + 1, last_hit_at = NOW() WHERE id = %s",
                        (best_id,)
                    )
                    conn.commit()
                    logger.debug(f"✅ FAQ命中统计已更新 - ID: {best_id}")
                except Exception as e:
                    logger.warning(f"更新FAQ命中统计失败: {e}")

            return best
        except Error as e:
            logger.error(f"❌ 获取白名单答案失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def get_pending_bullet_screens(self, session_id, limit=10):
        """获取待处理弹幕"""
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return []
                
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM bullet_screen_queue WHERE session_id = %s AND is_processed = FALSE ORDER BY priority DESC, created_at ASC LIMIT %s",
                (session_id, limit)
            )
            return cursor.fetchall()
        except Error as e:
            logger.error(f"❌ 获取待处理弹幕失败: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def mark_bullet_screens_processed(self, bullet_screen_ids):
        """标记弹幕已处理"""
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            placeholders = ','.join(['%s'] * len(bullet_screen_ids))
            cursor.execute(
                f"UPDATE bullet_screen_queue SET is_processed = TRUE, processed_at = NOW() WHERE id IN ({placeholders})",
                tuple(bullet_screen_ids)
            )
            conn.commit()
            return True
        except Error as e:
            logger.error(f"❌ 标记弹幕已处理失败: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def get_cached_answer(self, session_id, question):
        """从缓存中获取答案（优化版：问题归一化）
        
        Args:
            session_id: 会话ID
            question: 问题文本
        
        Returns:
            str: 缓存的答案，如果不存在返回None
        """
        import hashlib
        import re
        
        # 问题归一化：去除标点、语气词、统一疑问词
        def normalize_question(q):
            q = q.strip()
            # 去除常见标点
            q = re.sub(r'[？?！!。.，,、；;：:""\'\'""（）()【】\[\]]', '', q)
            # 去除语气词
            q = re.sub(r'(吗|呢|啊|哦|嘛|呀|哇|哈)+', '', q)
            # 统一疑问词
            q = q.replace('么', '吗')
            # 去除多余空格
            q = ' '.join(q.split())
            return q.lower()
        
        # 计算问题的hash（归一化后）
        question_normalized = normalize_question(question)
        question_hash = hashlib.sha256(question_normalized.encode('utf-8')).hexdigest()
        
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return None
            
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT answer, id FROM qa_cache WHERE session_id = %s AND question_hash = %s ORDER BY last_used_at DESC LIMIT 1",
                (session_id, question_hash)
            )
            result = cursor.fetchone()
            
            if result:
                # 更新命中次数和最后使用时间
                cursor.execute(
                    "UPDATE qa_cache SET hit_count = hit_count + 1, last_used_at = NOW() WHERE id = %s",
                    (result['id'],)
                )
                conn.commit()
                
                logger.info(f"✅ 问答缓存命中 - 会话: {session_id}, 问题: {question_normalized[:20]}...")
                return result['answer']
            
            return None
            
        except Error as e:
            logger.error(f"❌ 获取缓存答案失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def cache_qa(self, session_id, question, answer):
        """缓存问答对（优化版：使用归一化的问题）
        
        Args:
            session_id: 会话ID
            question: 问题文本
            answer: 答案文本
        
        Returns:
            bool: 是否成功
        """
        import hashlib
        import re
        
        # 问题归一化（与get_cached_answer保持一致）
        def normalize_question(q):
            q = q.strip()
            q = re.sub(r'[？?！!。.，,、；;：:""\'\'""（）()【】\[\]]', '', q)
            q = re.sub(r'(吗|呢|啊|哦|嘛|呀|哇|哈)+', '', q)
            q = q.replace('么', '吗')
            q = ' '.join(q.split())
            return q.lower()
        
        # 计算问题的hash
        question_normalized = normalize_question(question)
        question_hash = hashlib.sha256(question_normalized.encode('utf-8')).hexdigest()
        
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            
            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM qa_cache WHERE session_id = %s AND question_hash = %s",
                (session_id, question_hash)
            )
            existing = cursor.fetchone()
            
            if existing:
                # 更新现有记录
                cursor.execute(
                    "UPDATE qa_cache SET answer = %s, hit_count = hit_count + 1, last_used_at = NOW() WHERE id = %s",
                    (answer, existing[0])
                )
            else:
                # 插入新记录
                cursor.execute(
                    "INSERT INTO qa_cache (session_id, question, question_hash, answer) VALUES (%s, %s, %s, %s)",
                    (session_id, question, question_hash, answer)
                )
            
            conn.commit()
            logger.info(f"✅ 问答缓存已保存 - 会话: {session_id}, 问题: {question_normalized[:20]}...")
            
            # 自动清理缓存（保留最近1000条）
            self._clean_qa_cache()
            
            return True
            
        except Error as e:
            logger.error(f"❌ 缓存问答失败: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def _clean_qa_cache(self, max_cache_size=1000):
        """清理问答缓存，只保留最近使用的N条
        
        Args:
            max_cache_size: 最大缓存数量，默认1000
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return
            
            cursor = conn.cursor()
            
            # 检查缓存数量
            cursor.execute("SELECT COUNT(*) FROM qa_cache")
            count = cursor.fetchone()[0]
            
            if count > max_cache_size:
                # 删除旧的缓存
                cursor.execute("""
                    DELETE FROM qa_cache 
                    WHERE id NOT IN (
                        SELECT id FROM (
                            SELECT id FROM qa_cache 
                            ORDER BY last_used_at DESC 
                            LIMIT %s
                        ) AS tmp
                    )
                """, (max_cache_size,))
                deleted = cursor.rowcount
                conn.commit()
                
                if deleted > 0:
                    logger.info(f"✅ 已清理 {deleted} 条旧的问答缓存，保留最近 {max_cache_size} 条")
                    
        except Error as e:
            logger.warning(f"清理问答缓存失败: {e}")
        finally:
            if conn:
                conn.close()
    
    def check_sensitive_words(self, message):
        """检查消息是否包含敏感词（政治、色情等）
        
        Args:
            message: 消息文本
        
        Returns:
            tuple: (bool, list) - (是否包含敏感词, 命中的敏感词列表)
        """
        if not message:
            return False, []
        
        try:
            # 读取敏感词黑名单
            data = self._load_json_file(self.blacklist_file)
            global_list = data.get('_global', [])
            
            if not global_list:
                return False, []
            
            msg_lower = message.lower().strip()
            matched_words = []
            
            for word in global_list:
                if not word:
                    continue
                word_lower = word.lower().strip()
                if word_lower in msg_lower:
                    matched_words.append(word)
            
            if matched_words:
                logger.warning(f"⚠️ 敏感词命中: {matched_words} - 消息: {message}")
                return True, matched_words
            
            return False, []
            
        except Exception as e:
            logger.error(f"❌ 检查敏感词失败: {e}")
            return False, []
    
    def get_faq_statistics(self, session_id=None):
        """获取FAQ统计信息
        
        Args:
            session_id: 会话ID，如果为None则统计所有FAQ
        
        Returns:
            dict: 统计信息
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return None
            
            cursor = conn.cursor(dictionary=True)
            
            if session_id:
                # 单个会话的统计
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_faqs,
                        SUM(hit_count) as total_hits,
                        AVG(hit_count) as avg_hits,
                        MAX(hit_count) as max_hits,
                        COUNT(CASE WHEN hit_count > 0 THEN 1 END) as used_faqs,
                        COUNT(CASE WHEN hit_count = 0 THEN 1 END) as unused_faqs
                    FROM whitelist 
                    WHERE session_id = %s
                """, (session_id,))
                stats = cursor.fetchone()
                
                # 获取热门FAQ (Top 10)
                cursor.execute("""
                    SELECT pattern, answer, hit_count, last_hit_at, product_types
                    FROM whitelist 
                    WHERE session_id = %s AND hit_count > 0
                    ORDER BY hit_count DESC 
                    LIMIT 10
                """, (session_id,))
                hot_faqs = cursor.fetchall()
                
                # 获取未使用的FAQ
                cursor.execute("""
                    SELECT pattern, answer, product_types
                    FROM whitelist 
                    WHERE session_id = %s AND hit_count = 0
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (session_id,))
                unused_faqs = cursor.fetchall()
                
                return {
                    'session_id': session_id,
                    'statistics': stats,
                    'hot_faqs': hot_faqs,
                    'unused_faqs': unused_faqs
                }
            else:
                # 全局统计
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_faqs,
                        SUM(hit_count) as total_hits,
                        AVG(hit_count) as avg_hits,
                        COUNT(DISTINCT session_id) as total_sessions
                    FROM whitelist
                """)
                stats = cursor.fetchone()
                
                # 全局热门FAQ
                cursor.execute("""
                    SELECT w.pattern, w.answer, w.hit_count, w.product_types, s.host_name, s.live_theme
                    FROM whitelist w
                    LEFT JOIN sessions s ON w.session_id = s.id
                    WHERE w.hit_count > 0
                    ORDER BY w.hit_count DESC 
                    LIMIT 20
                """)
                hot_faqs = cursor.fetchall()
                
                return {
                    'statistics': stats,
                    'hot_faqs': hot_faqs
                }
                
        except Error as e:
            logger.error(f"❌ 获取FAQ统计失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def get_faq_recommendations(self, session_id, min_hit_count=10):
        """获取FAQ推荐（基于高频但未被FAQ覆盖的问题）
        
        Args:
            session_id: 会话ID
            min_hit_count: 最小命中次数，默认10
        
        Returns:
            list: 推荐添加为FAQ的问题列表
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                return []
            
            cursor = conn.cursor(dictionary=True)
            
            # 找出高频但未被FAQ覆盖的问题
            cursor.execute("""
                SELECT 
                    q.question,
                    q.answer,
                    q.hit_count,
                    q.last_used_at
                FROM qa_cache q
                WHERE q.session_id = %s 
                  AND q.hit_count >= %s
                  AND NOT EXISTS (
                      SELECT 1 FROM whitelist w 
                      WHERE w.session_id = q.session_id 
                      AND LOWER(q.question) LIKE CONCAT('%%', LOWER(w.pattern), '%%')
                  )
                ORDER BY q.hit_count DESC
                LIMIT 20
            """, (session_id, min_hit_count))
            
            recommendations = cursor.fetchall()
            
            logger.info(f"✅ 找到 {len(recommendations)} 条FAQ推荐 - 会话: {session_id}")
            
            return recommendations
            
        except Error as e:
            logger.error(f"❌ 获取FAQ推荐失败: {e}")
            return []
        finally:
            if conn:
                conn.close()


# 单例模式
db = Database()