-- Bosqich 2: Balans to'ldirish, promo kod sotib olish, referal.
-- Eslatma: flash sale, VIP chegirma va 2-darajali referal TZ'ning
-- ustuvorlik tartibida 5-bosqichga kiritilgan — bu yerda ataylab yo'q.

CREATE TABLE IF NOT EXISTS payments (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    photo_file_id   TEXT NOT NULL,
    amount          BIGINT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    reason          TEXT,
    reviewed_by     BIGINT,
    reviewed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Bitta to'lov so'rovi barcha adminlarga alohida xabar bo'lib boradi;
-- kimdir tasdiqlasa/rad etsa, qolgan nusxalarni ham yangilash uchun saqlanadi.
CREATE TABLE IF NOT EXISTS payment_notifications (
    id          SERIAL PRIMARY KEY,
    payment_id  INTEGER NOT NULL REFERENCES payments(id),
    admin_id    BIGINT NOT NULL,
    chat_id     BIGINT NOT NULL,
    message_id  BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_codes (
    id          SERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'available',   -- available | used
    expiry_at   TIMESTAMPTZ,
    used_by     BIGINT REFERENCES users(id),
    used_at     TIMESTAMPTZ,
    price_paid  BIGINT,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Standart sozlamalar (mavjud bo'lmasa qo'shiladi, mavjud bo'lsa tegilmaydi)
INSERT INTO settings (key, value) VALUES
    ('card_number', 'Kiritilmagan — /admin orqali sozlang'),
    ('card_holder', 'Kiritilmagan'),
    ('promo_price', '10000'),
    ('referral_bonus_l1', '0'),
    ('payment_request_limit_per_hour', '3')
ON CONFLICT (key) DO NOTHING;
