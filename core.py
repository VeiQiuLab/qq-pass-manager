"""Offline admission records. All public record operations require an explicit group."""
from __future__ import annotations

import csv
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"
# Disjoint first-character pools guarantee that a code can never belong to both groups.
FIRST = {"A": "2345679ACDEFGH", "B": "JKLMNPQRTUVWXY"}
ALPHABET = FIRST["A"] + FIRST["B"]
STATES = {"pending": "待核验", "verified": "已核验·未核销", "used": "已核销",
          "revoked": "已撤销", "expired": "已过期"}
TTL = 24 * 60 * 60


class RuleError(ValueError):
    pass


def group_id(group):
    if group not in FIRST:
        raise RuleError("必须明确选择 A 群或 B 群。")
    return group


def qq_number(value):
    value = str(value).strip()
    if not re.fullmatch(r"[1-9][0-9]{4,11}", value):
        raise RuleError("QQ 号须为 5–12 位数字，且不能以 0 开头。")
    return value


def token_text(value):
    value = str(value).strip().upper()
    if len(value) != 8 or any(c not in ALPHABET for c in value):
        raise RuleError("口令格式错误：请输入 8 位口令（不区分大小写）。")
    return value


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z") if value is not None else ""


def state(row, now):
    if row["state"] != "active":
        return row["state"]
    if now >= row["expires_at"]:
        return "expired"
    return "verified" if row["verified_at"] is not None else "pending"


def csv_safe(value):
    text = str(value) if value is not None else ""
    # Quoting alone does not prevent spreadsheet formula execution.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")) else text


