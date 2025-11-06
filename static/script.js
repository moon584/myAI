let currentSessionId = null;
let sessionInfo = null;
// 在创建会话时记录一次包含类型的商品快照（用于后续根据类型定制快捷键话术）
let createdProductsSnapshot = [];
let sidebarCollapsed = false;

// API基础URL
const API_BASE = window.location.origin;

// 商品类型属性配置
const productTypeConfig = {
    fruit: {
        name: "水果",
        attributes: [
            { key: "sweetness", label: "甜度", type: "select", options: ["偏酸", "微甜", "适中", "很甜", "特别甜"] },
            { key: "texture", label: "口感", type: "select", options: ["脆爽", "软糯", "多汁", "绵密", "清脆"] },
            { key: "origin", label: "产地", type: "text", placeholder: "例如：山东烟台" },
            { key: "size", label: "大小规格", type: "text", placeholder: "例如：单果200-250g" },
            { key: "season", label: "最佳食用季节", type: "text", placeholder: "例如：9-11月" },
            { key: "storage", label: "储存建议", type: "textarea", placeholder: "冷藏保存，建议3天内食用" }
        ]
    },
    vegetable: {
        name: "蔬菜",
        attributes: [
            { key: "freshness", label: "新鲜度", type: "select", options: ["当日采摘", "隔日送达", "冷链保鲜"] },
            { key: "cooking", label: "推荐烹饪方式", type: "select", options: ["清炒", "炖煮", "凉拌", "蒸制", "煲汤"] },
            { key: "origin", label: "产地", type: "text", placeholder: "例如：本地大棚" },
            { key: "season", label: "时令季节", type: "text", placeholder: "例如：春季" },
            { key: "storage", label: "储存建议", type: "textarea", placeholder: "冷藏保存，建议尽快食用" }
        ]
    },
    meat: {
        name: "禽蛋肉类",
        attributes: [
            { key: "raising", label: "饲养方式", type: "select", options: ["散养", "圈养", "有机养殖", "山林放养"] },
            { key: "part", label: "部位", type: "text", placeholder: "例如：鸡胸肉、猪里脊" },
            { key: "texture", label: "肉质特点", type: "select", options: ["鲜嫩", "紧实", "肥瘦相间", "细腻"] },
            { key: "cooking_time", label: "推荐烹饪时间", type: "text", placeholder: "例如：炖煮1小时" },
            { key: "storage", label: "储存建议", type: "textarea", placeholder: "冷冻保存，解冻后请尽快食用" }
        ]
    },
    grain: {
        name: "五谷杂粮",
        attributes: [
            { key: "variety", label: "品种", type: "text", placeholder: "例如：东北大米、小米" },
            { key: "origin", label: "产地", type: "text", placeholder: "例如：黑龙江" },
            { key: "processing", label: "加工方式", type: "select", options: ["精加工", "粗加工", "保留胚芽", "无添加"] },
            { key: "cooking", label: "食用方法", type: "textarea", placeholder: "煮粥、蒸饭均可" },
            { key: "storage", label: "储存建议", type: "textarea", placeholder: "阴凉干燥处保存" }
        ]
    },
    handicraft: {
        name: "手工艺品",
        attributes: [
            { key: "material", label: "材质", type: "text", placeholder: "例如：竹编、陶瓷、布料" },
            { key: "craft", label: "工艺", type: "text", placeholder: "例如：手工编织、传统烧制" },
            { key: "purpose", label: "用途", type: "select", options: ["装饰", "实用", "收藏", "礼品"] },
            { key: "size", label: "尺寸", type: "text", placeholder: "例如：高20cm，直径15cm" },
            { key: "making_time", label: "制作时长", type: "text", placeholder: "例如：3天" },
            { key: "cultural", label: "文化意义", type: "textarea", placeholder: "传统工艺，承载地方文化" }
        ]
    },
    processed: {
        name: "加工食品",
        attributes: [
            { key: "ingredients", label: "主要原料", type: "textarea", placeholder: "列出主要原料" },
            { key: "shelf_life", label: "保质期", type: "text", placeholder: "例如：6个月" },
            { key: "flavor", label: "风味特点", type: "select", options: ["甜", "咸", "辣", "酸", "鲜", "原味"] },
            { key: "usage", label: "食用方法", type: "textarea", placeholder: "开袋即食或加热食用" },
            { key: "storage", label: "储存建议", type: "textarea", placeholder: "阴凉干燥处保存" }
        ]
    }
};

