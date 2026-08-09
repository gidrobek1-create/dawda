-- Bosqich 1: asosiy oqim uchun minimal sxema.
-- Keyingi bosqichlarda (balans to'ldirish, promo, referal, campaign, admin_logs)
-- yangi migratsiya fayllari (002_..., 003_...) qo'shib boriladi — bu fayl o'zgartirilmaydi.

CREATE TABLE IF NOT EXISTS users (
    id              BIGINT PRIMARY KEY,          -- telegram user id
    username        TEXT,
    full_name       TEXT,
    language        TEXT,                        -- 'uz' | 'ru' | NULL (hali tanlanmagan)
    balance         BIGINT NOT NULL DEFAULT 0,    -- so'mda, butun son
    referrer_id     BIGINT REFERENCES users(id),
    referral_count  INTEGER NOT NULL DEFAULT 0,
    vip_level       TEXT NOT NULL DEFAULT 'none',
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    is_registered   BOOLEAN NOT NULL DEFAULT FALSE, -- til tanlab, oqimni to'liq o'tganmi
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

-- Majburiy obuna kanallari (bir nechtasi bo'lishi mumkin)
CREATE TABLE IF NOT EXISTS required_channels (
    id          SERIAL PRIMARY KEY,
    chat_id     TEXT NOT NULL,      -- @username yoki -100... id
    title       TEXT,
    invite_link TEXT,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admins (
    user_id     BIGINT PRIMARY KEY,
    role        TEXT NOT NULL DEFAULT 'moderator', -- 'super' | 'moderator'
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
