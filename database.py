import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List

from config import DB_NAME

DB_PATH = DB_NAME


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _connect():
    return aiosqlite.connect(DB_PATH)


async def _add_column_if_missing(db, table: str, column: str, ddl: str):
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        cols = [row[1] for row in await cur.fetchall()]
    if column not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


async def init_db():
    async with _connect() as db:
        await db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TEXT,
    updated_at TEXT
)
""")

        await _add_column_if_missing(db, "users", "fake_deals", "fake_deals INTEGER DEFAULT 0")
        await _add_column_if_missing(db, "users", "fake_disputes", "fake_disputes INTEGER DEFAULT 0")
        await _add_column_if_missing(db, "users", "fake_reviews", "fake_reviews INTEGER DEFAULT 0")
        await _add_column_if_missing(db, "users", "fake_rating", "fake_rating REAL DEFAULT 5.0")

        # 🟥 BAN TABLE
        await db.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                reason TEXT,
                banned_by INTEGER,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS public_statuses (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                reason TEXT,
                added_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                reason TEXT NOT NULL,
                photos TEXT,
                reported_by INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_by INTEGER,
                created_at TEXT NOT NULL,
                reviewed_at TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buyer_id INTEGER NOT NULL,
                buyer_username TEXT,
                seller_id INTEGER NOT NULL,
                seller_username TEXT,
                amount TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                duration_hours INTEGER DEFAULT 24,
                expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await _add_column_if_missing(db, "deals", "duration_hours", "duration_hours INTEGER DEFAULT 24")
        await _add_column_if_missing(db, "deals", "expires_at", "expires_at TEXT")
        await _add_column_if_missing(db, "deals", "guarantor_id", "guarantor_id INTEGER")
        await _add_column_if_missing(db, "deals", "guarantor_username", "guarantor_username TEXT")
        await _add_column_if_missing(db, "deals", "guarantor_confirmed", "guarantor_confirmed INTEGER DEFAULT 0")
        await _add_column_if_missing(db, "deals", "buyer_proof", "buyer_proof INTEGER DEFAULT 0")
        await _add_column_if_missing(db, "deals", "seller_proof", "seller_proof INTEGER DEFAULT 0")
        await _add_column_if_missing(db, "deals", "guarantor_details", "guarantor_details TEXT")
        await _add_column_if_missing(db, "deals", "seller_details", "seller_details TEXT")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS deal_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id INTEGER NOT NULL,
                reviewer_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(deal_id, reviewer_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS deal_completion_confirmations (
                deal_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(deal_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS deal_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                sender_username TEXT,
                message_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS deal_proofs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                proof_type TEXT NOT NULL,
                file_id TEXT,
                proof_text TEXT,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS role_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS manual_trust (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT,
                actor_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        for sql in [
            "CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)",
            "CREATE INDEX IF NOT EXISTS idx_public_statuses_role ON public_statuses(role)",
            "CREATE INDEX IF NOT EXISTS idx_staff_role ON staff(role)",
            "CREATE INDEX IF NOT EXISTS idx_deals_buyer ON deals(buyer_id)",
            "CREATE INDEX IF NOT EXISTS idx_deals_seller ON deals(seller_id)",
            "CREATE INDEX IF NOT EXISTS idx_deals_guarantor ON deals(guarantor_id)",
            "CREATE INDEX IF NOT EXISTS idx_reviews_target ON deal_reviews(target_id)",
            "CREATE INDEX IF NOT EXISTS idx_role_history_username ON role_history(username)",
        ]:
            await db.execute(sql)

        await db.commit()


async def add_user(user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]):
    username = (username or "").lower()
    ts = now_iso()
    async with _connect() as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                updated_at = excluded.updated_at
        """, (user_id, username, first_name, last_name, ts, ts))
        await db.commit()


async def get_all_users() -> List[int]:
    async with _connect() as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def get_user_by_username(username: str):
    username = username.strip().lstrip("@").lower()
    async with _connect() as db:
        async with db.execute("SELECT user_id, username, first_name, last_name FROM users WHERE lower(username) = ?", (username,)) as cursor:
            return await cursor.fetchone()


async def add_staff(user_id: int, username: Optional[str], role: str):
    username = (username or "").lower()
    ts = now_iso()
    async with _connect() as db:
        await db.execute("""
            INSERT INTO staff (user_id, username, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = CASE WHEN excluded.username != '' THEN excluded.username ELSE staff.username END,
                role = excluded.role,
                updated_at = excluded.updated_at
        """, (user_id, username, role, ts, ts))
        await db.commit()


