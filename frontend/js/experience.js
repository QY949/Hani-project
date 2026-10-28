// ================= 互动体验：哈尼纹样拼图 =================
// 3x3 交换式拼图：点击两块碎片交换位置，全部归位即完成。
// 拼图素材：默认精选几张本地图；页面加载时尝试从 /api/images 拉取 images/ 目录
//          下的全部图片，供用户自由切换（后端未启动时使用精选兜底）。

const PUZZLE_SIZE = 3;
const PUZZLE_COUNT = PUZZLE_SIZE * PUZZLE_SIZE;

// 离线兜底素材（保证不依赖后端也能玩）
const FALLBACK_IMAGES = [
    { src: './images/puzzle_hani_embroidery.jpg', label: '哈尼刺绣纹样' },
    { src: './images/gallery_silver.jpg', label: '哈尼银饰盛装' },
    { src: './images/gallery_embroider_bag.jpg', label: '哈尼刺绣背包' },
    { src: './images/game_hani_kids.jpg', label: '哈尼族童趣' },
    { src: './images/hani_terrace_bg.jpg', label: '哈尼梯田晨雾' },
];
// 不进入拼图选择器的文件
const EXCLUDE_FILES = new Set(['placeholder.jpg', 'ai_avatar.png']);

// 图片友好名（用于动态拉取到的文件名回退）
const IMAGE_LABELS = {
    'puzzle_hani_embroidery.jpg': '哈尼刺绣纹样',
    'gallery_silver.jpg': '哈尼银饰盛装',
    'gallery_costumes.jpg': '哈尼各支系服饰',
    'gallery_headpiece.jpg': '银饰头冠',
    'gallery_bands.jpg': '哈尼刺绣花带',
    'gallery_embroider_bag.jpg': '哈尼刺绣背包',
    'gallery_embroidery_craft.jpg': '哈尼刺绣工艺',
    'gallery_hearth.jpg': '火塘边的哈尼姑娘',
    'gallery_toast.jpg': '长街宴 · 举杯同庆',
    'gallery_longstreet_feast.jpg': '长街宴',
    'game_hani_kids.jpg': '哈尼族童趣',
    'hani_terrace_bg.jpg': '哈尼梯田晨雾',
};
// 完成时的纹样解说（按文件名区分，缺省走通用文案）
const IMAGE_DONE = {
    'puzzle_hani_embroidery.jpg': '你拼出的是哈尼族经典的“回纹”刺绣纹样 —— 常见于衣襟、背包与头巾，象征生生不息。',
    'gallery_silver.jpg': '你拼出的是哈尼银饰盛装 —— 银泡银牌在火塘光里闪烁，是哈尼女子最隆重的节日盛装。',
    'gallery_costumes.jpg': '你拼出的是哈尼各支系服饰 —— 不同支系在配色与银饰上各有讲究，是辨识族群的“活字典”。',
    'gallery_headpiece.jpg': '你拼出的是哈尼银饰头冠 —— 层层银片垂落，随舞步轻响，是盛装的点睛之笔。',
    'gallery_bands.jpg': '你拼出的是哈尼刺绣花带 —— 姑娘们一针一线织出的腰带与背带，藏着对美好生活的祈愿。',
    'gallery_embroider_bag.jpg': '你拼出的是哈尼刺绣背包 —— 几何纹样里装着梯田与山峦，是日常也是艺术。',
    'gallery_embroidery_craft.jpg': '你拼出的是哈尼刺绣工艺 —— 母女相授的指间技艺，已在针线间传承千年。',
    'gallery_hearth.jpg': '你拼出的是火塘边的哈尼姑娘 —— 火塘是哈尼家的中心，也是最温暖的课堂。',
    'gallery_toast.jpg': '你拼出的是长街宴举杯同庆 —— 百家宴席连成一条街，是哈尼最热闹的团圆。',
    'gallery_longstreet_feast.jpg': '你拼出的是长街宴 —— 沿街摆开的千桌宴席，是哈尼人待客的最高礼遇。',
    'game_hani_kids.jpg': '你拼出的是哈尼族童趣 —— 梯田畔长大的孩子，从小就在稻浪里奔跑嬉戏。',
    'hani_terrace_bg.jpg': '你拼出的是哈尼梯田晨雾 —— 层叠如天的梯田，是哈尼人写给大地的诗。',
};

