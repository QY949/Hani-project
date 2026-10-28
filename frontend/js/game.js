// ================= 梯田守护者 · 哈尼文化问答 =================
// 题库（每题 4 个选项，含解析）；每局随机抽取 8 题，选项顺序打乱。
const QUESTION_POOL = [
    {
        q: '红河哈尼梯田是在哪一年被列入世界文化遗产名录的？',
        options: ['1999 年', '2005 年', '2013 年', '2018 年'],
        answer: 2,
        explain: '2013 年，"红河哈尼梯田文化景观"被联合国教科文组织列入世界文化遗产名录。',
    },
    {
        q: '哈尼族最盛大的传统节日是哪一个？',
        options: ['十月年', '火把节', '泼水节', '盘王节'],
        answer: 0,
        explain: '十月年是哈尼族最盛大的节日，农历十月第一个属龙日开始，人们祭祖、宴亲、歌舞，庆祝一年丰收。',
    },
    {
        q: '绵延数百米的"长街宴"与哪个节庆密切相关？',
        options: ['昂玛突节', '火把节', '泼水节', '三月三'],
        answer: 0,
        explain: '昂玛突节祭祀寨神、林神之后，全村沿街摆桌连成宴席，称为长街宴，象征族群团结与共享丰收。',
    },
    {
        q: '哈尼族传统民居"蘑菇房"的结构特点是？',
        options: ['夯土为墙、茅草为顶，形似蘑菇', '全竹拼接、架空防潮', '石块砌墙、平顶晒台', '圆形帐篷、可拆迁移'],
        answer: 0,
        explain: '蘑菇房夯土为墙、茅草为顶，形似蘑菇，冬暖夏凉，与森林、梯田共同构成哈尼村落景观。',
    },
    {
        q: '哈尼语属于哪个语支？',
        options: ['彝语支', '壮傣语支', '苗瑶语支', '藏语支'],
        answer: 0,
        explain: '哈尼语属汉藏语系藏缅语族彝语支，内部分哈雅、豪白、碧卡三大方言。',
    },
    {
        q: '拼音哈尼文创制于哪一年？',
        options: ['1949 年', '1957 年', '1966 年', '1982 年'],
        answer: 1,
        explain: '1957 年，以哈雅方言绿春县大寨哈尼话为标准音创制了拼音哈尼文。',
    },
    {
        q: '现行哈尼文的标准音地点在哪里？',
        options: ['绿春县大寨', '元阳县箐口', '墨江县城', '勐海县打洛'],
        answer: 0,
        explain: '哈尼文以哈雅方言绿春县大寨哈尼话为标准音。',
    },
    {
        q: '哈尼梯田农耕系统著名的"四素同构"指的是？',
        options: ['森林—村寨—梯田—水系', '山—水—林—田', '天—地—人—神', '森林—河谷—集镇—道路'],
        answer: 0,
        explain: '"森林—村寨—梯田—水系"四素同构、循环利用，是哈尼人千年农耕智慧的结晶。',
    },
    {
        q: '被列入国家级非物质文化遗产的"哈尼哈吧"是什么艺术？',
        options: ['古老的民间说唱艺术', '祭祀性群体舞蹈', '多声部山歌对唱', '葫芦丝演奏技艺'],
        answer: 0,
        explain: '哈尼哈吧是哈尼族古老的民间说唱艺术，内容涵盖创世、迁徙与农耕。',
    },
    {
        q: '哈尼族群体舞蹈"乐作舞"的表演形式是？',
        options: ['众人围圈而舞', '单人独舞', '两人对舞', '沿长桌行列舞'],
        answer: 0,
        explain: '乐作舞是哈尼族围圈而舞的群体舞蹈，与多声部民歌一同被列入国家级非物质文化遗产。',
    },
    {
        q: '从民族源流看，哈尼族先民主要来自哪个古代族群系统？',
        options: ['氐羌', '百越', '百濮', '三苗'],
        answer: 0,
        explain: '哈尼族与彝、拉祜、纳西等族同源于古代氐羌族群，历经"和夷—和蛮—和尼"的历史演变。',
    },
    {
        q: '世界文化遗产"红河哈尼梯田"位于哪个州市？',
        options: ['红河哈尼族彝族自治州', '普洱市', '西双版纳州', '文山州'],
        answer: 0,
        explain: '红河哈尼梯田位于云南省红河州，核心区分布在元阳、红河、金平、绿春等县。',
    },
];

const TOTAL_QUESTIONS = 8;

// 称号与评语
function getRank(score) {
    if (score >= 8) return { title: '非遗传承大使', comment: '满分！你对哈尼文化的了解已经堪比村寨里的长老，梯田因你而生生不息。' };
    if (score >= 6) return { title: '梯田守护者', comment: '非常出色！哈尼文化的大半风景都已装在你心里，再去图集里印证一番吧。' };
    if (score >= 4) return { title: '哈尼文化爱好者', comment: '不错的开始！去"历史文化"页逛一逛，下次挑战定能更上一层楼。' };
    return { title: '梯田初学者', comment: '每一级梯田都从第一锄开始——先去历史文化页补补课，再来挑战！' };
}

