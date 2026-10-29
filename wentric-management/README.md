# Wentric Management — Windows uchun mahalliy MVP

Wentric IT Group ichki boshqaruv tizimi: **Telegram bot + FastAPI + PostgreSQL + Next.js/TypeScript**. Kodlar boshlang‘ich ishlaydigan MVP sifatida tuzilgan; production tizim, mustaqil xavfsizlik auditi yoki xizmatlar real muhitda sinovdan o‘tganining kafolati emas.

## Nimalar kiritilgan?

- **Rollar:** Super Admin, CEO, CTO, COO, loyiha rahbari va xodim. Super Admin CEO’dan alohida. Bir nechta Super Admin Telegram ID orqali oldindan belgilanishi mumkin.
- **Telegram orqali web login:** Telegram Login Widget imzosini serverda tekshirish, DB sessiyasi va 30 daqiqalik harakatsizlik cheklovi.
- **Xodimlar:** administrator qo‘shishi, xodimlik arizasi, tasdiqlash/rad etish, taklif kodi, rollar va hisobni bloklash/ishdan ketkazish. Ishdan ketgan xodimning hisob/kartasi bekor qilinadi, tarix saqlanadi.
- **Loyihalar va vazifalar:** mas’ul, muddat, ustuvorlik, jarayon foizi, xodim tomonidan topshirish va rahbar tomonidan qabul qilish. Loyiha bo‘limi `technical`, `operations` yoki `general` sifatida belgilanadi; CTO/COO ko‘rish doirasi tegishli bo‘lim bilan cheklanadi.
- **Wentric Card:** raqamli karta, alohida tasdiqlash, QR-kod, bloklash va bekor qilish. QR token hash ko‘rinishida tekshiriladi, Telegram botda qayta ko‘rsatish uchun shifrlangan shaklda saqlanadi.
- **Davomat:** ofis/masofaviy ishni boshlash va tugatish, individual ish jadvali, ruxsat/ta’til so‘rovlari va tasdiqlash.
- **Moliya:** UZS, kirim/chiqim va oldindan tasdiqlanadigan xarajatlar. Backend bo‘yicha faqat CEO va Super Admin kiradi; Excel eksporti ham shu tekshiruvdan o‘tadi.
- **Ichki aloqa:** bildirishnomalar, muddat eslatmalari, e’lonlar, uchrashuvlar, bilimlar bazasi, taklif va muammolar.
- **Fayllar:** Telegram va web-panel orqali yuklash; lokal private storage, hajm va fayl kengaytmasi tekshiruvi.
- **Hisobot/audit:** dashboard ko‘rsatkichlari, PDF/Excel eksporti, xavfsizlik hodisalari va muhim amallar auditi.
- **Operatsion vositalar:** Docker PostgreSQL, Windows setup/start skriptlari, backup/restore va kunlik backup vazifasini o‘rnatish skripti.

## Kerakli dasturlar

- Windows 10/11
- Python 3.11 yoki yangiroq
- Node.js 20 yoki yangiroq
- Docker Desktop (PostgreSQL konteyneri uchun)
- Telegram’da BotFather orqali yaratilgan bot

## 1. `.env` sozlash

Loyiha ildizidagi `.env.example` dan `.env` nusxasini yarating. PowerShell:

```powershell
Copy-Item .env.example .env
Copy-Item web/.env.local.example web/.env.local
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Oxirgi buyruqni ikki marta ishga tushirib, alohida tasodifiy qiymatlarni `JWT_SECRET` va `BOT_API_SECRET` uchun qo‘ying. `POSTGRES_PASSWORD` uchun ham kuchli parol ishlating. Agar parolni o‘zgartirsangiz, `DATABASE_URL` ichidagi parolni ham moslang. Maxsus `@`, `:` kabi belgilarni URL-encode qilish kerak; mahalliy boshlanish uchun harf/raqam aralash kuchli parol osonroq.

`.env` ichida quyidagilarni to‘ldiring:

- `POSTGRES_PASSWORD` — PostgreSQL paroli
- `DATABASE_URL` — shu parol bilan mos async PostgreSQL URL
- `JWT_SECRET` — kamida 32 belgili tasodifiy sir
- `BOT_API_SECRET` — bot va backend orasidagi maxfiy kalit
- `TELEGRAM_BOT_TOKEN` — BotFather tokeni
- `TELEGRAM_BOT_USERNAME` — `@` belgisiz bot username
- `SUPER_ADMIN_TELEGRAM_IDS` — oldindan vakolat beriladigan Telegram raqamli ID’lari, bir nechta bo‘lsa vergul bilan

`web/.env.local` ichida:

- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1`
- `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` — `@` belgisiz bot username

