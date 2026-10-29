# Xavfsizlik nazorat ro‘yxati

- `.env` va `web/.env.local` maxfiy qiymatlarni saqlaydi va Git’dan chiqarilgan.
- Telegram Login Widget imzosi va `auth_date` serverda tekshiriladi.
- Backend har so‘rovda DB sessiyasi, xodim holati va rolni tekshiradi; 30 daqiqa faol bo‘lmagan sessiya tugaydi.
- Moliya faqat `SUPER_ADMIN` va `CEO` rollari uchun ochiq.
- `SUPER_ADMIN` CEO’dan alohida; oxirgi faol Super Admin rolini tasodifan olib tashlashga yo‘l qo‘yilmaydi.
- CTO uchun `technical`, COO uchun `operations` loyiha doirasi qo‘llanadi. Loyiha bo‘limi kodi: `technical`, `operations`, `general`.
- Xavfli amallar frontend tasdig‘i va `X-Confirm-Action: confirmed` server tekshiruvidan o‘tadi; CORS’da header ruxsat etilgan.
- Wentric Card QR tasodifiy tokenni o‘z ichiga oladi. Hash bilan tekshiriladi; qayta ko‘rsatish zarur bo‘lganda token `JWT_SECRET` dan hosil qilingan kalit bilan shifrlangan holda saqlanadi. `JWT_SECRET`ni almashtirishdan oldin kartalarni qayta chiqarish/rotatsiya rejasini tuzing.
- Xodim bloklansa yoki ishdan ketsa sessiyalar bekor qilinadi; ishdan ketganda kartalar bekor qilinadi, audit va tarixiy yozuvlar saqlanadi.
- Fayl kengaytmasi/hajmi tekshiriladi; fayllar tasodifiy server nomi bilan private storage’da turadi.
- Muhim amallar audit jurnalida; login muvaffaqiyatsizliklari security event’larda qayd etiladi.
- Backup/restore skriptlari mavjud. Backup nusxasini alohida himoyalangan joyga ham saqlang va tiklashni test qiling.

## Production’dan oldin

HTTPS va Secure cookie, CSRF himoyasi, login/API rate limiting, Alembic migratsiyalari, monitoring/alerting, fayl antivirus/karantin, backup shifrlash va off-site nusxalar, maxfiy kalitlarni rotatsiya qilish hamda mustaqil xavfsizlik auditi talab qilinadi. Bu repo mahalliy MVP bo‘lib, ishlab chiqarish tizimiga to‘g‘ridan-to‘g‘ri chiqarilmasin.