let puzzleImages = FALLBACK_IMAGES.slice();
let currentImageIndex = 0;
let PUZZLE_IMAGE = puzzleImages[0].src;   // 当前拼图底图（会随切换改变）
let currentAspect = 1;                     // 当前底图宽高比，让拼图按原图比例显示（避免拉伸变形）

const board = document.getElementById('puzzleBoard');
const statusEl = document.getElementById('puzzleStatus');
const resetBtn = document.getElementById('puzzleResetBtn');
const hintBtn = document.getElementById('puzzleHintBtn');
const hintBox = document.getElementById('puzzleHintBox');
const hintImg = document.getElementById('puzzleHintImg');
const hintCap = document.getElementById('puzzleHintCap');
const doneBox = document.getElementById('puzzleDone');
const doneText = document.getElementById('puzzleDoneText');
const thumbsWrap = document.getElementById('puzzleThumbs');

let tiles = [];        // tiles[i] = 第 i 格当前放的碎片编号（正确位置即编号 == 下标）
let selectedIndex = -1;
let moves = 0;

// ---------- 工具 ----------

function fileNameOf(url) {
    return String(url || '').split('/').pop();
}
function friendlyName(name) {
    if (IMAGE_LABELS[name]) return IMAGE_LABELS[name];
    return name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');
}

// ---------- 素材选择器 ----------

function buildPicker() {
    if (!thumbsWrap) return;
    thumbsWrap.innerHTML = '';
    puzzleImages.forEach((img, i) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'puzzle-thumb' + (i === currentImageIndex ? ' active' : '');
        btn.title = img.label;
        btn.setAttribute('aria-label', img.label);

        const im = document.createElement('img');
        im.src = img.src;
        im.alt = img.label;
        im.loading = 'lazy';
        im.addEventListener('error', function () {
            if (this.dataset.fb) return;
            this.dataset.fb = '1';
            this.src = './images/placeholder.jpg';
        });

        btn.appendChild(im);
        btn.addEventListener('click', () => selectImage(i));
        thumbsWrap.appendChild(btn);
    });
}

function selectImage(i) {
    if (i === currentImageIndex || i < 0 || i >= puzzleImages.length) return;
    currentImageIndex = i;
    PUZZLE_IMAGE = puzzleImages[i].src;
    updateHint();
    // 高亮当前缩略图
    const all = thumbsWrap.querySelectorAll('.puzzle-thumb');
    all.forEach((el, idx) => el.classList.toggle('active', idx === i));
    shuffleTiles();
    applyImageRatio(PUZZLE_IMAGE);   // 按原图比例重绘，保证与"看原图"一致
}

function updateHint() {
    const img = puzzleImages[currentImageIndex];
    if (hintImg) hintImg.src = img.src;
    if (hintCap) hintCap.textContent = '参考原图：' + img.label + '（拼好就是它！）';
}

// 读取底图真实宽高比并应用到棋盘：让拼图按原图比例显示，与"看原图"一一对应（不再拉伸变形）
let ratioToken = 0;
function applyImageRatio(src) {
    const token = ++ratioToken;   // 防止快速切换时旧图异步回调覆盖新比例
    const im = new Image();
    im.onload = () => {
        if (token !== ratioToken) return;
        currentAspect = (im.naturalWidth && im.naturalHeight) ? im.naturalWidth / im.naturalHeight : 1;
        board.style.aspectRatio = currentAspect;
        renderBoard();   // 以正确比例重绘，确保原图与拼图视觉一致
    };
    im.onerror = () => {
        if (token !== ratioToken) return;
        currentAspect = 1;
        board.style.aspectRatio = '1 / 1';
        renderBoard();
    };
    im.src = src;
}

// ---------- 初始化 / 打乱 ----------

function shuffleTiles() {
    do {
        tiles = [];
        for (let i = 0; i < PUZZLE_COUNT; i++) tiles.push(i);
        for (let i = tiles.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [tiles[i], tiles[j]] = [tiles[j], tiles[i]];
        }
    } while (isSolved());   // 保证开局不是已完成状态

    selectedIndex = -1;
    moves = 0;
    doneBox.classList.remove('show');
    renderBoard();
    updateStatus();
}