async def get_staff_role(user_id: int) -> Optional[str]:
    async with _connect() as db:
        async with db.execute("SELECT role FROM staff WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def get_staff_by_username(username: str):
    username = username.strip().lstrip("@").lower()
    async with _connect() as db:
        async with db.execute("SELECT user_id, role FROM staff WHERE lower(username) = ?", (username,)) as cursor:
            return await cursor.fetchone()


async def get_staff_list():
    async with _connect() as db:
        async with db.execute("""
            SELECT user_id, username, role FROM staff
            ORDER BY CASE role WHEN 'owner' THEN 1 WHEN 'admin' THEN 2 WHEN 'moderator' THEN 3 WHEN 'helper' THEN 4 ELSE 5 END, username
        """) as cursor:
            return await cursor.fetchall()


async def get_staff_by_role(role: str):
    async with _connect() as db:
        async with db.execute("SELECT user_id, username FROM staff WHERE role = ? ORDER BY username, user_id", (role,)) as cursor:
            return await cursor.fetchall()


async def remove_staff(user_id: int):
    async with _connect() as db:
        await db.execute("DELETE FROM staff WHERE user_id = ?", (user_id,))
        await db.commit()


async def set_public_status(username: str, role: str, reason: Optional[str] = None, added_by: Optional[int] = None):
    username = username.strip().lstrip("@").lower()
    ts = now_iso()
    async with _connect() as db:
        await db.execute("""
            INSERT INTO public_statuses (username, role, reason, added_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                role = excluded.role,
                reason = COALESCE(excluded.reason, public_statuses.reason),
                added_by = excluded.added_by,
                updated_at = excluded.updated_at
        """, (username, role, reason, added_by, ts, ts))
        await db.commit()


async def get_public_status(username: str) -> Optional[str]:
    username = username.strip().lstrip("@").lower()
    async with _connect() as db:
        async with db.execute("SELECT role FROM public_statuses WHERE username = ?", (username,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def delete_public_status(username: str):
    username = username.strip().lstrip("@").lower()
    async with _connect() as db:
        await db.execute("DELETE FROM public_statuses WHERE username = ?", (username,))
        await db.commit()


async def get_all_public_roles():
    async with _connect() as db:
        async with db.execute("SELECT username, role FROM public_statuses ORDER BY role, username") as cursor:
            return await cursor.fetchall()


async def get_public_by_role(role: str) -> List[str]:
    async with _connect() as db:
        async with db.execute("SELECT username FROM public_statuses WHERE role = ? ORDER BY username", (role,)) as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def get_all_user_roles(username: str) -> List[str]:
    username = username.strip().lstrip("@").lower()
    roles = []
    async with _connect() as db:
        async with db.execute("SELECT role FROM staff WHERE lower(username) = ?", (username,)) as cursor:
            row = await cursor.fetchone()
            if row:
                roles.append(row[0])
        async with db.execute("SELECT role FROM public_statuses WHERE username = ?", (username,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] not in roles:
                roles.append(row[0])
    priority = {"scammer": 0, "owner": 1, "admin": 2, "moderator": 3, "helper": 4, "guarantor": 5}
    return sorted(roles, key=lambda r: priority.get(r, 99))


async def add_role_history(username: str, role: str, action: str, actor_id: int):
    username = username.strip().lstrip("@").lower()
    async with _connect() as db:
        await db.execute("INSERT INTO role_history (username, role, action, actor_id, created_at) VALUES (?, ?, ?, ?, ?)", (username, role, action, actor_id, now_iso()))
        await db.commit()


async def get_role_history(username: str, limit: int = 20):
    username = username.strip().lstrip("@").lower()
    async with _connect() as db:
        async with db.execute("""
            SELECT actor_id, role, action, created_at FROM role_history
            WHERE username = ? ORDER BY id DESC LIMIT ?
        """, (username, limit)) as cursor:
            return await cursor.fetchall()


async def add_report(username: str, reason: str, photos: Optional[str], reported_by: int) -> int:
    username = username.strip().lstrip("@").lower()
    async with _connect() as db:
        cursor = await db.execute("""
            INSERT INTO reports (username, reason, photos, reported_by, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (username, reason, photos, reported_by, now_iso()))
        await db.commit()
        return cursor.lastrowid


async def get_report_info(report_id: int):
    async with _connect() as db:
        async with db.execute("SELECT username, reason FROM reports WHERE id = ?", (report_id,)) as cursor:
            return await cursor.fetchone()


async def get_pending_reports():
    async with _connect() as db:
        async with db.execute("""
            SELECT id, username, reason, photos, reported_by, created_at FROM reports
            WHERE status = 'pending' ORDER BY created_at ASC, id ASC
        """) as cursor:
            return await cursor.fetchall()


async def approve_report(report_id: int, reviewed_by: int) -> bool:
    ts = now_iso()
    async with _connect() as db:
        async with db.execute("SELECT username, reason FROM reports WHERE id = ? AND status = 'pending'", (report_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False
        username, reason = row
        cur = await db.execute("UPDATE reports SET status = 'approved', reviewed_by = ?, reviewed_at = ? WHERE id = ? AND status = 'pending'", (reviewed_by, ts, report_id))
        if cur.rowcount == 0:
            return False
        await db.execute("""
            INSERT INTO public_statuses (username, role, reason, added_by, created_at, updated_at)
            VALUES (?, 'scammer', ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET role = 'scammer', reason = excluded.reason, added_by = excluded.added_by, updated_at = excluded.updated_at
        """, (username, reason, reviewed_by, ts, ts))
        await db.commit()
        return True


async def reject_report(report_id: int, reviewed_by: int) -> bool:
    async with _connect() as db:
        cur = await db.execute("UPDATE reports SET status = 'rejected', reviewed_by = ?, reviewed_at = ? WHERE id = ? AND status = 'pending'", (reviewed_by, now_iso(), report_id))
        await db.commit()
        return cur.rowcount > 0


async def get_moderator_stats():
    async with _connect() as db:
        async with db.execute("""
            SELECT s.user_id, s.username,
                   SUM(CASE WHEN r.status = 'approved' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN r.status = 'rejected' THEN 1 ELSE 0 END),
                   COUNT(r.id)
            FROM reports r LEFT JOIN staff s ON s.user_id = r.reviewed_by
            WHERE r.status IN ('approved', 'rejected') GROUP BY r.reviewed_by ORDER BY COUNT(r.id) DESC
        """) as cursor:
            return await cursor.fetchall()


async def transfer_ownership(old_owner_id: int, new_owner_id: int):
    ts = now_iso()
    async with _connect() as db:
        await db.execute("UPDATE staff SET role = 'admin', updated_at = ? WHERE user_id = ? AND role = 'owner'", (ts, old_owner_id))
        await db.execute("""
            INSERT INTO staff (user_id, username, role, created_at, updated_at)
            VALUES (?, '', 'owner', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET role = 'owner', updated_at = excluded.updated_at
        """, (new_owner_id, ts, ts))
        await db.commit()


# ИСПРАВЛЕНА ФУНКЦИЯ create_deal (статус 'pending')
async def create_deal(buyer_id: int, buyer_username: str, seller_id: int, seller_username: str, amount: str, description: str, duration_hours: int = 24, guarantor_id: int = None) -> int:
    ts = now_iso()
    expire_ts = (datetime.utcnow() + timedelta(hours=duration_hours)).isoformat(timespec="seconds")
    async with _connect() as db:
        cur = await db.execute("""
            INSERT INTO deals (buyer_id, buyer_username, seller_id, seller_username, amount, description, status, duration_hours, expires_at, created_at, updated_at, guarantor_id)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        """, (buyer_id, (buyer_username or '').lower(), seller_id, (seller_username or '').lower(), amount, description, duration_hours, expire_ts, ts, ts, guarantor_id))
        await db.commit()
        return cur.lastrowid


async def get_deal(deal_id: int):
    async with _connect() as db:
        async with db.execute("""
            SELECT id, buyer_id, buyer_username, seller_id, seller_username,
                   amount, description, status, created_at, updated_at,
                   guarantor_id, guarantor_username, guarantor_confirmed, buyer_proof, seller_proof,
                   duration_hours, expires_at, guarantor_details, seller_details
            FROM deals WHERE id = ?
        """, (deal_id,)) as cursor:
            return await cursor.fetchone()


async def get_user_deals(user_id: int):
    async with _connect() as db:
        async with db.execute("""
            SELECT id, buyer_id, buyer_username, seller_id, seller_username,
                   amount, description, status, created_at, updated_at,
                   guarantor_id, guarantor_username, guarantor_confirmed, buyer_proof, seller_proof,
                   duration_hours, expires_at, guarantor_details, seller_details
            FROM deals WHERE buyer_id = ? OR seller_id = ? OR guarantor_id = ?
            ORDER BY id DESC LIMIT 30
        """, (user_id, user_id, user_id)) as cursor:
            return await cursor.fetchall()


async def accept_deal(deal_id: int, seller_id: int) -> bool:
    async with _connect() as db:
        cur = await db.execute("""
            UPDATE deals SET status = 'guarantor_selection', updated_at = ?
            WHERE id = ? AND seller_id = ? AND status = 'created'
        """, (now_iso(), deal_id, seller_id))
        await db.commit()
        return cur.rowcount > 0


async def reject_deal(deal_id: int, seller_id: int) -> bool:
    async with _connect() as db:
        cur = await db.execute("UPDATE deals SET status = 'rejected', updated_at = ? WHERE id = ? AND seller_id = ? AND status = 'created'", (now_iso(), deal_id, seller_id))
        await db.commit()
        return cur.rowcount > 0


async def can_be_guarantor(username: str):
    username = username.strip().lstrip("@").lower()
    public = await get_public_status(username)
    if public == "scammer":
        return False, None
    user = await get_user_by_username(username)
    if not user:
        return False, None
    staff = await get_staff_by_username(username)
    if staff and staff[1] in ("owner", "admin", "moderator", "helper"):
        return True, {"user_id": user[0], "username": username}
    if public == "guarantor":
        return True, {"user_id": user[0], "username": username}
    return False, None


async def propose_guarantor(deal_id: int, guarantor_id: int, guarantor_username: str) -> bool:
    async with _connect() as db:
        cur = await db.execute("""
            UPDATE deals SET guarantor_id = ?, guarantor_username = ?, guarantor_confirmed = 0,
                status = 'guarantor_pending_seller', updated_at = ?
            WHERE id = ? AND status = 'guarantor_selection'
        """, (guarantor_id, guarantor_username.lower(), now_iso(), deal_id))
        await db.commit()
        return cur.rowcount > 0


async def reset_guarantor_selection(deal_id: int) -> bool:
    async with _connect() as db:
        cur = await db.execute("""
            UPDATE deals SET guarantor_id = NULL, guarantor_username = NULL, guarantor_confirmed = 0,
                status = 'guarantor_selection', updated_at = ? WHERE id = ?
        """, (now_iso(), deal_id))
        await db.commit()
        return cur.rowcount > 0


async def seller_confirm_guarantor(deal_id: int) -> bool:
    async with _connect() as db:
        cur = await db.execute("UPDATE deals SET status = 'guarantor_pending_guarantor', updated_at = ? WHERE id = ? AND status = 'guarantor_pending_seller'", (now_iso(), deal_id))
        await db.commit()
        return cur.rowcount > 0


async def guarantor_accept_deal(deal_id: int, guarantor_id: int) -> bool:
    async with _connect() as db:
        cur = await db.execute("""
            UPDATE deals SET guarantor_confirmed = 1, status = 'active', updated_at = ?
            WHERE id = ? AND guarantor_id = ? AND status = 'guarantor_pending_guarantor'
        """, (now_iso(), deal_id, guarantor_id))
        await db.commit()
        return cur.rowcount > 0


async def set_guarantor_details(deal_id: int, details: str):
    async with _connect() as db:
        await db.execute("UPDATE deals SET guarantor_details = ? WHERE id = ?", (details, deal_id))
        await db.commit()


async def set_seller_details(deal_id: int, details: str):
    async with _connect() as db:
        await db.execute("UPDATE deals SET seller_details = ? WHERE id = ?", (details, deal_id))
        await db.commit()


async def open_deal_dispute(deal_id: int, user_id: int) -> bool:
    async with _connect() as db:
        cur = await db.execute("""
            UPDATE deals SET status = 'disputed', updated_at = ?
            WHERE id = ? AND (buyer_id = ? OR seller_id = ? OR guarantor_id = ?) AND status = 'active'
        """, (now_iso(), deal_id, user_id, user_id, user_id))
        if cur.rowcount > 0:
            await db.execute("UPDATE users SET fake_disputes = fake_disputes + 1 WHERE user_id IN (SELECT buyer_id FROM deals WHERE id = ? UNION SELECT seller_id FROM deals WHERE id = ?)", (deal_id, deal_id))
            await db.commit()
            return True
        return False


async def add_deal_message(deal_id: int, sender_id: int, sender_username: str, message_text: str):
    async with _connect() as db:
        await db.execute("INSERT INTO deal_messages (deal_id, sender_id, sender_username, message_text, created_at) VALUES (?, ?, ?, ?, ?)", (deal_id, sender_id, (sender_username or '').lower(), message_text, now_iso()))
        await db.commit()


async def get_deal_messages(deal_id: int, limit: int = 50):
    async with _connect() as db:
        async with db.execute("SELECT sender_id, sender_username, message_text, created_at FROM deal_messages WHERE deal_id = ? ORDER BY id DESC LIMIT ?", (deal_id, limit)) as cursor:
            return await cursor.fetchall()


async def add_deal_proof(deal_id: int, user_id: int, proof_type: str, file_id: Optional[str], proof_text: Optional[str]):
    deal = await get_deal(deal_id)
    if not deal:
        return False
    if user_id == deal[1]:
        username = deal[2] or ""
        proof_col = "buyer_proof"
    elif user_id == deal[3]:
        username = deal[4] or ""
        proof_col = "seller_proof"
    else:
        return False
    async with _connect() as db:
        await db.execute("""
            INSERT INTO deal_proofs (deal_id, user_id, username, proof_type, file_id, proof_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (deal_id, user_id, username.lower(), proof_type, file_id, proof_text, now_iso()))
        await db.execute(f"UPDATE deals SET {proof_col} = 1, updated_at = ? WHERE id = ?", (now_iso(), deal_id))
        await db.commit()
        return True


async def get_deal_proofs(deal_id: int):
    async with _connect() as db:
        async with db.execute("""
            SELECT id, user_id, username, proof_type, file_id, proof_text, created_at
            FROM deal_proofs WHERE deal_id = ? ORDER BY id ASC
        """, (deal_id,)) as cursor:
            return await cursor.fetchall()


async def guarantor_complete_deal(deal_id: int, guarantor_id: int) -> str:
    async with _connect() as db:
        async with db.execute("SELECT status, guarantor_id, buyer_id, seller_id, buyer_proof, seller_proof FROM deals WHERE id = ?", (deal_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return "not_allowed"
        status, gid, buyer_id, seller_id, buyer_proof, seller_proof = row
        if gid != guarantor_id or status not in ("active", "disputed"):
            return "not_allowed"
        if not buyer_proof or not seller_proof:
            return "no_proofs"
        
        await db.execute("UPDATE deals SET status = 'completed', updated_at = ? WHERE id = ?", (now_iso(), deal_id))
        await db.execute("UPDATE users SET fake_deals = fake_deals + 1 WHERE user_id IN (?, ?)", (buyer_id, seller_id))
        
        await db.commit()
        return "completed"


async def complete_deal_side(deal_id: int, user_id: int) -> str:
    return "not_allowed"


async def add_deal_review(deal_id: int, reviewer_id: int, rating: int, text: str) -> str:
    async with _connect() as db:
        async with db.execute("SELECT buyer_id, seller_id, status FROM deals WHERE id = ?", (deal_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return "not_allowed"
        buyer_id, seller_id, status = row
        if status != "completed" or reviewer_id not in (buyer_id, seller_id):
            return "not_allowed"
        target_id = seller_id if reviewer_id == buyer_id else buyer_id
        try:
            await db.execute("INSERT INTO deal_reviews (deal_id, reviewer_id, target_id, rating, text, created_at) VALUES (?, ?, ?, ?, ?, ?)", 
                             (deal_id, reviewer_id, target_id, rating, text, now_iso()))
            await db.execute("UPDATE users SET fake_reviews = fake_reviews + 1 WHERE user_id = ?", (target_id,))
            await db.commit()
            return "ok"
        except Exception:
            return "duplicate"


async def get_manual_trust(username: str) -> int:
    username = username.strip().lstrip("@").lower()
    async with _connect() as db:
        async with db.execute("SELECT COALESCE(SUM(amount), 0) FROM manual_trust WHERE username = ?", (username,)) as cursor:
            return (await cursor.fetchone())[0]


def _age_text(created_at: Optional[str]) -> str:
    if not created_at:
        return "нет данных"
    try:
        created = datetime.fromisoformat(created_at)
    except Exception:
        return "нет данных"
    days = max((datetime.utcnow() - created).days, 0)
    if days < 1:
        return "сегодня"
    if days < 30:
        return f"{days} дн."
    months = days // 30
    if months < 12:
        return f"{months} мес."
    years = months // 12
    rest = months % 12
    return f"{years} г. {rest} мес." if rest else f"{years} г."


async def get_trust_profile(username: str):
    username = username.strip().lstrip("@").lower()
    user = await get_user_by_username(username)
    manual = await get_manual_trust(username)
    result = {
        "reputation": manual,
        "completed_deals": 0,
        "positive_reviews": 0,
        "negative_reviews": 0,
        "reviews_total": 0,
        "disputes": 0,
        "age_text": "нет данных",
        "manual_trust": manual,
        "trust_score": manual,
    }
    if not user:
        return result
    user_id = user[0]
    async with _connect() as db:
        async with db.execute("SELECT created_at FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            created_at = row[0] if row else None
        async with db.execute("SELECT COUNT(*) FROM deals WHERE status = 'completed' AND (buyer_id = ? OR seller_id = ? OR guarantor_id = ?)", (user_id, user_id, user_id)) as cursor:
            completed = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM deals WHERE status = 'disputed' AND (buyer_id = ? OR seller_id = ? OR guarantor_id = ?)", (user_id, user_id, user_id)) as cursor:
            disputes = (await cursor.fetchone())[0]
        async with db.execute("SELECT rating FROM deal_reviews WHERE target_id = ?", (user_id,)) as cursor:
            ratings = [r[0] for r in await cursor.fetchall()]
    positive = sum(1 for r in ratings if r >= 4)
    negative = sum(1 for r in ratings if r <= 2)
    neutral = sum(1 for r in ratings if r == 3)
    age_bonus = 0
    try:
        age_bonus = min((datetime.utcnow() - datetime.fromisoformat(created_at)).days // 30, 12) if created_at else 0
    except Exception:
        pass
    reputation = completed * 2 + positive * 3 + neutral - negative * 5 - disputes * 3 + manual
    result.update({
        "reputation": reputation,
        "completed_deals": completed,
        "positive_reviews": positive,
        "negative_reviews": negative,
        "reviews_total": len(ratings),
        "disputes": disputes,
        "age_text": _age_text(created_at),
        "manual_trust": manual,
        "trust_score": reputation + age_bonus,
    })
    return result


# Функции, используемые в bot.py
async def get_user_deals_list(user_id: int):
    deals = await get_user_deals(user_id)
    result = []
    for d in deals:
        # d: 0 id,1 buyer_id,2 buyer_username,3 seller_id,4 seller_username,5 amount,6 description,7 status,...
        status_text = {
            'pending': 'ожидает подтверждения продавца',
            'accepted_by_seller': 'принята продавцом, ожидает гаранта',
            'awaiting_guarantor_details': 'гарант вводит реквизиты',
            'active': 'активна (ожидает оплаты)',
            'paid': 'оплачена покупателем, проверка гаранта',
            'awaiting_seller_details': 'гарант запрашивает реквизиты продавца',
            'processing': 'продавец передаёт товар',
            'delivered': 'товар передан, ожидает подтверждения покупателя',
            'disputed': 'спор',
            'completed': 'завершена',
            'rejected_by_seller': 'отклонена продавцом',
            'rejected_by_guarantor': 'отклонена гарантом'
        }.get(d[7], d[7])
        result.append({
            "id": d[0],
            "buyer_id": d[1],
            "seller_id": d[3],
            "amount": d[5],
            "description": d[6],
            "status": d[7],
            "status_text": status_text,
        })
    return result


async def get_deal_by_id(deal_id: int):
    d = await get_deal(deal_id)
    if not d:
        return None
    return {
        "id": d[0],
        "buyer_id": d[1],
        "seller_id": d[3],
        "guarantor_id": d[10],
        "amount": d[5],
        "description": d[6],
        "status": d[7],
        "guarantor_details": d[18] if len(d) > 18 else None,
        "seller_details": d[19] if len(d) > 19 else None,
    }


async def update_deal_status(deal_id: int, status: str):
    async with _connect() as db:
        await db.execute(
            "UPDATE deals SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), deal_id)
        )
        await db.commit()
async def ban_user(user_id: int, username: str, reason: str, banned_by: int):
    async with _connect() as db:
        await db.execute("""
            INSERT OR REPLACE INTO banned_users (user_id, username, reason, banned_by)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, reason, banned_by))
        await db.commit()


async def is_banned(user_id: int) -> bool:
    async with _connect() as db:
        cur = await db.execute("""
            SELECT 1 FROM banned_users WHERE user_id = ?
        """, (user_id,))
        return await cur.fetchone() is not None

async def unban_user(user_id: int):
    async with _connect() as db:
        await db.execute("""
            DELETE FROM banned_users WHERE user_id = ?
        """, (user_id,))
        await db.commit()