**Muhim:** `.env` va `web/.env.local` GitHub’ga yuklanmaydi. Super Admin ID’larini faqat ishonchli akkauntlar uchun belgilang.

## 2. O‘rnatish

PowerShell’ni loyiha papkasida oching:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./scripts/setup.ps1
```

Skript Python virtual muhitini yaratib, backend/bot kutubxonalarini va Next.js paketlarini o‘rnatadi. Internet yoki paket reyestri mavjud bo‘lishi kerak.

## 3. Ishga tushirish

`.env` va `web/.env.local` qiymatlarini to‘ldirgach:

```powershell
./scripts/start-dev.ps1
```

Skript PostgreSQL’ni Docker orqali ishga tushiradi va API, bot hamda web-panelni alohida PowerShell oynalarida ochadi.

- Web-panel: http://localhost:3000
- API hujjatlari: http://127.0.0.1:8000/docs
- Health-check: http://127.0.0.1:8000/health

Telegram Login Widget ishlashi uchun Telegram’da bot login domenini sozlash talab etilishi mumkin. Agar `localhost` widget tomonidan qabul qilinmasa, Telegram qo‘llab-quvvatlaydigan HTTPS domen/tunnel sozlang. Mahalliy web login testida bot tokeni va web-paneldagi bot username bir xil botga tegishli bo‘lsin.

Birinchi login uchun `SUPER_ADMIN_TELEGRAM_IDS` ro‘yxatidagi ID Telegram orqali muvaffaqiyatli autentifikatsiya qilsa, Super Admin hisobi yaratiladi. Oddiy xodimlar tasdiqlangan xodim hisobi bilan kiradi yoki Telegram bot orqali ariza yuboradi.

## 4. Kunlik backup

Bir marta PowerShell’da:

```powershell
./scripts/install-daily-backup.ps1
```

Bu Windows Task Scheduler’da har kuni soat 23:00 da PostgreSQL backup vazifasini yaratadi. Mahalliy kompyuter o‘chiq bo‘lsa backup ishlamaydi; ushbu MVP’da nusxalar lokal `backups/` papkasida saqlanadi. Muhim ma’lumotlar uchun backup’ni alohida, himoyalangan joyga nusxalash va tiklashni sinash kerak.

Qo‘lda backup:

```powershell
./scripts/backup.ps1
```

Tiklash (joriy bazadagi ma’lumotlarni almashtirishi mumkin; skript `RESTORE` so‘zini tasdiqlatadi):

```powershell
./scripts/restore.ps1 -BackupFile .\backups\wentric_YYYYMMDD_HHMMSS.dump
```

## 5. Mahalliy tekshiruv

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Yana `docs/TEST_PLAN.md` dagi qo‘lda test ssenariylarini bajaring. API ishga tushgach `/health`, `/docs` va DB ulanishini tekshiring.

## Texnik eslatmalar va cheklovlar

- Backend boshlanishida SQLAlchemy `create_all` ishlatiladi. Production yoki keyingi versiyaga o‘tishda **Alembic migratsiyalari** qo‘shilishi zarur; model ustunlarini o‘zgartirish `create_all` orqali mavjud bazaga migratsiya qilinmaydi. Yangi o‘rnatishda bo‘sh ma’lumotlar bazasi ishlating.
- Bu muhitda Python fayllari compile-check va 4 ta Telegram login/token unit-testidan o‘tdi. Tashqi paketlarni yuklash cheklangani sabab Next.js production build va to‘liq DB/Telegram integratsiyasi bu yerda end-to-end bajarilmadi; kompyuteringizda `setup.ps1` dan keyin tekshiring.
- Production’dan avval HTTPS/Secure cookie, rate limiting, CSRF siyosati, monitoring, ma’lumotlar bazasi migratsiyalari, shifrlangan uzoq-muddatli backup, fayllar uchun antivirus/karantin, loglarni cheklangan saqlash va mustaqil security review talab qilinadi.
