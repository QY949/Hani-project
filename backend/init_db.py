#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_db.py —— “向世界介绍云南少数民族”项目 · 数据库初始化脚本
================================================================

功能：
  1. 创建三张核心数据表（SQLite，数据库文件：backend/ich_data.db）：

     - users      用户表：id / username / password_hash / role（admin / user / guest）
     - vocabulary 词汇表：id / ethnic_group（民族）/ word（词汇）/ meaning（中文释义）
                          / category（分类）/ audio_url（语音路径）/ source_url（来源）
     - gallery    图集表：id / title / image_url / description / uploader_id（关联 users）

  2. 写入种子数据：默认管理员 admin / admin123（首次登录后请尽快修改）。

  3. 自动清理已废弃的 vocabulary_legacy 旧表（早期瑶族词汇表，项目已转向哈尼族）。

用法：
  python init_db.py              # 初始化（幂等，可反复执行）
  python init_db.py --quiet      # 安静模式（供启动脚本调用）
  python init_db.py --reset      # 清空三张业务表后重建
  python init_db.py --db 路径    # 指定其它数据库文件
"""

import argparse
import hashlib
import os
import secrets
import sqlite3

# ------------------------------------------------------------------ 配置 ----

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ich_data.db")

# 词汇分类（与爬虫 spider.py 共用）
CATEGORIES = ("日常", "动植物", "农耕", "称谓", "身体", "数字颜色", "自然", "文化习俗")
DEFAULT_CATEGORY = "日常"

# 用户角色
ROLES = ("admin", "user", "guest")

SCHEMA_STATEMENTS = [
    # ---------------- 用户表 ----------------
    """CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    NOT NULL UNIQUE,                 -- 用户名（唯一）
        password_hash TEXT    NOT NULL,                        -- PBKDF2 密码哈希
        role          TEXT    NOT NULL DEFAULT 'user'          -- 角色：admin / user / guest
                      CHECK (role IN ('admin', 'user', 'guest')),
        created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
    )""",
    # ---------------- 词汇表 ----------------
    """CREATE TABLE IF NOT EXISTS vocabulary (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        ethnic_group TEXT    NOT NULL,                          -- 民族，如：哈尼族
        word         TEXT    NOT NULL,                          -- 民族语词汇
        meaning      TEXT    NOT NULL,                          -- 中文释义
        category     TEXT    NOT NULL DEFAULT '日常',           -- 分类：日常/动植物/农耕/称谓/文化习俗 ...
        audio_url    TEXT    NOT NULL DEFAULT '',               -- 语音文件路径（暂无则留空）
        source_url   TEXT    NOT NULL DEFAULT '',               -- 数据来源网址
        created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        UNIQUE (ethnic_group, word)                             -- 同一民族同一词汇只存一条
    )""",
    # ---------------- 图集表 ----------------
    """CREATE TABLE IF NOT EXISTS gallery (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT    NOT NULL,                           -- 图集标题
        image_url   TEXT    NOT NULL,                           -- 图片路径/网址
        description TEXT    NOT NULL DEFAULT '',                -- 图片描述
        uploader_id INTEGER REFERENCES users (id)               -- 上传者（关联 users.id）
                    ON DELETE SET NULL,                         -- 用户删除后，图片保留、上传者置空
        created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_vocab_group     ON vocabulary (ethnic_group)",
    "CREATE INDEX IF NOT EXISTS idx_vocab_category  ON vocabulary (category)",
    "CREATE INDEX IF NOT EXISTS idx_gallery_uploader ON gallery (uploader_id)",
]

# 图集演示数据：动态扫描 frontend/assets/images 下真实存在的前 3 张图片，
# 避免硬编码文件名导致死链（换图后重新运行 init_db.py 即可刷新演示数据）
DEMO_GALLERY_LIMIT = 3