// ---------- 状态 ----------

let quizQuestions = [];
let quizIndex = 0;
let quizScore = 0;
let quizAnswered = false;

// ---------- 元素 ----------

const startPanel = document.getElementById('quizStart');
const quizBody = document.getElementById('quizBody');
const quizResult = document.getElementById('quizResult');
const startBtn = document.getElementById('quizStartBtn');
const retryBtn = document.getElementById('quizRetryBtn');
const nextBtn = document.getElementById('quizNextBtn');
const stepEl = document.getElementById('quizStep');
const barEl = document.getElementById('quizBar');
const scoreNowEl = document.getElementById('quizScoreNow');
const questionEl = document.getElementById('quizQuestion');
const optionsEl = document.getElementById('quizOptions');
const feedbackEl = document.getElementById('quizFeedback');
const finalScoreEl = document.getElementById('quizFinalScore');
const titleEl = document.getElementById('quizTitle');
const commentEl = document.getElementById('quizComment');

// ---------- 工具 ----------

function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
}

// ---------- 流程 ----------

function startQuiz() {
    // 抽题 + 打乱每题选项（答案索引随选项一起调整）
    quizQuestions = shuffle(QUESTION_POOL).slice(0, TOTAL_QUESTIONS).map(item => {
        const correctText = item.options[item.answer];
        const options = shuffle(item.options);
        return { q: item.q, options, answer: options.indexOf(correctText), explain: item.explain };
    });
    quizIndex = 0;
    quizScore = 0;

    startPanel.style.display = 'none';
    quizResult.style.display = 'none';
    quizBody.style.display = 'block';
    renderQuestion();
}

function renderQuestion() {
    quizAnswered = false;
    const item = quizQuestions[quizIndex];

    stepEl.textContent = '第 ' + (quizIndex + 1) + ' / ' + TOTAL_QUESTIONS + ' 题';
    barEl.style.width = (quizIndex / TOTAL_QUESTIONS) * 100 + '%';
    scoreNowEl.textContent = '得分 ' + quizScore;
    questionEl.textContent = item.q;
    feedbackEl.textContent = '';
    feedbackEl.className = 'quiz-feedback';
    nextBtn.style.display = 'none';

    optionsEl.innerHTML = '';
    const keys = ['A', 'B', 'C', 'D'];
    item.options.forEach((text, i) => {
        const btn = document.createElement('button');
        btn.className = 'quiz-option';

        const key = document.createElement('span');
        key.className = 'opt-key';
        key.textContent = keys[i] || (i + 1);

        const label = document.createElement('span');
        label.textContent = text;

        btn.appendChild(key);
        btn.appendChild(label);
        btn.addEventListener('click', () => answerQuestion(i));
        optionsEl.appendChild(btn);
    });
}

function answerQuestion(picked) {
    if (quizAnswered) return;
    quizAnswered = true;

    const item = quizQuestions[quizIndex];
    const buttons = optionsEl.querySelectorAll('.quiz-option');
    const correct = picked === item.answer;

    buttons.forEach((btn, i) => {
        btn.disabled = true;
        if (i === item.answer) btn.classList.add('correct');
        else if (i === picked) btn.classList.add('wrong');
    });

    if (correct) {
        quizScore += 1;
        feedbackEl.className = 'quiz-feedback ok';
        feedbackEl.textContent = '回答正确，梯田又添一级！';
    } else {
        feedbackEl.className = 'quiz-feedback no';
        feedbackEl.textContent = '答错了，正确答案是 ' + 'ABCD'[item.answer] + '。';
    }

    const explain = document.createElement('span');
    explain.className = 'explain';
    explain.textContent = item.explain;
    feedbackEl.appendChild(explain);

    scoreNowEl.textContent = '得分 ' + quizScore;
    nextBtn.textContent = quizIndex + 1 === TOTAL_QUESTIONS ? '查看结果' : '下一题';
    nextBtn.style.display = 'inline-block';
}

function showResult() {
    quizBody.style.display = 'none';
    quizResult.style.display = 'block';

    finalScoreEl.textContent = quizScore;
    const rank = getRank(quizScore);
    titleEl.textContent = rank.title;
    commentEl.textContent = rank.comment;
}

// ---------- 事件 ----------

startBtn.addEventListener('click', startQuiz);
retryBtn.addEventListener('click', startQuiz);
nextBtn.addEventListener('click', () => {
    if (quizIndex + 1 < TOTAL_QUESTIONS) {
        quizIndex += 1;
        renderQuestion();
    } else {
        showResult();
    }
});
