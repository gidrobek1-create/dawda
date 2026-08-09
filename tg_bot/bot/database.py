import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        # min_size=1 bo'lsa, bot uxlab tirgach birinchi so'rov yangi ulanish ochishni kutadi —
        # bu ham "birinchi xabar sekin keladi" hissini kuchaytiradi. 3 ta tayyor ulanish ushlab turamiz.
        self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=3, max_size=10)
        logger.info("PostgreSQL bazasiga ulanildi")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def run_migrations(self) -> None:
        """Barcha migrations/*.sql fayllarni tartib bilan bajaradi.
        Oddiy 'run once' yondashuv: har bir fayl idempotent (CREATE TABLE IF NOT EXISTS)
        deb yoziladi, shu sabab qayta ishga tushirilsa ham xato bermaydi."""
        assert self.pool
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        async with self.pool.acquire() as conn:
            for f in files:
                sql = f.read_text(encoding="utf-8")
                logger.info("Migratsiya bajarilmoqda: %s", f.name)
                await conn.execute(sql)

    # ---------- users ----------

    async def upsert_user(self, user_id: int, username: str | None, full_name: str | None,
                           referrer_id: int | None = None) -> None:
        assert self.pool
        await self.pool.execute(
            """
            INSERT INTO users (id, username, full_name, referrer_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE
                SET username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name
            """,
            user_id, username, full_name, referrer_id,
        )

    async def get_user(self, user_id: int) -> asyncpg.Record | None:
        assert self.pool
        return await self.pool.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    async def set_language(self, user_id: int, language: str) -> None:
        assert self.pool
        await self.pool.execute(
            "UPDATE users SET language = $1, is_registered = TRUE WHERE id = $2",
            language, user_id,
        )

    async def set_active(self, user_id: int, active: bool) -> None:
        assert self.pool
        await self.pool.execute("UPDATE users SET active = $1 WHERE id = $2", active, user_id)

    # ---------- required_channels ----------

    async def get_required_channels(self) -> list[asyncpg.Record]:
        assert self.pool
        return await self.pool.fetch("SELECT * FROM required_channels ORDER BY id")

    async def add_required_channel(self, chat_id: str, title: str | None, invite_link: str | None) -> None:
        assert self.pool
        await self.pool.execute(
            "INSERT INTO required_channels (chat_id, title, invite_link) VALUES ($1, $2, $3)",
            chat_id, title, invite_link,
        )

    async def remove_required_channel(self, channel_id: int) -> None:
        assert self.pool
        await self.pool.execute("DELETE FROM required_channels WHERE id = $1", channel_id)

    # ---------- admins ----------

    async def get_admin_role(self, user_id: int) -> str | None:
        assert self.pool
        row = await self.pool.fetchrow("SELECT role FROM admins WHERE user_id = $1", user_id)
        return row["role"] if row else None

    async def ensure_super_admins(self, ids: list[int]) -> None:
        assert self.pool
        for uid in ids:
            await self.pool.execute(
                """
                INSERT INTO admins (user_id, role) VALUES ($1, 'super')
                ON CONFLICT (user_id) DO UPDATE SET role = 'super'
                """,
                uid,
            )

    async def add_admin(self, user_id: int, role: str) -> None:
        assert self.pool
        await self.pool.execute(
            """
            INSERT INTO admins (user_id, role) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET role = EXCLUDED.role
            """,
            user_id, role,
        )

    async def get_all_admin_ids(self) -> list[int]:
        assert self.pool
        rows = await self.pool.fetch("SELECT user_id FROM admins")
        return [r["user_id"] for r in rows]

    async def get_admins(self) -> list[asyncpg.Record]:
        assert self.pool
        return await self.pool.fetch("SELECT user_id, role FROM admins ORDER BY added_at")

    async def remove_admin(self, user_id: int) -> None:
        assert self.pool
        await self.pool.execute("DELETE FROM admins WHERE user_id = $1", user_id)

    async def get_admin_stats(self) -> dict:
        assert self.pool
        users_row = await self.pool.fetchrow(
            "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE active) AS active FROM users"
        )
        payments_row = await self.pool.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COALESCE(SUM(amount) FILTER (WHERE status = 'approved'), 0) AS total_topup
            FROM payments
            """
        )
        promo = await self.promo_stats()
        admins_count = await self.pool.fetchval("SELECT COUNT(*) FROM admins")
        return {
            "users_total": users_row["total"],
            "users_active": users_row["active"],
            "payments_pending": payments_row["pending"],
            "total_topup": payments_row["total_topup"],
            "promo_available": promo["available"],
            "promo_used": promo["used"],
            "admins_count": admins_count,
        }

    # ---------- settings ----------

    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        assert self.pool
        row = await self.pool.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        assert self.pool
        await self.pool.execute(
            """
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            key, value,
        )

    # ---------- balance / referral ----------

    async def add_balance(self, user_id: int, amount: int) -> None:
        assert self.pool
        await self.pool.execute("UPDATE users SET balance = balance + $1 WHERE id = $2", amount, user_id)

    async def apply_referral_bonus(self, referrer_id: int) -> None:
        """Yangi foydalanuvchi ro'yxatdan to'liq o'tganda (til tanlagach) chaqiriladi.
        1-darajali bonus qo'shadi va referral_count'ni oshiradi."""
        assert self.pool
        bonus_raw = await self.get_setting("referral_bonus_l1", "0")
        bonus = int(bonus_raw) if bonus_raw and bonus_raw.isdigit() else 0
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                referrer = await conn.fetchrow("SELECT id FROM users WHERE id = $1", referrer_id)
                if referrer is None:
                    return
                if bonus > 0:
                    await conn.execute("UPDATE users SET balance = balance + $1 WHERE id = $2", bonus, referrer_id)
                await conn.execute(
                    "UPDATE users SET referral_count = referral_count + 1 WHERE id = $1", referrer_id
                )

    async def get_referral_stats(self, user_id: int) -> dict:
        assert self.pool
        user = await self.get_user(user_id)
        bonus_raw = await self.get_setting("referral_bonus_l1", "0")
        bonus = int(bonus_raw) if bonus_raw and bonus_raw.isdigit() else 0
        count = user["referral_count"] if user else 0
        return {
            "count": count,
            "bonus_per_referral": bonus,
            "total_earned": count * bonus,
        }

    # ---------- payments ----------

    async def count_recent_payment_requests(self, user_id: int, minutes: int = 60) -> int:
        assert self.pool
        row = await self.pool.fetchrow(
            """
            SELECT COUNT(*) AS cnt FROM payments
            WHERE user_id = $1 AND created_at > now() - ($2 || ' minutes')::interval
            """,
            user_id, str(minutes),
        )
        return row["cnt"]

    async def create_payment(self, user_id: int, photo_file_id: str, amount: int) -> int:
        assert self.pool
        row = await self.pool.fetchrow(
            """
            INSERT INTO payments (user_id, photo_file_id, amount)
            VALUES ($1, $2, $3) RETURNING id
            """,
            user_id, photo_file_id, amount,
        )
        return row["id"]

    async def add_payment_notification(self, payment_id: int, admin_id: int, chat_id: int, message_id: int) -> None:
        assert self.pool
        await self.pool.execute(
            """
            INSERT INTO payment_notifications (payment_id, admin_id, chat_id, message_id)
            VALUES ($1, $2, $3, $4)
            """,
            payment_id, admin_id, chat_id, message_id,
        )

    async def get_payment_notifications(self, payment_id: int) -> list[asyncpg.Record]:
        assert self.pool
        return await self.pool.fetch(
            "SELECT * FROM payment_notifications WHERE payment_id = $1", payment_id
        )

    async def get_payment(self, payment_id: int) -> asyncpg.Record | None:
        assert self.pool
        return await self.pool.fetchrow("SELECT * FROM payments WHERE id = $1", payment_id)

    async def resolve_payment(self, payment_id: int, approve: bool, admin_id: int,
                               reason: str | None = None) -> bool:
        """Faqat 'pending' holatdagi to'lovni hal qiladi (poyga holatidan himoya).
        True qaytarsa — muvaffaqiyatli hal qilindi, False — allaqachon ko'rib chiqilgan."""
        assert self.pool
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                payment = await conn.fetchrow(
                    "SELECT * FROM payments WHERE id = $1 FOR UPDATE", payment_id
                )
                if payment is None or payment["status"] != "pending":
                    return False
                new_status = "approved" if approve else "rejected"
                await conn.execute(
                    """
                    UPDATE payments SET status = $1, reason = $2, reviewed_by = $3, reviewed_at = now()
                    WHERE id = $4
                    """,
                    new_status, reason, admin_id, payment_id,
                )
                if approve:
                    await conn.execute(
                        "UPDATE users SET balance = balance + $1 WHERE id = $2",
                        payment["amount"], payment["user_id"],
                    )
        return True

    async def get_purchase_history(self, user_id: int, limit: int = 10) -> dict:
        assert self.pool
        payments = await self.pool.fetch(
            """
            SELECT amount, created_at FROM payments
            WHERE user_id = $1 AND status = 'approved'
            ORDER BY created_at DESC LIMIT $2
            """,
            user_id, limit,
        )
        promos = await self.pool.fetch(
            """
            SELECT pc.code, pc.price_paid, pc.used_at, pp.name AS package_name
            FROM promo_codes pc
            LEFT JOIN promo_packages pp ON pp.id = pc.package_id
            WHERE pc.used_by = $1
            ORDER BY pc.used_at DESC LIMIT $2
            """,
            user_id, limit,
        )
        return {"payments": payments, "promos": promos}

    # ---------- promo paketlar ----------

    async def create_promo_package(self, name: str, price: int) -> int:
        assert self.pool
        max_order = await self.pool.fetchval("SELECT COALESCE(MAX(sort_order), -1) FROM promo_packages")
        row = await self.pool.fetchrow(
            "INSERT INTO promo_packages (name, price, sort_order) VALUES ($1, $2, $3) RETURNING id",
            name, price, max_order + 1,
        )
        return row["id"]

    async def get_promo_package(self, package_id: int) -> asyncpg.Record | None:
        assert self.pool
        return await self.pool.fetchrow("SELECT * FROM promo_packages WHERE id = $1", package_id)

    async def list_promo_packages(self, active_only: bool = False) -> list[asyncpg.Record]:
        assert self.pool
        query = "SELECT * FROM promo_packages"
        if active_only:
            query += " WHERE active = TRUE"
        query += " ORDER BY sort_order, id"
        return await self.pool.fetch(query)

    async def update_promo_package(self, package_id: int, *, name: str | None = None,
                                    price: int | None = None) -> None:
        assert self.pool
        if name is not None:
            await self.pool.execute("UPDATE promo_packages SET name = $1 WHERE id = $2", name, package_id)
        if price is not None:
            await self.pool.execute("UPDATE promo_packages SET price = $1 WHERE id = $2", price, package_id)

    async def set_promo_package_active(self, package_id: int, active: bool) -> None:
        assert self.pool
        await self.pool.execute("UPDATE promo_packages SET active = $1 WHERE id = $2", active, package_id)

    async def delete_promo_package(self, package_id: int) -> None:
        assert self.pool
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM promo_codes WHERE package_id = $1 AND status = 'available'", package_id)
                await conn.execute("UPDATE promo_codes SET package_id = NULL WHERE package_id = $1", package_id)
                await conn.execute("DELETE FROM promo_packages WHERE id = $1", package_id)

    async def promo_package_counts(self, package_id: int) -> dict:
        assert self.pool
        row = await self.pool.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'available' AND (expiry_at IS NULL OR expiry_at > now())) AS available,
                COUNT(*) FILTER (WHERE status = 'used') AS used
            FROM promo_codes WHERE package_id = $1
            """,
            package_id,
        )
        return {"available": row["available"], "used": row["used"]}

    async def list_promo_packages_with_counts(self, active_only: bool = False) -> list[dict]:
        """Har bir paketni mavjud/ishlatilgan kodlar soni bilan birga qaytaradi
        (masalan "42 lik — 1500 so'm (0 ta bor)" ko'rinishidagi menyu uchun)."""
        assert self.pool
        packages = await self.list_promo_packages(active_only=active_only)
        result = []
        for pkg in packages:
            counts = await self.promo_package_counts(pkg["id"])
            result.append({**dict(pkg), **counts})
        return result

    # ---------- promo codes ----------

    async def add_promo_codes(self, codes: list[str], package_id: int | None = None, expiry_at=None) -> int:
        assert self.pool
        added = 0
        async with self.pool.acquire() as conn:
            for code in codes:
                code = code.strip()
                if not code:
                    continue
                try:
                    await conn.execute(
                        "INSERT INTO promo_codes (code, package_id, expiry_at) VALUES ($1, $2, $3)",
                        code, package_id, expiry_at,
                    )
                    added += 1
                except asyncpg.UniqueViolationError:
                    continue  # bir xil kod ikki marta qo'shilmasin
        return added

    async def promo_stats(self) -> dict:
        assert self.pool
        row = await self.pool.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'available' AND (expiry_at IS NULL OR expiry_at > now())) AS available,
                COUNT(*) FILTER (WHERE status = 'used') AS used
            FROM promo_codes
            """
        )
        return {"available": row["available"], "used": row["used"]}

    async def purchase_promo_code(self, user_id: int, package_id: int) -> tuple[str, str | None]:
        """Tanlangan paketdan balansdan yechib, birinchi mavjud promo kodni beradi.
        Qaytaradi: ('ok', code) | ('insufficient', None) | ('empty', None) | ('not_found', None)
        FOR UPDATE SKIP LOCKED — bir vaqtda bir nechta foydalanuvchi bitta kodni ololmasligi uchun."""
        assert self.pool
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                package = await conn.fetchrow(
                    "SELECT * FROM promo_packages WHERE id = $1 AND active = TRUE", package_id
                )
                if package is None:
                    return "not_found", None
                price = package["price"]

                user = await conn.fetchrow("SELECT balance FROM users WHERE id = $1 FOR UPDATE", user_id)
                if user is None or user["balance"] < price:
                    return "insufficient", None

                promo = await conn.fetchrow(
                    """
                    SELECT id, code FROM promo_codes
                    WHERE package_id = $1 AND status = 'available' AND (expiry_at IS NULL OR expiry_at > now())
                    ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED
                    """,
                    package_id,
                )
                if promo is None:
                    return "empty", None
                await conn.execute("UPDATE users SET balance = balance - $1 WHERE id = $2", price, user_id)
                await conn.execute(
                    """
                    UPDATE promo_codes SET status = 'used', used_by = $1, used_at = now(), price_paid = $2
                    WHERE id = $3
                    """,
                    user_id, price, promo["id"],
                )
                return "ok", promo["code"]
