// ================= 图集页：瀑布流 + 上传 =================
// 数据来源（两路合并，数据库记录优先）：
//   1) GET /api/gallery  —— 数据库 gallery 表（含标题/描述/上传者）
//   2) GET /api/images    —— 扫描 frontend/images/ 目录，手动放进来的图片自动上墙
// 上传：POST /api/upload（multipart，登录用户）-> 保存到 frontend/images/，数据库存 images/xxx.jpg
// 删除：DELETE /api/gallery/:id（上传者本人 / 管理员）
const galleryGrid = document.getElementById('galleryGrid');
const galleryCount = document.getElementById('galleryCount');
const uploadForm = document.getElementById('uploadForm');
const uploadBtn = document.getElementById('uploadBtn');
const uploadStatus = document.getElementById('uploadStatus');
const uploadFormWrap = document.getElementById('uploadFormWrap');
const uploadLoginTip = document.getElementById('uploadLoginTip');
const uploadTriggerBtn = document.getElementById('uploadTriggerBtn');
const lightbox = document.getElementById('lightbox');
const lightboxImg = document.getElementById('lightboxImg');
const lightboxCaption = document.getElementById('lightboxCaption');

// images/ 目录内置素材的友好标题（数据库无记录时使用）
const FRIENDLY_NAMES = {
    'hani_terrace_bg.jpg': '哈尼梯田 · 蘑菇房村落',
    'gallery_longstreet_feast.jpg': '长街宴',
    'gallery_toast.jpg': '长街宴 · 举杯同庆',
    'gallery_hearth.jpg': '火塘边的哈尼姑娘',
    'gallery_costumes.jpg': '哈尼族各支系服饰',
    'gallery_silver.jpg': '哈尼银饰盛装',
    'gallery_headpiece.jpg': '银饰头冠',
    'gallery_bands.jpg': '哈尼刺绣花带',
    'gallery_embroider_bag.jpg': '哈尼刺绣背包',
    'gallery_embroidery_craft.jpg': '哈尼刺绣工艺',
    'puzzle_hani_embroidery.jpg': '哈尼刺绣纹样',
    'game_hani_kids.jpg': '哈尼族童趣插画',
};

// 不参与图集展示的文件（占位图 / 入口背景由页面自行引用）
const HIDDEN_FILES = new Set(['placeholder.jpg']);

let galleryItems = [];

// ---------- 渲染 ----------

function showEmpty(message) {
    galleryGrid.innerHTML =
        '<p class="empty-tip">' + (message || '图集还是空的，登录后上传第一张哈尼影像吧！') + '</p>';
    galleryCount.textContent = '共 0 张图片';
}

function fileNameOf(url) {
    return String(url || '').split('/').pop();
}

function friendlyTitle(url, fallbackTitle) {
    if (fallbackTitle) return fallbackTitle;
    const name = fileNameOf(url);
    if (FRIENDLY_NAMES[name]) return FRIENDLY_NAMES[name];
    // 上传的随机文件名 -> 去掉随机前缀，取可读部分
    return name.replace(/^[0-9a-f]{12}_[0-9a-f]{8}\./, '上传图片 ');
}

function renderGallery(items) {
    galleryItems = items;
    if (!galleryItems.length) {
        showEmpty();
        return;
    }
    galleryCount.textContent = '共 ' + galleryItems.length + ' 张图片';
    galleryGrid.innerHTML = '';

    galleryItems.forEach(item => {
        const card = document.createElement('div');
        card.className = 'g-card';

        const img = document.createElement('img');
        img.src = item.image_url;
        img.alt = item.title || '哈尼非遗图集';
        img.loading = 'lazy';
        img.addEventListener('error', function () {
            if (this.dataset.fallbackApplied) return;
            this.dataset.fallbackApplied = '1';
            this.src = './images/placeholder.jpg';
        });
        img.addEventListener('click', () => openLightbox(item.image_url, item.title));

        const info = document.createElement('div');
        info.className = 'g-info';

        const title = document.createElement('h4');
        title.textContent = item.title || '未命名图集';

        const desc = document.createElement('p');
        desc.textContent = item.description || '';

        info.appendChild(title);
        info.appendChild(desc);
        // 仅保留“上传者”，不显示“来源”
        if (item.uploader_name) {
            const uploader = document.createElement('p');
            uploader.className = 'g-uploader';
            uploader.textContent = '上传者：' + item.uploader_name;
            info.appendChild(uploader);
        }

        // 本人 / 管理员可删除（仅数据库记录可删）
        const user = Auth.user;
        if (item.id && user && (user.role === 'admin' || user.id === item.uploader_id)) {
            const delBtn = document.createElement('button');
            delBtn.className = 'g-delete';
            delBtn.textContent = '删除';
            delBtn.addEventListener('click', () => deleteGallery(item.id, item.title));
            info.appendChild(delBtn);
        }

        card.appendChild(img);
        card.appendChild(info);
        galleryGrid.appendChild(card);
    });
}