class Store:
    def __init__(self, directory, clock=time.time):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        for group in FIRST:
            with self._db(group) as db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS applicants (
                        id INTEGER PRIMARY KEY, qq TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '');
                    CREATE TABLE IF NOT EXISTS codes (
                        id INTEGER PRIMARY KEY, applicant_id INTEGER NOT NULL REFERENCES applicants(id),
                        token TEXT NOT NULL UNIQUE, issued_at INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'active'
                            CHECK(state IN ('active','used','revoked')),
                        verified_at INTEGER, used_at INTEGER, revoked_at INTEGER);
                    CREATE UNIQUE INDEX IF NOT EXISTS one_active ON codes(applicant_id) WHERE state='active';
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY, code_id INTEGER NOT NULL REFERENCES codes(id),
                        kind TEXT NOT NULL, at INTEGER NOT NULL);
                """)
                old = db.execute("SELECT value FROM meta WHERE key='group'").fetchone()
                if old is not None and old[0] != group:
                    raise RuleError("数据库群标识不符，已停止加载；请勿交换 A/B 数据库文件。")
                db.execute("INSERT OR IGNORE INTO meta VALUES ('group', ?)", (group,))
                version = db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
                if version is not None and version[0] != '1':
                    raise RuleError("数据库版本不兼容，已停止加载。")
                db.execute("INSERT OR IGNORE INTO meta VALUES ('schema','1')")

    @contextmanager
    def _db(self, group, write=False):
        group_id(group)
        db = sqlite3.connect(self.directory / f"group_{group}.sqlite3", timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _now(self, db):
        now = int(self.clock())
        previous = db.execute("SELECT value FROM meta WHERE key='last_write_time'").fetchone()
        if previous is not None and now < int(previous[0]):
            raise RuleError("系统时间早于上次操作，已拒绝写入；请校准电脑时间。")
        db.execute("INSERT OR REPLACE INTO meta VALUES ('last_write_time', ?)", (str(now),))
        return now

    def issue(self, group, qq, name, notes="", *, reissue=False):
        group_id(group)
        qq = qq_number(qq)
        name, notes = str(name).strip(), str(notes).strip()
        if not name or len(name) > 100 or len(notes) > 2000:
            raise RuleError("申请人姓名必填（最多 100 字），备注最多 2000 字。")
        with self._db(group, True) as db:
            now = self._now(db)
            person = db.execute("SELECT * FROM applicants WHERE qq=?", (qq,)).fetchone()
            if person:
                if not reissue:
                    raise RuleError("本群已有该 QQ 号；请选择其记录，按需撤销并重新发放。")
                if db.execute("SELECT 1 FROM codes WHERE applicant_id=? AND state='used'", (person['id'],)).fetchone():
                    raise RuleError("该申请者已有核销记录，不能再次发放。")
                active = db.execute("SELECT id FROM codes WHERE applicant_id=? AND state='active'", (person['id'],)).fetchall()
                for row in active:
                    db.execute("UPDATE codes SET state='revoked',revoked_at=? WHERE id=?", (now, row['id']))
                    db.execute("INSERT INTO events(code_id,kind,at) VALUES (?,'replaced',?)", (row['id'], now))
                db.execute("UPDATE applicants SET name=?,notes=? WHERE id=?", (name, notes, person['id']))
                pid = person['id']
            else:
                if reissue:
                    raise RuleError("该 QQ 号在本群不存在，不能重发。")
                pid = db.execute("INSERT INTO applicants(qq,name,notes) VALUES (?,?,?)", (qq, name, notes)).lastrowid
            for _ in range(100):
                token = secrets.choice(FIRST[group]) + ''.join(secrets.choice(ALPHABET) for _ in range(7))
                if not db.execute("SELECT 1 FROM codes WHERE token=?", (token,)).fetchone():
                    break
            else:
                raise RuleError("随机口令连续冲突，请重试。")
            cid = db.execute("INSERT INTO codes(applicant_id,token,issued_at,expires_at) VALUES (?,?,?,?)", (pid, token, now, now + TTL)).lastrowid
            db.execute("INSERT INTO events(code_id,kind,at) VALUES (?,'issued',?)", (cid, now))
        return self.get(group, cid)

    @staticmethod
    def _query():
        return "SELECT c.*, a.qq, a.name, a.notes FROM codes c JOIN applicants a ON c.applicant_id=a.id"

    def get(self, group, code_id):
        with self._db(group) as db:
            row = db.execute(self._query() + " WHERE c.id=?", (code_id,)).fetchone()
        if row is None:
            raise RuleError("当前群没有此记录。")
        result = dict(row)
        result.update(group=group, status=state(row, int(self.clock())))
        return result

    def list_records(self, group, search="", status="all"):
        if status not in {"all", *STATES}:
            raise RuleError("状态筛选无效。")
        with self._db(group) as db:
            rows = db.execute(self._query() + " ORDER BY c.id DESC").fetchall()
        now, needle = int(self.clock()), search.strip().casefold()
        result = []
        for row in rows:
            s = state(row, now)
            if status != "all" and s != status:
                continue
            if needle and not any(needle in str(row[k]).casefold() for k in ('qq','name','notes','token')):
                continue
            result.append(dict(row, group=group, status=s))
        return result

    def _validate(self, db, qq, token, now):
        row = db.execute(self._query() + " WHERE a.qq=? AND c.token=?", (qq, token)).fetchone()
        if row is None:
            raise RuleError("核验失败：当前群中 QQ 号与口令不匹配（跨群口令不接受）。")
        s = state(row, now)
        if s not in ('pending','verified'):
            raise RuleError("操作拒绝：此口令" + STATES[s] + "。")
        return row

    def verify(self, group, qq, token):
        qq, token = qq_number(qq), token_text(token)
        with self._db(group, True) as db:
            now = self._now(db)
            row = self._validate(db, qq, token, now)
            db.execute("UPDATE codes SET verified_at=? WHERE id=?", (now, row['id']))
            db.execute("INSERT INTO events(code_id,kind,at) VALUES (?,'verified',?)", (row['id'], now))
        return self.get(group, row['id'])

    def consume(self, group, qq, token, *, manual_approved=False):
        if manual_approved is not True:
            raise RuleError("请先在 QQ 客户端人工核对并批准入群，再确认核销。")
        qq, token = qq_number(qq), token_text(token)
        with self._db(group, True) as db:
            now = self._now(db)
            row = self._validate(db, qq, token, now)
            if row['verified_at'] is None:
                raise RuleError("请先核验口令，再进行人工批准后的核销。")
            changed = db.execute("UPDATE codes SET state='used',used_at=? WHERE id=? AND state='active' AND expires_at>?", (now, row['id'], now)).rowcount
            if changed != 1:
                raise RuleError("口令状态已改变，核销失败。")
            db.execute("INSERT INTO events(code_id,kind,at) VALUES (?,'used',?)", (row['id'], now))
        return self.get(group, row['id'])

    def revoke(self, group, code_id):
        with self._db(group, True) as db:
            now = self._now(db)
            row = db.execute("SELECT * FROM codes WHERE id=?", (code_id,)).fetchone()
            if row is None or row['state'] != 'active':
                raise RuleError("当前群记录不存在，或已核销/撤销，无法撤销。")
            db.execute("UPDATE codes SET state='revoked', revoked_at=? WHERE id=?", (now, code_id))
            db.execute("INSERT INTO events(code_id,kind,at) VALUES (?,'revoked',?)", (code_id, now))

    def edit(self, group, code_id, name, notes):
        name, notes = name.strip(), notes.strip()
        if not name or len(name) > 100 or len(notes) > 2000:
            raise RuleError("申请人必填且最多 100 字，备注最多 2000 字。")
        with self._db(group, True) as db:
            self._now(db)
            row = db.execute("SELECT applicant_id FROM codes WHERE id=?", (code_id,)).fetchone()
            if row is None:
                raise RuleError("当前群没有此记录。")
            db.execute("UPDATE applicants SET name=?,notes=? WHERE id=?", (name, notes, row[0]))

    def export_csv(self, group, path, search="", status="all"):
        rows = self.list_records(group, search, status)
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['群组','记录ID','申请人','QQ号','口令','状态','发放时间','到期时间','最近核验','核销时间','撤销时间','备注'])
            for r in rows:
                writer.writerow([csv_safe(v) for v in [group + '群', r['id'], r['name'], r['qq'], r['token'], STATES[r['status']], *[timestamp(r[k]) for k in ('issued_at','expires_at','verified_at','used_at','revoked_at')], r['notes']]])
        return len(rows)


def default_directory():
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home())
    return base / 'QQPassManager' / 'data'