// ---------- 渲染 ----------

function renderBoard() {
    board.innerHTML = '';
    tiles.forEach((piece, position) => {
        const tile = document.createElement('button');
        tile.type = 'button';
        tile.className = 'puzzle-tile';
        tile.setAttribute('aria-label', '碎片 ' + (position + 1));

        // 切片显示：background-size 300% + position 按碎片正确位置偏移
        tile.style.backgroundImage = 'url("' + PUZZLE_IMAGE + '")';
        tile.style.backgroundSize = (PUZZLE_SIZE * 100) + '% ' + (PUZZLE_SIZE * 100) + '%';
        tile.style.backgroundPosition =
            ((piece % PUZZLE_SIZE) * (100 / (PUZZLE_SIZE - 1))) + '% ' +
            (Math.floor(piece / PUZZLE_SIZE) * (100 / (PUZZLE_SIZE - 1))) + '%';

        if (piece === position) tile.classList.add('solved');
        if (position === selectedIndex) tile.classList.add('selected');

        tile.addEventListener('click', () => onTileClick(position));
        board.appendChild(tile);
    });
}

function updateStatus() {
    const solvedCount = tiles.filter((piece, position) => piece === position).length;
    statusEl.innerHTML = '已归位 <b>' + solvedCount + ' / ' + PUZZLE_COUNT + '</b> · 交换 ' + moves + ' 次';
}

// ---------- 交互 ----------

function onTileClick(position) {
    if (isSolved()) return;

    if (selectedIndex === -1) {
        selectedIndex = position;
        renderBoard();
        return;
    }
    if (selectedIndex === position) {
        selectedIndex = -1;   // 再次点击取消选中
        renderBoard();
        return;
    }

    // 交换两块
    [tiles[selectedIndex], tiles[position]] = [tiles[position], tiles[selectedIndex]];
    moves += 1;
    selectedIndex = -1;
    renderBoard();
    updateStatus();

    if (isSolved()) {
        const name = fileNameOf(PUZZLE_IMAGE);
        if (doneText) {
            doneText.textContent = IMAGE_DONE[name] ||
                ('你成功拼出了「' + puzzleImages[currentImageIndex].label + '」！每一块碎片归位，都是一次对哈尼文化的指尖触摸。');
        }
        doneBox.classList.add('show');
        doneBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function isSolved() {
    return tiles.every((piece, position) => piece === position);
}

// ---------- 按钮 ----------

resetBtn.addEventListener('click', shuffleTiles);

hintBtn.addEventListener('click', () => {
    const showing = hintBox.style.display !== 'none';
    hintBox.style.display = showing ? 'none' : 'block';
    hintBtn.textContent = showing ? '看原图' : '隐藏原图';
});

// ---------- 启动 ----------

buildPicker();
updateHint();
shuffleTiles();
applyImageRatio(PUZZLE_IMAGE);   // 按真实比例渲染首图，与"看原图"一致

// 尝试从后端拉取 images/ 目录全部图片，作为可切换的拼图素材（后端未启动则保持兜底）
fetch('/api/images')
    .then(r => (r.ok ? r.json() : null))
    .then(data => {
        if (!data || !Array.isArray(data.images) || !data.images.length) return;
        const list = data.images
            .map(u => fileNameOf(u))
            .filter(n => n && !EXCLUDE_FILES.has(n))
            .map(n => ({ src: './images/' + n, label: friendlyName(n) }));
        if (!list.length) return;
        // 保留用户当前选择的图片：若当前底图在新列表中，定位到同一张；否则回到第一张
        const keepSrc = PUZZLE_IMAGE;
        const keepIdx = list.findIndex(x => x.src === keepSrc);
        puzzleImages = list;
        currentImageIndex = keepIdx >= 0 ? keepIdx : 0;
        PUZZLE_IMAGE = puzzleImages[currentImageIndex].src;
        buildPicker();
        updateHint();
        shuffleTiles();
        applyImageRatio(PUZZLE_IMAGE);
    })
    .catch(() => { /* 离线模式：使用兜底素材 */ });