// 更新商品属性输入区域
function updateProductAttributes(selectElement) {
    const productItem = selectElement.closest('.product-item');
    const attributesContainer = productItem.querySelector('.product-attributes');
    const productType = selectElement.value;
    
    if (productType && productTypeConfig[productType]) {
        const config = productTypeConfig[productType];
        attributesContainer.style.display = 'block';
        attributesContainer.innerHTML = `
            <h4>${config.name} - 商品属性</h4>
            ${config.attributes.map(attr => `
                <div class="attribute-group">
                    <label>${attr.label}</label>
                    ${generateAttributeInput(attr)}
                </div>
            `).join('')}
        `;
    } else {
        attributesContainer.style.display = 'none';
        attributesContainer.innerHTML = '';
    }
}

// 生成属性输入框
function generateAttributeInput(attr) {
    switch(attr.type) {
        case 'select':
            return `
                <select class="attribute-select" data-key="${attr.key}">
                    <option value="">请选择</option>
                    ${attr.options.map(opt => `<option value="${opt}">${opt}</option>`).join('')}
                </select>
            `;
        case 'textarea':
            return `
                <textarea class="attribute-textarea" data-key="${attr.key}" placeholder="${attr.placeholder || ''}"></textarea>
            `;
        default:
            return `
                <input type="text" class="attribute-input" data-key="${attr.key}" placeholder="${attr.placeholder || ''}" />
            `;
    }
}

// 添加商品输入框
function addProduct() {
    const container = document.getElementById('productsContainer');
    const productItem = document.createElement('div');
    productItem.className = 'product-item';
    productItem.innerHTML = `
        <div class="product-basic-info">
            <span class="product-index">#</span>
            <input type="text" class="product-name" placeholder="商品名称" />
            <select class="product-type" onchange="updateProductAttributes(this)">
                <option value="">选择商品类型</option>
                <option value="fruit">水果</option>
                <option value="vegetable">蔬菜</option>
                <option value="meat">禽蛋肉类</option>
                <option value="grain">五谷杂粮</option>
                <option value="handicraft">手工艺品</option>
                <option value="processed">加工食品</option>
            </select>
            <div class="price-unit-group">
                <input type="number" class="product-price price-input" placeholder="价格" step="0.01" min="0" />
                <select class="unit-select">
                    <option value="元/斤">元/斤</option>
                    <option value="元/个">元/个</option>
                    <option value="元/箱">元/箱</option>
                    <option value="元/盒">元/盒</option>
                    <option value="元/袋">元/袋</option>
                    <option value="元/公斤">元/公斤</option>
                    <option value="元/份">元/份</option>
                    <option value="元">元</option>
                </select>
            </div>
            <button class="btn btn-remove" onclick="removeProduct(this)">删除</button>
        </div>
        <div class="product-attributes" style="display: none;"></div>
    `;
    container.appendChild(productItem);
    updateProductIndices();
}

// 删除商品输入框
function removeProduct(button) {
    const container = document.getElementById('productsContainer');
    if (container.children.length > 1) {
        button.closest('.product-item').remove();
    }
    updateProductIndices();
}

