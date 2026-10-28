// ================= 首页动效 =================
// 1. hero 文字依次入场
// 2. 模块卡片滚动显现（IntersectionObserver）
// 3. 图片加载失败时优雅降级为占位图（./images/placeholder.jpg）

function fallbackPlaceholder(img) {
    if (img.dataset.fallbackApplied) return;
    img.dataset.fallbackApplied = '1';
    img.src = './images/placeholder.jpg';
}

window.addEventListener('DOMContentLoaded', () => {
    // ---- hero 入场 ----
    const hero = document.getElementById('hero');
    if (hero) {
        const parts = [hero.querySelector('.hero-kicker'), hero.querySelector('h1'),
                       hero.querySelector('.hero-sub'), hero.querySelector('.hero-actions')];
        parts.forEach((el, i) => {
            if (!el) return;
            el.style.opacity = '0';
            el.style.transform = 'translateY(24px)';
            el.style.transition = 'opacity 0.8s ease ' + (i * 0.15 + 0.15) + 's, transform 0.8s ease ' + (i * 0.15 + 0.15) + 's';
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    el.style.opacity = '1';
                    el.style.transform = 'translateY(0)';
                });
            });
        });
    }

    // ---- 模块卡片滚动显现 ----
    const cards = document.querySelectorAll('.module-card, .g-card, .vocab-card, .pattern-card');
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });
        cards.forEach((card, i) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(28px)';
            card.style.transition = 'opacity 0.6s ease ' + (i % 4) * 0.08 + 's, transform 0.6s ease ' + (i % 4) * 0.08 + 's';
            observer.observe(card);
        });
    }

    // ---- 全站图片加载失败 -> 占位图 ----
    document.querySelectorAll('img').forEach(img => {
        if (!img.complete && !img.src) return;
        img.addEventListener('error', () => fallbackPlaceholder(img));
    });
});
