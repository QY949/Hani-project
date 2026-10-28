#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spider.py —— 哈尼族语言文化词汇爬虫
====================================

数据来源：云南少数民族语言文化网（云南省民语委办公室主办）
          https://www.ynmyw.cn

本项目只采集【哈尼族】词汇数据，提取字段：
  民族(ethnic_group) / 词汇(word) / 中文释义(meaning) / 分类(category)

反爬策略：
  - User-Agent 池随机轮换
  - 每次请求前随机休眠 1~3 秒（可用参数调整）
  - 失败自动重试（指数退避）
  - 入库前按 (民族, 词汇) 去重，重复数据自动跳过

用法：
  python spider.py                 # 正式爬取并写入数据库
  python spider.py --dry-run       # 只解析、不写库（调试用）
  python spider.py --delay-min 2 --delay-max 5   # 自定义休眠区间
"""

import argparse
import os
import random
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from init_db import DEFAULT_CATEGORY, DB_PATH, get_connection  # noqa: E402

# ---------------------------------------------------------------- 爬虫配置 ----

# 只配置哈尼族词源。想扩充词库时，按同样格式继续往下加即可。
# category 不写则按标题关键词自动推断（见 guess_category）。
SOURCES = [
    {
        "name": "2019年哈尼语新词术语",
        "ethnic_group": "哈尼族",
        "category": "日常",
        "url": "https://www.ynmyw.cn/view/cnAppHtml/22/40/view/6631.html",
    },
    {
        "name": "2020年哈尼语新词术语",
        "ethnic_group": "哈尼族",
        "category": "日常",
        "url": "https://www.ynmyw.cn/view/cnAppHtml/22/40/view/6630.html",
    },
    {
        "name": "2021年哈尼语新词术语",
        "ethnic_group": "哈尼族",
        "category": "日常",
        "url": "https://www.ynmyw.cn/view/cnAppHtml/22/40/view/6633.html",
    },
    {
        "name": "2023年哈尼语新词术语",
        "ethnic_group": "哈尼族",
        "category": "日常",
        "url": "https://www.ynmyw.cn/view/cnAppHtml/22/40/view/6634.html",
    },
]

# User-Agent 池（每次请求随机挑一个）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

# 表头/无效单元格关键词（命中即跳过）
HEADER_TOKENS = {
    "汉文", "瑶文", "勉文", "哈尼文", "民文", "序号", "编号", "中文", "词汇", "分类",
    "词条", "民族", "注音", "读音", "示例", "说明", "国际音标", "备注",
}

# 标题关键词 -> 词汇分类
CATEGORY_RULES = (
    ("农耕", ("农耕", "农事", "梯田", "作物", "种植", "粮食", "收获")),
    ("动植物", ("动植物", "草木", "草药", "花卉", "鸟", "鱼", "虫", "牲畜", "野兽")),
    ("称谓", ("称谓", "问候", "亲属", "称呼")),
    ("身体", ("身体", "人体", "部位")),
    ("数字颜色", ("数字", "颜色", "数量")),
    ("文化习俗", ("节庆", "习俗", "歌舞", "服饰", "仪式", "文学", "歌谣", "文化", "非遗")),
    ("自然", ("自然", "天地", "山川", "气候")),
)


def guess_category(text):
    """根据页面标题推断词汇分类，命中不了就归入默认分类。"""
    for category, keywords in CATEGORY_RULES:
        if any(keyword in text for keyword in keywords):
            return category
    return DEFAULT_CATEGORY


# ---------------------------------------------------------------- 网络请求 ----

def fetch(url, session, timeout=15, delay_range=(1.0, 3.0), retries=3):
    """带 UA 轮换、随机休眠、失败重试的页面抓取。失败返回 None。"""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            time.sleep(random.uniform(*delay_range))  # 随机休眠，降低被封风险
            response = session.get(
                url,
                headers={"User-Agent": random.choice(USER_AGENTS)},
                timeout=timeout,
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except requests.RequestException as error:
            last_error = error
            wait = 2 * attempt
            print("    第 {}/{} 次请求失败（{}），{} 秒后重试 ...".format(attempt, retries, error, wait))
            time.sleep(wait)
    print("    [放弃] {} —— {}".format(url, last_error))
    return None


# ---------------------------------------------------------------- 页面解析 ----

def _is_header(text):
    """判断是否为表头/无效单元格。"""
    if not text:
        return True
    if text in HEADER_TOKENS:
        return True
    return text.startswith(("汉文", "民文", "序号", "编号", "瑶文", "勉文", "哈尼文"))


def parse_vocab_pairs(html):
    """从页面提取 (中文释义, 民族语词汇) 列表。

    兼容三类表格结构：
      - 2 列 ：汉文 | 哈尼文
      - 3 列 ：序号 | 汉文 | 哈尼文
      - 4/6 列：一行里放多组“汉文 | 哈尼文”
    """
    soup = BeautifulSoup(html, "lxml")
    raw_pairs = []

    for tr in soup.find_all("tr"):
        cells = [
            re.sub(r"\s+", " ", td.get_text().replace("\xa0", " ")).strip()
            for td in tr.find_all("td")
        ]
        if len(cells) == 2:
            raw_pairs.append((cells[0], cells[1]))
        elif len(cells) == 3 and cells[0].isdigit():
            raw_pairs.append((cells[1], cells[2]))
        elif len(cells) >= 4:
            for index in range(0, len(cells) - 1, 2):
                raw_pairs.append((cells[index], cells[index + 1]))

    pairs = []
    seen = set()
    for meaning, word in raw_pairs:
        clean_meaning = re.sub(r"\s+", "", meaning)      # 中文释义去掉所有空白
        clean_word = re.sub(r"\s+", " ", word).strip()   # 民族语保留单词间的单个空格
        if _is_header(clean_meaning) or _is_header(re.sub(r"\s+", "", clean_word)):
            continue
        if not clean_meaning or not clean_word:
            continue
        if clean_meaning.isdigit() or clean_word.isdigit():
            continue
        if len(clean_meaning) > 40 or len(clean_word) > 80:  # 过滤误抓的长段落
            continue
        if (clean_meaning, clean_word) in seen:              # 页内去重
            continue
        seen.add((clean_meaning, clean_word))
        pairs.append((clean_meaning, clean_word))

    return pairs


# ---------------------------------------------------------------- 主流程 ------

def crawl(db_path=DB_PATH, sources=None, delay_range=(1.0, 3.0), timeout=15, retries=3, dry_run=False):
    sources = sources or SOURCES
    conn = get_connection(db_path)

    # 预载已有数据，避免重复入库
    existing = {(row["ethnic_group"], row["word"]) for row in conn.execute(
        "SELECT ethnic_group, word FROM vocabulary"
    )}

    session = requests.Session()
    total_new = total_dup = 0

    for source in sources:
        url = source["url"]
        group = source["ethnic_group"]
        print("\n>> [{}] {}".format(group, source["name"]))
        print("   {}".format(url))

        html = fetch(url, session, timeout=timeout, delay_range=delay_range, retries=retries)
        if not html:
            continue

        pairs = parse_vocab_pairs(html)
        category = source.get("category") or guess_category(source["name"])
        new_count = dup_count = 0

        for meaning, word in pairs:
            if (group, word) in existing:
                dup_count += 1
                continue
            existing.add((group, word))
            new_count += 1
            if not dry_run:
                conn.execute(
                    "INSERT OR IGNORE INTO vocabulary"
                    " (ethnic_group, word, meaning, category, audio_url, source_url)"
                    " VALUES (?, ?, ?, ?, '', ?)",
                    (group, word, meaning, category, url),
                )

        if not dry_run:
            conn.commit()
        total_new += new_count
        total_dup += dup_count
        print("   解析 {} 条 -> 新增 {} 条，重复跳过 {} 条（分类：{}）".format(
            len(pairs), new_count, dup_count, category))

    conn.close()
    print("\n爬取完成！共新增 {} 条，重复跳过 {} 条。".format(total_new, total_dup))
    if dry_run:
        print("（--dry-run 演练模式，未写入数据库）")
    return total_new


def main():
    parser = argparse.ArgumentParser(
        description="哈尼族语言文化词汇爬虫（数据来源：云南少数民族语言文化网 ynmyw.cn）")
    parser.add_argument("--db", default=DB_PATH, help="数据库文件路径（默认：backend/ich_data.db）")
    parser.add_argument("--delay-min", type=float, default=1.0, help="请求前随机休眠下限（秒）")
    parser.add_argument("--delay-max", type=float, default=3.0, help="请求前随机休眠上限（秒）")
    parser.add_argument("--timeout", type=int, default=15, help="单次请求超时（秒）")
    parser.add_argument("--retries", type=int, default=3, help="失败重试次数")
    parser.add_argument("--dry-run", action="store_true", help="只解析、不写库（调试用）")
    args = parser.parse_args()

    print("=" * 56)
    print("哈尼族语言文化词汇爬虫 · 数据来源：ynmyw.cn（云南省民语委）")
    print("词源 {} 个 | 休眠 {:.0f}~{:.0f} 秒 | 重试 {} 次".format(
        len(SOURCES), args.delay_min, args.delay_max, args.retries))
    print("=" * 56)

    if args.delay_min > args.delay_max:
        parser.error("--delay-min 不能大于 --delay-max")

    crawl(
        db_path=args.db,
        delay_range=(args.delay_min, args.delay_max),
        timeout=args.timeout,
        retries=args.retries,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
