// ================= AI 助手页：对接后端 /api/chat 大模型 =================
// 权限：游客仅可浏览页面，发送消息/上传图片需登录（普通用户/管理员）。
// 图片对话：选图 -> POST /api/upload 保存到 frontend/images/，返回本地路径
//           （如 images/xxx.jpg）-> 发送时把该路径作为 image_url 传给 /api/chat，
//           后端转 base64 交给多模态大模型识别。
// 降级：大模型未配置（503）时，自动改用本地知识库回答并注明来源。
window.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatImageFile = document.getElementById('chatImageFile');
    const chatImageBtn = document.getElementById('chatImageBtn');
    const chatImagePreview = document.getElementById('chatImagePreview');
    const chatImagePreviewImg = document.getElementById('chatImagePreviewImg');
    const chatImageRemove = document.getElementById('chatImageRemove');
    const chatUploadStatus = document.getElementById('chatUploadStatus');
    const chatLoginBanner = document.getElementById('chatLoginBanner');
    const bambooLoaderTemplate = document.getElementById('bambooLoaderTemplate');

    // ---------- 本地知识库（仅在大模型不可用时兜底） ----------
    const knowledgeBase = [
        { keywords: ['语言', '方言', '哈尼文'], answer: '哈尼语属汉藏语系藏缅语族彝语支，分哈雅、豪白、碧卡三大方言。1957 年创制的哈尼文以哈雅方言绿春县大寨话为标准音。' },
        { keywords: ['梯田', '世界遗产', '农耕'], answer: '红河哈尼梯田 2013 年被列入世界文化遗产。"森林—村寨—梯田—水系"四素同构，是哈尼人千年农耕智慧的结晶。' },
        { keywords: ['十月年', '节日', '过年'], answer: '十月年是哈尼族最盛大的节日，农历十月第一个属龙日开始，人们祭祖、宴亲、歌舞，庆祝一年丰收。' },
        { keywords: ['长街宴', '昂玛突', '美食'], answer: '昂玛突节祭祀寨神、林神之后，全村沿街摆桌连成宴席，绵延数百米，称为长街宴，象征族群团结与共享丰收。' },
        { keywords: ['蘑菇房', '民居', '建筑'], answer: '蘑菇房是哈尼族传统民居，夯土为墙、茅草为顶，形似蘑菇，冬暖夏凉，与森林、梯田共同构成哈尼村落景观。' },
        { keywords: ['服饰', '纺织', '刺绣', '银饰'], answer: '哈尼族服饰以藏青、黑色土布为底，缀以彩色花边、银泡与银饰，僾尼支系女子的银泡头巾尤为艳丽。' },
        { keywords: ['哈尼哈吧', '古歌', '音乐'], answer: '哈尼哈吧是哈尼族古老的民间说唱艺术，内容涵盖创世、迁徙与农耕，被列入国家级非物质文化遗产。' },
        { keywords: ['乐作舞', '舞蹈', '多声部'], answer: '乐作舞是哈尼族围圈而舞的群体舞蹈；红河一带的哈尼族多声部民歌以八声部合唱流传，均被列入国家级非物质文化遗产。' },
        { keywords: ['你好', '您好'], answer: '你好！很高兴与你交流，请问你想了解哈尼族的哪个方面呢？' },
        { keywords: ['谢谢', '感谢'], answer: '不客气！传承少数民族文化是我们共同的责任。' }
    ];

    function localAnswer(text) {
        for (const item of knowledgeBase) {
            if (item.keywords.some(keyword => text.includes(keyword))) {
                return item.answer;
            }
        }
        return '抱歉，我目前只了解一些基础的哈尼族非遗知识。你可以问我关于"语言方言"、"哈尼梯田"、"十月年"、"长街宴"或"蘑菇房"的问题哦！';
    }

    // ---------- 消息渲染 ----------

    function scrollBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function addMessage(text, className) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message ' + className;
        msgDiv.innerText = text;
        chatMessages.appendChild(msgDiv);
        scrollBottom();
        return msgDiv;
    }

    // 用户消息（可附带本地图片缩略图，imageUrl 为页面相对路径 ./images/xxx.jpg）
    function addUserMessage(text, imageUrl) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message user-message';
        if (text) msgDiv.innerText = text;
        if (imageUrl) {
            const img = document.createElement('img');
            img.src = imageUrl;
            img.alt = '随消息发送的图片';
            img.onerror = function() { this.style.display = 'none'; };
            msgDiv.appendChild(img);
        }
        chatMessages.appendChild(msgDiv);
        scrollBottom();
    }

    // 竹筒倒水加载气泡（等待 AI 回复时显示，回复后移除）
    function addLoadingBubble() {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message ai-message chat-loading-bubble';
        if (bambooLoaderTemplate && bambooLoaderTemplate.content) {
            msgDiv.appendChild(bambooLoaderTemplate.content.cloneNode(true));
        } else {
            msgDiv.innerText = '正在思考...';
        }
        chatMessages.appendChild(msgDiv);
        scrollBottom();
        return msgDiv;
    }

    // ---------- 待发送图片（上传后暂存本地路径） ----------

    let pendingImageUrl = null;   // 后端返回的本地路径，如 images/xxx.jpg
    let uploading = false;

    function clearPendingImage() {
        pendingImageUrl = null;
        chatImagePreview.style.display = 'none';
        chatImagePreviewImg.removeAttribute('src');
        chatUploadStatus.textContent = '';
    }

    function setUploadStatus(text, isError) {
        chatUploadStatus.textContent = text || '';
        chatUploadStatus.classList.toggle('error', !!isError);
    }

    // 选择图片 -> 上传到 /api/upload -> 拿到本地路径（images/xxx.jpg）
    chatImageBtn.addEventListener('click', () => {
        if (!Auth.isLoggedIn()) {
            Auth.requireLogin('上传图片让 AI 识别');
            return;
        }
        chatImageFile.click();
    });

    chatImageFile.addEventListener('change', async () => {
        const file = chatImageFile.files && chatImageFile.files[0];
        chatImageFile.value = '';   // 允许重复选择同一文件
        if (!file) return;

        // 客户端预校验（与后端 /api/upload 规则一致）
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'];
        if (!allowedTypes.includes(file.type)) {
            setUploadStatus('不支持的图片格式，请选择 jpg / png / gif / webp / bmp', true);
            return;
        }
        if (file.size > 8 * 1024 * 1024) {
            setUploadStatus('图片过大：上限 8MB', true);
            return;
        }

        uploading = true;
        chatImageBtn.disabled = true;
        setUploadStatus('图片上传中…');

        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            const data = await response.json().catch(() => ({}));

            if (response.ok && data.url) {
                // 后端返回相对路径（images/xxx.jpg），前端展示用 ./ 前缀
                pendingImageUrl = data.url;
                chatImagePreviewImg.src = './' + data.url;
                chatImagePreview.style.display = 'inline-block';
                setUploadStatus('图片已就绪，输入问题（可留空）后点「发送」让 AI 识别');
            } else if (response.status === 401 || response.status === 403) {
                clearPendingImage();
                setUploadStatus('登录状态已失效，请重新登录后再上传图片', true);
            } else {
                clearPendingImage();
                setUploadStatus('上传失败：' + (data.error || ('HTTP ' + response.status)), true);
            }
        } catch (error) {
            clearPendingImage();
            setUploadStatus('网络错误：无法连接服务器，请确认后端已启动（python app.py）', true);
        } finally {
            uploading = false;
            chatImageBtn.disabled = false;
        }
    });

    chatImageRemove.addEventListener('click', clearPendingImage);

    // ---------- 发送消息 ----------

    let sending = false;

    async function sendMessage() {
        const text = userInput.value.trim();
        const imageUrl = pendingImageUrl;   // 本地路径，如 images/xxx.jpg
        if (!text && !imageUrl) return;
        if (sending || uploading) return;

        // 游客仅浏览：发送前引导登录
        if (!Auth.isLoggedIn()) {
            Auth.requireLogin('与 AI 专家对话');
            return;
        }

        sending = true;
        sendBtn.disabled = true;
        sendBtn.textContent = '发送中';

        // 只传图片未输入文字时，补一句识别引导语，让大模型进行识别
        const message = text || '请识别这张图片，介绍它与哈尼族文化的关联。';
        addUserMessage(text, imageUrl ? './' + imageUrl : null);
        userInput.value = '';
        clearPendingImage();
        const loading = addLoadingBubble();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ message: message, image_url: imageUrl || '' })
            });
            const data = await response.json().catch(() => ({}));

            if (response.ok) {
                loading.innerText = data.reply || '（未收到回复内容）';
                scrollBottom();
                return;
            }

            // 错误分级处理
            if (response.status === 503) {
                // 大模型未配置：降级到本地知识库
                const answer = localAnswer(message);
                loading.innerText = answer +
                    '\n\n（当前为本地知识库回答：AI 大模型服务未配置，请在 backend/.env 中配置 LLM_API_KEY）';
            } else if (response.status === 400) {
                loading.innerText = '请求有问题：' + (data.error || '请检查图片路径是否正确');
            } else if (response.status === 502) {
                loading.innerText = 'AI 服务暂时无法访问，请稍后重试。' +
                    (data.error ? '\n（' + data.error + '）' : '');
            } else if (response.status === 401 || response.status === 403) {
                loading.innerText = '登录状态已失效，请重新登录后再试。';
            } else {
                loading.innerText = '发送失败：' + (data.error || ('HTTP ' + response.status));
            }
        } catch (error) {
            loading.innerText = '网络错误：无法连接服务器，请确认后端已启动（python app.py）';
        } finally {
            scrollBottom();
            sending = false;
            sendBtn.disabled = false;
            sendBtn.textContent = '发送';
        }
    }

    // ---------- 登录态联动：未登录时显示提示横幅 ----------

    function refreshLoginBanner() {
        chatLoginBanner.style.display = Auth.isLoggedIn() ? 'none' : 'block';
    }
    document.addEventListener('auth:changed', refreshLoginBanner);

    // ---------- 事件绑定 ----------

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') sendMessage();
    });

    // ---------- 启动 ----------

    refreshLoginBanner();
});