// ---------- 数据加载：数据库记录 + 目录扫描合并 ----------

function loadGallery() {
    galleryCount.textContent = '正在加载图集...';

    Promise.all([
        fetch('/api/gallery').then(r => r.ok ? r.json() : []).catch(() => []),
        fetch('/api/images').then(r => r.ok ? r.json() : { images: [] }).catch(() => ({ images: [] })),
    ])
        .then(([dbItems, dirResult]) => {
            const merged = [];
            const seen = new Set();

            // 1. 数据库记录优先（带标题/描述/上传者）
            (dbItems || []).forEach(item => {
                if (!item || !item.image_url) return;
                seen.add(fileNameOf(item.image_url));
                merged.push(item);
            });

            // 2. 目录扫描补充（数据库里没有的本地文件）
            (dirResult.images || []).forEach(url => {
                const name = fileNameOf(url);
                if (seen.has(name) || HIDDEN_FILES.has(name)) return;
                seen.add(name);
                merged.push({
                    id: null,
                    title: FRIENDLY_NAMES[name] || '',
                    image_url: url,
                    description: '',
                    uploader_name: '',
                    uploader_id: null,
                });
            });

            renderGallery(merged);
        })
        .catch(error => {
            console.error('连接 Flask 后端失败:', error);
            showEmpty('暂无图集数据 —— 请启动后端服务（python app.py）');
        });
}

// ---------- 上传 ----------

function setUploadStatus(message, type) {
    uploadStatus.textContent = message;
    uploadStatus.className = 'upload-status' + (type ? ' ' + type : '');
}

uploadTriggerBtn.addEventListener('click', () => {
    // 游客点击上传按钮：展开面板并引导登录
    if (!Auth.isLoggedIn()) {
        Auth.requireLogin('上传图片');
        return;
    }
    uploadFormWrap.scrollIntoView({ behavior: 'smooth', block: 'center' });
    document.getElementById('uploadFile').focus();
});

uploadForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!Auth.requireLogin('上传图片')) return;

    const fileInput = document.getElementById('uploadFile');
    const file = fileInput.files[0];
    if (!file) {
        setUploadStatus('请先选择要上传的图片', 'error');
        return;
    }
    if (file.size > 8 * 1024 * 1024) {
        setUploadStatus('图片大小超过 8MB 限制，请压缩后再上传', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', document.getElementById('uploadTitle').value.trim());
    formData.append('description', document.getElementById('uploadDesc').value.trim());

    uploadBtn.disabled = true;
    setUploadStatus('正在上传...', '');
    try {
        const response = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await response.json();
        if (!response.ok) {
            setUploadStatus(data.error || '上传失败', 'error');
            return;
        }
        setUploadStatus('上传成功！路径：' + data.url, 'success');
        uploadForm.reset();
        loadGallery();
    } catch (error) {
        setUploadStatus('网络错误：无法连接服务器，请确认后端已启动', 'error');
    } finally {
        uploadBtn.disabled = false;
    }
});

// ---------- 删除图集（本人 / 管理员） ----------

async function deleteGallery(id, title) {
    if (!confirm('确定删除图集「' + (title || id) + '」吗？（仅删除记录，图片文件保留在 images/ 目录）')) return;
    try {
        const response = await fetch('/api/gallery/' + id, { method: 'DELETE' });
        const data = await response.json();
        if (!response.ok) {
            alert(data.error || '删除失败');
            return;
        }
        loadGallery();
    } catch (error) {
        alert('网络错误：无法连接服务器');
    }
}

// ---------- 灯箱 ----------

function openLightbox(url, title) {
    lightboxImg.src = url;
    lightboxCaption.textContent = title || '';
    lightbox.style.display = 'flex';
}
lightbox.addEventListener('click', () => {
    lightbox.style.display = 'none';
    lightboxImg.removeAttribute('src');
});
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') lightbox.style.display = 'none';
});

// ---------- 登录态联动 ----------

function refreshUploadPanel() {
    const loggedIn = Auth.isLoggedIn();
    uploadFormWrap.style.display = loggedIn ? 'block' : 'none';
    uploadLoginTip.style.display = loggedIn ? 'none' : 'block';
}
document.addEventListener('auth:changed', () => {
    refreshUploadPanel();
    loadGallery();  // 登录态变化后重渲染（删除按钮显隐）
});

// ---------- 启动 ----------

window.addEventListener('DOMContentLoaded', () => {
    refreshUploadPanel();
    loadGallery();
});