def _demo_gallery_rows():
    """演示图集：固定指向 frontend/images/ 下的本地语义图（文件存在才写入）。

    全站图片规则：只使用 frontend/images/ 本地相对路径（数据库存 images/xxx.jpg）。
    用户后续把图片放进 frontend/images/ 目录，图集页 /api/images 会自动扫描展示，
    无需改这里的演示数据。
    """
    images_dir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "images"))
    candidates = (
        ("长街宴", "gallery_longstreet_feast.jpg", "昂玛突节后全村沿街摆桌连成宴席，绵延数百米，象征族群团结与共享丰收。"),
        ("哈尼银饰盛装", "gallery_silver.jpg", "僾尼支系女子盛装：银泡头巾、银牌垂帘与彩色流苏，是哈尼服饰文化的华彩篇章。"),
        ("哈尼刺绣花带", "gallery_bands.jpg", "哈尼刺绣经典纹样：回纹、三角纹与菱形纹交织，绣于衣襟、背包与头巾之上。"),
    )
    rows = []
    for title, name, description in candidates:
        if len(rows) >= DEMO_GALLERY_LIMIT:
            break
        if os.path.isfile(os.path.join(images_dir, name)):
            rows.append((title, "images/" + name, description))
    return tuple(rows)


# ------------------------------------------------------------ 基础工具函数 ----

def get_connection(db_path=DB_PATH):
    """打开数据库连接（所有脚本统一走这里，保证外键约束生效）。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password, iterations=260000):
    """PBKDF2-HMAC-SHA256 密码哈希，不依赖第三方库。"""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return "pbkdf2_sha256${}${}${}".format(iterations, salt, digest.hex())


def verify_password(password, stored_hash):
    """校验密码是否匹配 stored_hash。"""
    try:
        _, iterations, salt, expected = stored_hash.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
        return secrets.compare_digest(digest.hex(), expected)
    except (ValueError, AttributeError):
        return False


def _table_columns(conn, table):
    return [row[1] for row in conn.execute("PRAGMA table_info({})".format(table)).fetchall()]


# ---------------------------------------------------------------- 初始化 ----

def init_db(db_path=DB_PATH, quiet=False, reset=False):
    def log(message):
        if not quiet:
            print(message)

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = get_connection(db_path)

    try:
        if reset:
            log("[--reset] 正在清空 users / vocabulary / gallery 三张表 ...")
            for table in ("gallery", "vocabulary", "users"):
                conn.execute("DROP TABLE IF EXISTS {}".format(table))

        # 0. 清理已废弃的瑶族旧表（项目词汇数据已转向哈尼族）
        if _table_columns(conn, "vocabulary_legacy"):
            conn.execute("DROP TABLE IF EXISTS vocabulary_legacy")
            log("已清理废弃的 vocabulary_legacy 旧表")

        # 1. 建表 + 索引（IF NOT EXISTS，幂等）
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)

        # 2. 种子数据：默认管理员
        existing_admin = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if existing_admin is None:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
                ("admin", hash_password("admin123")),
            )
            log("已创建默认管理员：admin / admin123（请登录后尽快修改密码）")
        else:
            log("默认管理员已存在，跳过")

        # 3. 种子数据：图集演示数据
        if conn.execute("SELECT COUNT(*) FROM gallery").fetchone()[0] == 0:
            admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
            for title, image_url, description in _demo_gallery_rows():
                conn.execute(
                    "INSERT INTO gallery (title, image_url, description, uploader_id) VALUES (?, ?, ?, ?)",
                    (title, image_url, description, admin_id),
                )
            log("已写入图集演示数据 {} 条".format(len(_demo_gallery_rows())))

        conn.commit()

        # 4. 汇总
        stats = {
            table: conn.execute("SELECT COUNT(*) FROM {}".format(table)).fetchone()[0]
            for table in ("users", "vocabulary", "gallery")
        }
        log("数据库就绪：{}".format(db_path))
        log("  users={users}  vocabulary={vocabulary}  gallery={gallery}".format(**stats))
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="“向世界介绍云南少数民族”数据库初始化")
    parser.add_argument("--db", default=DB_PATH, help="数据库文件路径（默认：backend/ich_data.db）")
    parser.add_argument("--quiet", action="store_true", help="安静模式，减少输出")
    parser.add_argument("--reset", action="store_true", help="清空三张业务表后重建")
    args = parser.parse_args()
    init_db(db_path=args.db, quiet=args.quiet, reset=args.reset)


if __name__ == "__main__":
    main()
