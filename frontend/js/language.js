// ================= 语言页：哈尼语词汇（数据来自后端 /api/vocabulary） =================
// - 分类筛选（分类由数据动态生成）
// - 关键词搜索（匹配释义或哈尼文）
// - 喇叭发音：有 audio_url 播放音频文件，否则用浏览器语音合成朗读释义
const vocabGrid = document.getElementById('vocabGrid');
const langFilter = document.getElementById('langFilter');
const vocabSearch = document.getElementById('vocabSearch');

let vocabData = [];
let activeCategory = '全部';

// ---------- 数据加载 ----------

function loadVocab() {
    fetch('/api/vocabulary')
        .then(response => {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(data => {
            vocabData = data || [];
            buildCategoryFilter();
            renderVocab();
        })
        .catch(error => {
            console.error('连接 Flask 后端失败:', error);
            vocabGrid.innerHTML =
                '<p class="empty-tip">暂无词汇数据 —— 请先在 backend 目录启动服务（python app.py）</p>';
        });
}

// ---------- 分类筛选 ----------

function buildCategoryFilter() {
    const categories = ['全部'];
    vocabData.forEach(item => {
        const cat = item.category || '未分类';
        if (!categories.includes(cat)) categories.push(cat);
    });

    langFilter.innerHTML = '';
    categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.textContent = cat + (cat === '全部' ? '（' + vocabData.length + '）' : '');
        if (cat === activeCategory) btn.classList.add('active');
        btn.addEventListener('click', () => {
            activeCategory = cat;
            langFilter.querySelectorAll('button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderVocab();
        });
        langFilter.appendChild(btn);
    });
}

// ---------- 渲染词汇卡片 ----------

function renderVocab() {
    const searchText = vocabSearch.value.trim().toLowerCase();

    const filtered = vocabData.filter(item => {
        const cat = item.category || '未分类';
        if (activeCategory !== '全部' && cat !== activeCategory) return false;
        if (!searchText) return true;
        const haystack = (item.meaning + ' ' + item.word).toLowerCase();
        return haystack.includes(searchText);
    });

    vocabGrid.innerHTML = '';
    if (!filtered.length) {
        vocabGrid.innerHTML = '<p class="empty-tip">没有匹配的词汇，换个关键词试试</p>';
        return;
    }

    filtered.forEach(item => {
        const card = document.createElement('div');
        card.className = 'vocab-card';

        const cat = document.createElement('span');
        cat.className = 'v-cat';
        cat.textContent = item.category || '未分类';

        const wordLabel = document.createElement('span');
        wordLabel.className = 'v-label';
        wordLabel.textContent = '哈尼文';

        const word = document.createElement('p');
        word.className = 'v-word';
        word.textContent = item.word || '暂缺';

        const meanLabel = document.createElement('span');
        meanLabel.className = 'v-label';
        meanLabel.textContent = '释义';

        const meaning = document.createElement('p');
        meaning.className = 'v-meaning';
        meaning.textContent = item.meaning || '';

        const speaker = document.createElement('button');
        speaker.className = 'speaker-btn';
        speaker.title = '点击听哈尼发音';
        speaker.setAttribute('aria-label', '播放 ' + (item.word || item.meaning || '') + ' 的哈尼语读音');
        speaker.addEventListener('click', () => speakWord(item, speaker));

        const foot = document.createElement('div');
        foot.className = 'v-foot';
        const hint = document.createElement('span');
        hint.className = 'v-hint';
        hint.textContent = '点击听哈尼发音';
        foot.appendChild(speaker);
        foot.appendChild(hint);

        card.appendChild(cat);
        card.appendChild(wordLabel);
        card.appendChild(word);
        card.appendChild(meanLabel);
        card.appendChild(meaning);
        card.appendChild(foot);
        vocabGrid.appendChild(card);
    });
}

// ---------- 发音 ----------

let currentAudio = null;

function speakWord(item, btn) {
    // 停止上一个音频
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    document.querySelectorAll('.speaker-btn.playing').forEach(b => b.classList.remove('playing'));

    // 1) 数据库里存了音频文件 -> 播放音频
    if (item.audio_url) {
        currentAudio = new Audio(item.audio_url);
        currentAudio.onended = () => btn.classList.remove('playing');
        currentAudio.onerror = () => fallbackSpeak(item, btn);
        btn.classList.add('playing');
        currentAudio.play().catch(() => fallbackSpeak(item, btn));
        return;
    }
    // 2) 没有音频文件 -> 浏览器语音合成：先读哈尼文，再读中文释义
    fallbackSpeak(item, btn);
}

function fallbackSpeak(item, btn) {
    if (!('speechSynthesis' in window)) {
        btn.title = '当前浏览器不支持语音合成';
        return;
    }
    speechSynthesis.cancel();
    btn.classList.add('playing');

    // 朗读顺序：先哈尼文（罗马字，浏览器无哈尼语音故以中文语音近似），再中文释义
    // 满足"读哈尼语 / 两种语言都读"的需求（不再只读中文）
    const queue = [];
    if (item.word) queue.push({ text: item.word, rate: 0.8 });
    if (item.meaning) queue.push({ text: item.meaning, rate: 0.95 });

    let i = 0;
    function speakNext() {
        if (i >= queue.length) { btn.classList.remove('playing'); return; }
        const part = queue[i++];
        const u = new SpeechSynthesisUtterance(part.text);
        u.lang = 'zh-CN';
        u.rate = part.rate;
        u.onend = speakNext;
        u.onerror = speakNext;
        speechSynthesis.speak(u);
    }
    if (queue.length) speakNext();
    else btn.classList.remove('playing');
}

// ---------- 事件 ----------

vocabSearch.addEventListener('input', renderVocab);

// ---------- 启动 ----------

window.addEventListener('DOMContentLoaded', loadVocab);