// 在创建会话时收集商品信息
async function createSession() {
    const userName = document.getElementById('userName').value.trim();
    const liveTheme = document.getElementById('liveTheme').value.trim();

    if (!userName || !liveTheme) {
        showError('请填写主播名称和直播主题');
        return;
    }

    // 收集商品信息（包含类型和属性）
    const productInputs = document.querySelectorAll('.product-item');
    const products = [];

    productInputs.forEach(rowEl => {
        const name = rowEl.querySelector('.product-name').value.trim();
        const price = rowEl.querySelector('.product-price').value.trim();
        const unit = rowEl.querySelector('.unit-select').value;
        const type = rowEl.querySelector('.product-type').value;

        if (name && price && type) {
            // 收集属性信息
            const attributes = {};
            const attributeInputs = rowEl.querySelectorAll('[data-key]');
            attributeInputs.forEach(input => {
                const key = input.getAttribute('data-key');
                const value = input.value.trim();
                if (value) {
                    attributes[key] = value;
                }
            });

            const product = {
                name: name,
                price: parseFloat(price),
                unit: unit,
                type: type,
                attributes: attributes
            };
            products.push(product);
        }
    });

    if (products.length === 0) {
        showError('请至少添加一个完整的商品信息');
        return;
    }

    // 检查是否有商品没有选择类型
    const invalidProducts = products.filter(p => !p.type);
    if (invalidProducts.length > 0) {
        showError('请为所有商品选择商品类型');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/session`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                host_name: userName,
                live_theme: liveTheme,
                products: products
            })
        });

        const data = await response.json();

        if (response.ok) {
            currentSessionId = data.session_id;
            // 保存本地类型快照，供后续根据类型调整快捷建议
            createdProductsSnapshot = products;

            // 不再保存到本地存储，每次刷新都需要重新创建会话
            // localStorage.setItem('current_session_id', currentSessionId);

            // 清空聊天记录，显示新会话的欢迎消息
            const chatContainer = document.getElementById('chatContainer');
            chatContainer.innerHTML = '';

            // 加载会话信息
            await loadSessionInfo();

            // 启用聊天功能
            document.getElementById('messageInput').disabled = false;
            document.getElementById('sendButton').disabled = false;
            document.getElementById('suggestionButtons').style.display = 'flex';

            // 隐藏错误信息
            document.getElementById('errorMessage').style.display = 'none';

            // 更新状态
            document.getElementById('status').textContent = '✅ 会话创建成功！可以开始生成直播话术了';
            document.getElementById('status').style.background = '#d4edda';

            // 显示会话信息
            document.getElementById('sessionInfo').style.display = 'block';

            // 创建成功后自动折叠左侧商品面板
            setSidebarCollapsed(true);
            // 根据商品类型调整快捷按钮文案
            updateSuggestionButtonsUI();

        } else {
            showError(data.error || '创建会话失败');
        }
    } catch (error) {
        showError('网络错误，请检查服务器连接');
        console.error('创建会话错误:', error);
    }
}
// 加载会话信息时显示完整价格信息
async function loadSessionInfo() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(`${API_BASE}/api/session/${currentSessionId}`);
        const data = await response.json();

        if (response.ok) {
            sessionInfo = data;

            // 显示会话信息
            document.getElementById('sessionDetails').textContent =
                `${data.host_name} - ${data.live_theme}`;

            // 不自动加载对话历史，只显示欢迎消息
            const productsText = data.products.map(p =>
                `${p.product_name}：${p.price}${p.unit || '元'}`
            ).join('、');

            addMessage('assistant', `太好了！${data.host_name}，我已经了解了你的直播信息：
            
直播主题：${data.live_theme}
售卖商品：${productsText}

现在我可以为你生成专业的直播话术了！你可以直接输入需求，或者点击下方的快捷按钮。`);

            // 填充快捷建议的商品选择下拉
            populateSuggestionProducts(sessionInfo.products || []);
            const box = document.getElementById('suggestionProductBox');
            if (box) box.style.display = 'inline-flex';
            // 初始根据第一个商品类型调整按钮
            updateSuggestionButtonsUI();


        } else {
            console.error('加载会话信息失败:', data.error);
        }

    } catch (error) {
        console.error('加载会话信息错误:', error);
    }
}

// 开启新对话
function startNewConversation() {
    if (!currentSessionId) return;
    
    if (!confirm('确定要开启新对话吗？当前对话记录将被清空。')) {
        return;
    }
    
    // 清空聊天容器
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = '';
    
    // 显示欢迎消息（使用当前会话信息）
    if (sessionInfo) {
        const productsText = sessionInfo.products.map(p =>
            `${p.product_name}：${p.price}${p.unit || '元'}`
        ).join('、');

        addMessage('assistant', `开启新对话！${sessionInfo.host_name}，让我们重新开始：
        
直播主题：${sessionInfo.live_theme}
售卖商品：${productsText}

你可以直接输入需求，或者点击下方的快捷按钮获取话术建议。`);
    }
    
    // 聚焦到输入框
    document.getElementById('messageInput').focus();
}

// 发送快捷建议请求
// 更新快捷建议请求
function askSuggestion(type) {
    let message = '';
    const sel = document.getElementById('suggestionProductSelect');
    let index = 1;
    let name = '';
    let ptype = '';
    if (sel && sel.value) {
        index = parseInt(sel.value, 10) || 1;
    }
    if (sessionInfo && Array.isArray(sessionInfo.products)) {
        const item = sessionInfo.products[index - 1];
        if (item) name = item.product_name || '';
    }
    ptype = getProductTypeByIndex(index) || '';
    message = buildSuggestionPrompt(type, ptype, index, name);

    document.getElementById('messageInput').value = message;
    sendMessage();
}

function populateSuggestionProducts(products) {
    const sel = document.getElementById('suggestionProductSelect');
    if (!sel) return;
    sel.innerHTML = '';
    if (!Array.isArray(products) || products.length === 0) return;
    products.forEach((p, idx) => {
        const opt = document.createElement('option');
        opt.value = String(idx + 1);
        opt.textContent = `${idx + 1} - ${p.product_name || ''}`;
        sel.appendChild(opt);
    });
}

// 从 /api/tts/tts-<hash>.wav 提取文件名
function extractTTSFileId(audioUrl) {
    try {
        const u = new URL(audioUrl, window.location.origin);
        const parts = u.pathname.split('/');
        return parts[parts.length - 1] || '';
    } catch (e) {
        return '';
    }
}

// 短轮询等待 TTS 就绪，避免刚开始就触发404
async function waitForTTSReady(audioUrl, maxWaitMs = 1500, pollIntervalMs = 150) {
    const start = Date.now();
    const file = extractTTSFileId(audioUrl);
    if (!file || !file.startsWith('tts-')) return; // 无法识别则直接返回
    while (Date.now() - start < maxWaitMs) {
        try {
            const resp = await fetch(`${API_BASE}/api/tts/status?file=${encodeURIComponent(file)}`, { cache: 'no-store' });
            if (!resp.ok) break; // 端点不可用则直接跳出
            const data = await resp.json();
            if (data && data.ready) return; // 就绪
            // 未就绪则短暂等待
        } catch (e) {
            break; // 网络或其他问题，直接跳出，后续走audio自带重试
        }
        await new Promise(r => setTimeout(r, pollIntervalMs));
    }
}

// 发送消息
async function sendMessage() {
    if (!currentSessionId) {
        showError('请先创建会话');
        return;
    }

    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const status = document.getElementById('status');
    const message = messageInput.value.trim();

    if (!message) return;

    // 添加用户消息到界面
    addMessage('user', message);

    // 清空输入框并禁用
    messageInput.value = '';
    messageInput.disabled = true;
    sendButton.disabled = true;
    status.textContent = '小聚正在思考...';

    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: message
            })
        });

        const data = await response.json();

        if (response.ok) {
            addMessage('assistant', data.response, data.audio_url);
            status.textContent = '✅ 思考完毕';
        } else {
            throw new Error(data.error || '请求失败');
        }

    } catch (error) {
        console.error('发送消息错误:', error);
        addMessage('assistant', `❌ 抱歉，出现了错误：${error.message}`);
        status.textContent = '❌ 请求失败';
    } finally {
        // 重新启用输入框
        messageInput.disabled = false;
        sendButton.disabled = false;
        messageInput.focus();
    }
}

// 添加消息到聊天界面
function addMessage(role, content, audioUrl) {
    const chatContainer = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    // 文本
    const textP = document.createElement('p');
    textP.textContent = content;
    messageDiv.appendChild(textP);

    // 若附带语音
    if (role === 'assistant' && audioUrl) {
        const audioWrap = document.createElement('div');
        audioWrap.className = 'audio-wrap';
        const audio = document.createElement('audio');
        audio.controls = true;
        audio.preload = 'auto';
        // 自动播放（可能受浏览器自动播放策略限制）
        audio.addEventListener('canplay', () => {
            const playPromise = audio.play();
            if (playPromise !== undefined) {
                playPromise.catch(() => {/* 静默失败，用户可手动播放 */});
            }
        });
        // 若TTS文件尚未生成或被系统短暂占用，采用指数退避重试加载（最长约20s）
        let retry = 0;
        audio.addEventListener('error', () => {
            if (retry < 15) { // 最多重试15次
                retry++;
                const delay = Math.min(5000, 400 + Math.pow(1.35, retry) * 200); // 400ms起步，指数增长，封顶5s
                setTimeout(() => {
                    const bust = `__r=${Date.now()}`;
                    const url = new URL(audioUrl, window.location.origin);
                    url.searchParams.set('__r', bust);
                    audio.src = url.pathname + url.search;
                    audio.load();
                }, delay);
            }
        });
        // 先做一次短轮询，等到ready后再首次设置src，避免一上来就是404
        waitForTTSReady(audioUrl, 1500, 150).finally(() => {
            const bust = `__r=${Date.now()}`;
            const url = new URL(audioUrl, window.location.origin);
            url.searchParams.set('__r', bust);
            audio.src = url.pathname + url.search;
            audio.load();
        });
        audioWrap.appendChild(audio);
        messageDiv.appendChild(audioWrap);
    }
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 显示错误信息
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

// 页面加载时初始化
window.addEventListener('DOMContentLoaded', function () {
    // 清除之前保存的会话，每次刷新都需要重新创建
    localStorage.removeItem('current_session_id');
    
    // 清空聊天容器
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = '';
    
    // 显示欢迎提示
    addMessage('assistant', '👋 欢迎使用专业版直播销售助手！请先在左侧配置直播信息，创建会话后即可开始生成专业的直播话术。');

    // 默认添加一个空商品行
    addProduct();
    updateProductIndices();

    // 回车发送消息
    document.getElementById('messageInput').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    
    // 侧边栏折叠按钮
    const toggleBtn = document.getElementById('sidebarToggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => setSidebarCollapsed(!sidebarCollapsed));
    }

    // 浮动快速展开按钮（仅在折叠时显示）
    const fab = document.getElementById('sidebarFab');
    if (fab) {
        fab.addEventListener('click', () => setSidebarCollapsed(false));
    }

    // 键盘快捷键：Alt+L 切换侧边栏；Alt+1..Alt+5 触发快捷建议
    window.addEventListener('keydown', (e) => {
        if (e.altKey && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
            const k = e.key.toLowerCase();
            if (k === 'l') {
                e.preventDefault();
                setSidebarCollapsed(!sidebarCollapsed);
            } else if (['1','2','3','4','5'].includes(k)) {
                e.preventDefault();
                if (!currentSessionId) return; // 未创建会话不触发
                const map = {
                    '1': '产品介绍',
                    '2': '食用方法',
                    '3': 'APP功能',
                    '4': '乡村文化',
                    '5': '促销引导'
                };
                askSuggestion(map[k]);
            }
        }
    });

    // 快捷建议下拉选改变时，动态更新按钮文案
    const sel = document.getElementById('suggestionProductSelect');
    if (sel) {
        sel.addEventListener('change', () => updateSuggestionButtonsUI());
    }
});

function updateProductIndices() {
    const items = document.querySelectorAll('#productsContainer .product-item');
    items.forEach((item, idx) => {
        let badge = item.querySelector('.product-index');
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'product-index';
            const basic = item.querySelector('.product-basic-info');
            if (basic) basic.prepend(badge);
        }
        badge.textContent = (idx + 1).toString();
    });
}

function setSidebarCollapsed(collapse) {
    sidebarCollapsed = collapse;
    const container = document.querySelector('.container');
    const toggleBtn = document.getElementById('sidebarToggle');
    const fab = document.getElementById('sidebarFab');
    if (!container) return;
    if (collapse) {
        container.classList.add('sidebar-collapsed');
        if (toggleBtn) toggleBtn.textContent = '⮜ 展开商品面板';
        if (toggleBtn) toggleBtn.title = '展开商品面板 (Alt+L)';
        if (fab) fab.style.display = 'block';
    } else {
        container.classList.remove('sidebar-collapsed');
        if (toggleBtn) toggleBtn.textContent = '⮞ 隐藏商品面板';
        if (toggleBtn) toggleBtn.title = '隐藏商品面板 (Alt+L)';
        if (fab) fab.style.display = 'none';
    }
}

function getProductTypeByIndex(index) {
    // 优先从服务端返回的数据读取（可能字段名 product_type 或 type）
    if (sessionInfo && Array.isArray(sessionInfo.products)) {
        const p = sessionInfo.products[index - 1];
        if (p) {
            const t = p.product_type || p.type;
            if (t) return String(t);
        }
    }
    // 回退到创建会话时的快照（保持顺序一致）
    if (Array.isArray(createdProductsSnapshot) && createdProductsSnapshot[index - 1]) {
        const t = createdProductsSnapshot[index - 1].type;
        if (t) return String(t);
    }
    return '';
}

// 按商品类型与快捷类型构建更自然的请求话术
function buildSuggestionPrompt(kind, ptype, index, name) {
    const id = `第${index}号商品${name ? `（${name}）` : ''}`;
    const type = (ptype || '').toLowerCase();
    const K = kind;
    // 针对不同类型的定制模板
    const templates = {
        fruit: {
            '产品介绍': `请用清新、自然的语气，介绍${id}的品种、产地风味、口感（甜度/多汁度）、成熟度与保存建议，控制在150字左右。`,
            '食用方法': `请分享${id}的清洗与切法小技巧、判断最佳成熟度的方法，以及1-2个简单搭配（如酸奶/沙拉），语气要亲切不夸张。`,
            '乡村文化': `结合季节与产地乡土特色，讲一个与${id}相关的农事或节气小知识，控制在120字内。`,
            '促销引导': `以不打扰的方式提醒观众：现在${id}新鲜到货，数量有限，感兴趣可以点开详情看看参数与实拍。文案自然、避免强推。`
        },
        vegetable: {
            '产品介绍': `请用家常、可信的口吻介绍${id}的新鲜度、口感与适合的做法（清炒/蒸/凉拌），并附简单保存建议（控水、冷藏）。150字内。`,
            '食用方法': `请给出${id}的家常做法建议（清炒/蒸/凉拌），火候与时间要点，以及保留脆嫩口感的小技巧。`,
            '乡村文化': `结合本地种植习惯或时令，分享一个与${id}相关的小科普，轻松有趣，约120字。`,
            '促销引导': `自然提醒：${id}今天是新鲜到货，喜欢清淡口味的朋友可以看看详情，支持门店自提。` 
        },
        meat: {
            '产品介绍': `用稳重、实在的语气介绍${id}的来源与部位、口感（鲜嫩/紧实），并简述适合烹饪方式与存储保鲜。150字内。`,
            '食用方法': `给出${id}的腌制/焯水要点、熟度判断（七八分熟等）与安全食用提示，简洁不啰嗦。`,
            '乡村文化': `结合本地养殖或传统菜式，聊一个与${id}有关的小故事或习俗，暖心不夸张。`,
            '促销引导': `不强推地提示：${id}支持冷链配送/门店自提，近期有小优惠，想尝鲜的朋友可以点详情对比参数。`
        },
        grain: {
            '产品介绍': `用质朴的语气介绍${id}的产地、品种与口感（清香/绵软），并简单说明存放与防潮建议。150字内。`,
            '食用方法': `给出${id}的浸泡时间与水米比例、口感偏好（偏软/偏硬）的调整建议，直观易操作。`,
            '乡村文化': `讲一个与${id}相关的农耕或节气知识，突出土地与劳作的诚意，120字左右。`,
            '促销引导': `轻声提醒：${id}是今年新粮，喜欢原香口感的朋友可以点开详情看看检验报告与烹饪建议。`
        },
        processed: {
            '产品介绍': `自然介绍${id}的主要原料、风味特点与工艺（无添加/少添加如实写），以及开袋即食或加热方式。150字内。`,
            '食用方法': `分享${id}的吃法搭配（如茶饮/面包/米饭），并提示存放与开封后食用期限。`,
            '乡村文化': `若有地方特色或传统做法，可简述${id}背后的地域风味故事，控制在120字。`,
            '促销引导': `自然引导：${id}今天有小折扣，想尝试的朋友可以先看配料表与营养信息，理性选择。`
        },
        handicraft: {
            '产品介绍': `请用温柔的语气介绍${id}的材质、工艺（手工/非遗等）、尺寸与用途场景，突出质感与温度，150字内。`,
            '食用方法': `请改为“使用与保养建议”：说明${id}的摆放/清洁/防潮防晒/避免重压等小贴士。`,
            '乡村文化': `讲述${id}背后的工艺传承或匠人故事，突出人情味与文化价值，约120字。`,
            '促销引导': `低调提示：${id}为手作作品，数量有限，感兴趣的朋友可查看详情里的尺寸与手工痕迹说明。`
        }
    };
    const t = templates[type] || templates['processed'];
    // 特例：APP功能与通用项
    if (K === 'APP功能') {
        return `介绍一下乡聚APP的直播、自提、购买与售后流程，用通俗语言说明下单到取货的关键步骤。`;
    }
    // 兜底回退到对应类型下的项；若缺失则回退到产品介绍
    return t[K] || t['产品介绍'] || `请介绍${id}的核心卖点与常见使用/食用方式，语气亲切自然。`;
}

// 根据选中的商品类型，动态调整快捷按钮的文案与提示
function updateSuggestionButtonsUI() {
    const sel = document.getElementById('suggestionProductSelect');
    let index = 1;
    if (sel && sel.value) index = parseInt(sel.value, 10) || 1;
    const type = (getProductTypeByIndex(index) || '').toLowerCase();
    const box = document.querySelector('.suggestion-buttons');
    if (!box) return;
    const btns = box.querySelectorAll('.suggestion-btn');
    if (!btns || btns.length < 5) return;
    const btnIntro = btns[0];
    const btnUsage = btns[1];
    const btnApp = btns[2];
    const btnCulture = btns[3];
    const btnPromo = btns[4];

    // 默认
    let introLabel = '📦 产品介绍';
    let usageLabel = '🍳 食用方法';
    let cultureLabel = '🏡 乡村文化';
    // 根据类型替换更贴切的标签
    if (type === 'handicraft') {
        introLabel = '🎨 工艺亮点';
        usageLabel = '🧴 使用保养';
        cultureLabel = '🏺 文化故事';
    } else if (type === 'processed') {
        usageLabel = '🍽️ 吃法搭配';
    } else if (type === 'grain') {
        usageLabel = '🥣 烹煮要点';
    }
    btnIntro.textContent = introLabel;
    btnUsage.textContent = usageLabel;
    btnApp.textContent = '📱 APP功能';
    btnCulture.textContent = cultureLabel;
    btnPromo.textContent = '💬 促销引导';
    // 更新title以反映快捷键
    const titles = ['Alt+1', 'Alt+2', 'Alt+3', 'Alt+4', 'Alt+5'];
    [btnIntro, btnUsage, btnApp, btnCulture, btnPromo].forEach((b, i) => b.title = titles[i]);
}