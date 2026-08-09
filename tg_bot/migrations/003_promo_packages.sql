-- Bosqich 3: promo kodlar endi bitta umumiy narxda emas, bir nechta
-- "paket" ko'rinishida sotiladi (masalan "42 lik — 1500 so'm", "79 lik — 3500 so'm").
-- Har bir paketning o'z narxi va o'ziga tegishli kodlar zaxirasi bor.

CREATE TABLE IF NOT EXISTS promo_packages (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,          -- masalan "42 lik"
    price       BIGINT NOT NULL,        -- so'mda
    sort_order  INTEGER NOT NULL DEFAULT 0,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS package_id INTEGER REFERENCES promo_packages(id);

-- Eski (paketsiz) sxemadan qolgan, hali paketga bog'lanmagan kodlarni yo'qotib
-- qo'ymaslik uchun ular birgina "Promokod" nomli standart paketga ko'chiriladi.
-- (Bu blok faqat shunday kodlar mavjud bo'lgandagina ishlaydi, shu sabab
-- migratsiya qayta ishga tushirilsa ham xavfsiz — takror bajarilmaydi.)
DO $$
DECLARE
    default_id INTEGER;
    old_price BIGINT;
BEGIN
    IF EXISTS (SELECT 1 FROM promo_codes WHERE package_id IS NULL) THEN
        SELECT value::BIGINT INTO old_price FROM settings WHERE key = 'promo_price';

        INSERT INTO promo_packages (name, price, sort_order)
        VALUES ('Promokod', COALESCE(old_price, 0), 0)
        RETURNING id INTO default_id;

        UPDATE promo_codes SET package_id = default_id WHERE package_id IS NULL;
    END IF;
END $$;
