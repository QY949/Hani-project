#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
show_db.py —— 数据库概览
========================

打印 users / vocabulary / gallery 三张表的记录数、
民族与分类分布，以及若干条样例数据，方便快速确认爬虫和初始化效果。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from init_db import DB_PATH, get_connection  # noqa: E402


def main(db_path=DB_PATH):
    conn = get_connection(db_path)
    print("数据库文件：{}\n".format(db_path))

    # ---- users ----
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print("【users 用户表】共 {} 条".format(count))
    for row in conn.execute("SELECT id, username, role, created_at FROM users LIMIT 10"):
        print("   #{} {:<12} [{}] {}".format(row[0], row[1], row[2], row[3]))
    print()

    # ---- vocabulary ----
    count = conn.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0]
    print("【vocabulary 词汇表】共 {} 条".format(count))
    for row in conn.execute(
        "SELECT ethnic_group, COUNT(*) AS c FROM vocabulary GROUP BY ethnic_group ORDER BY c DESC"
    ):
        print("   民族 [{}]：{} 条".format(row[0], row[1]))
    for row in conn.execute(
        "SELECT category, COUNT(*) AS c FROM vocabulary GROUP BY category ORDER BY c DESC"
    ):
        print("   分类 [{}]：{} 条".format(row[0], row[1]))
    for row in conn.execute(
        "SELECT ethnic_group, word, meaning, category FROM vocabulary LIMIT 5"
    ):
        print("   样例：[{}] {} -> {}（{}）".format(row[0], row[2], row[1], row[3]))
    print()

    # ---- gallery ----
    count = conn.execute("SELECT COUNT(*) FROM gallery").fetchone()[0]
    print("【gallery 图集表】共 {} 条".format(count))
    for row in conn.execute(
        "SELECT g.id, g.title, g.image_url, u.username FROM gallery g"
        " LEFT JOIN users u ON u.id = g.uploader_id LIMIT 10"
    ):
        print("   #{} {}（{}）上传者：{}".format(row[0], row[1], row[2], row[3] or "无"))

    conn.close()


if __name__ == "__main__":
    main()
