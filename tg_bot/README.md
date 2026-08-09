# Telegram Bot — 1-bosqich (asosiy oqim)

TZ'dagi 12-bo'limdagi ustuvorlik tartibi bo'yicha qurilmoqda. Hozircha tayyor:

- `/start`, majburiy obuna(lar)ni tekshirish (bir nechta kanal qo'llab-quvvatlanadi)
- Til tanlash (🇺🇿 / 🇷🇺), `/til` orqali keyin ham o'zgartirish
- Asosiy menyu (2x2 reply keyboard), tugmalar hozircha "tez orada" stub javob beradi
- Referal (`ref_<id>`) va o'yin (`oyin_<id>`) start-parametrlarini tanib olish (logikasi keyingi bosqichlarda to'ldiriladi)
- PostgreSQL + migratsiyalar, admin/super-admin jadvali
- **Ikki rejim:** lokal test uchun polling, Render uchun webhook (aiohttp server)

Keyingi bosqichlar (TZ 12-bo'lim bo'yicha): balans/to'ldirish, promo kod, referal bonuslari, admin panel, kanal o'yini captcha, VIP/kunlik bonus, flash sale, loglash/Excel eksport.

## Lokalda ishga tushirish (polling)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env faylni to'ldiring: BOT_TOKEN, DATABASE_URL (lokal Postgres), SUPER_ADMIN_IDS
# WEBHOOK_MODE=false qoldiring

python main.py
```

Lokal PostgreSQL bo'lmasa, tezroq boshlash uchun:

```bash
docker run --name tgbot-pg -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=tgbot -p 5432:5432 -d postgres:16
```

## Render'ga deploy qilish

### A) `render.yaml` orqali (tavsiya etiladi — "Blueprint")

1. Loyihani GitHub repo'siga push qiling (bu papkadagi barcha fayllar bilan).
2. Render dashboard → **New** → **Blueprint** → repo'ni tanlang. Render `render.yaml`ni o'qib, avtomatik:
   - `tgbot-db` nomli bepul PostgreSQL bazasini,
   - `tgbot` nomli Web Service'ni yaratadi va `DATABASE_URL`ni o'zi bog'laydi.
3. Deploy paytida so'raladigan qiymatlarni kiriting:
   - `BOT_TOKEN` — @BotFather'dan olingan token
   - `SUPER_ADMIN_IDS` — sizning Telegram ID'ingiz (vergul bilan bir nechtasi)
4. Birinchi deploy tugagach, Render sizga domen beradi (masalan `https://tgbot-xxxx.onrender.com`).
   Shu domenni **Environment** bo'limida `WEBHOOK_BASE_URL` ga qo'yib, **Manual Deploy** qiling
   (chunki bot birinchi ishga tushganda o'zining domenini bilmaydi — shuning uchun bitta qo'lda qadam kerak).
5. Loglarda `"Webhook o'rnatildi: https://.../webhook/..."` yozuvini ko'rsangiz — tayyor.

### B) Qo'lda (render.yaml'siz)

1. Render → **New** → **Web Service** → repo'ni ulang.
2. **Build Command:** `pip install -r requirements.txt`
3. **Start Command:** `python main.py`
4. **Environment** bo'limida qo'lda qo'shing: `BOT_TOKEN`, `DATABASE_URL` (Render Postgres yaratib, uning "Internal Database URL"ini), `WEBHOOK_MODE=true`, `WEBHOOK_BASE_URL`, `WEBHOOK_SECRET`, `SUPER_ADMIN_IDS`.
5. Deploy qiling.

### Muhim Render eslatmalari

- **Free plan** — servis foydalanilmasa "uxlab qoladi" va webhook so'rovi kelganda uyg'onadi (bir necha soniyadan o'nlab soniyagacha kechikish bo'lishi mumkin — botning "sekin ishlashi"ning eng katta sababi odatda shu). Botni doim tez javob berishini xohlasangiz: (1) pullik planga o'ting, yoki (2) tashqi "uptime ping" xizmati (masalan UptimeRobot) bilan `/health` manzilini har 5-10 daqiqada so'rab, servisni uyg'oq tutib turing.
- Kanallarga obunani tekshirish endi barcha kanallar uchun **parallel** bajariladi (ilgari ketma-ket edi) — bir nechta majburiy kanal bo'lsa, "✅ Tekshirish" tugmasi endi sezilarli tezroq javob beradi.
- Kod `PORT` muhit o'zgaruvchisini o'zi o'qiydi (Render buni avtomatik beradi) — qo'lda o'zgartirish shart emas.
- `WEBHOOK_SECRET` — Telegramdan boshqa hech kim webhook manziliga soxta so'rov yubormasligi uchun himoya; `render.yaml`da avtomatik generatsiya qilinadi.
- Baza migratsiyalari (`migrations/*.sql`) bot ishga tushganda avtomatik bajariladi — qo'lda `psql` bilan yugurtirish shart emas.

## Admin panel (/admin)

Barcha sozlamalar endi bitta joyda — alohida buyruqlarni eslab yurish shart emas:

```
/admin
```

Super-adminga tugmali menyu chiqadi: 💳 karta, 🎁 promo narxi, 🔗 referal bonusi,
⏱ to'lov limiti, 📢 majburiy kanallar (qo'shish/o'chirish), 🎟 promo kodlar
(qo'shish + statistika), 👥 adminlar (qo'shish/o'chirish), 📊 umumiy statistika.
Moderatorga esa faqat qisqa ma'lumot ko'rsatiladi — ular to'lovlarni o'ziga kelgan
xabar ostidagi ✅/❌ tugmalari orqali hal qilishda davom etadi.

Majburiy kanal qo'shishda **bot o'sha kanalda admin bo'lishi shart** — aks holda
obunani tekshira olmaydi va foydalanuvchilarni "obuna emassiz" deb bloklab qo'yishi mumkin.

## Keyingi qadam

TZ'dagi ustuvorlik tartibiga ko'ra navbatdagi bosqich — **4-bo'lim: kanal o'yini
(captcha), so'ngra VIP/kunlik bonus, 2-darajali referal, flash sale va
broadcast/Excel eksport/Sentry**. Shu bosqichlarni ham xohlasangiz, davom ettiraman.
