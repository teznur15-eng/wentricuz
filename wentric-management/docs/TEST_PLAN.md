# Mahalliy test rejasi

## Avtomatik testlar

Loyiha ildizida:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

`test_security.py` Telegram login HMAC tekshiruvi, o‘zgartirilgan ma’lumot va muddati o‘tgan login hamda token utilitalarini tekshiradi.

## Qo‘lda tekshiruv

1. `GET /health` → `status: ok`.
2. API start bo‘lganda PostgreSQL ulanishi va jadvallar yaratilishi.
3. Noto‘g‘ri Telegram imzosi → 401; eski `auth_date` → 401.
4. `SUPER_ADMIN_TELEGRAM_IDS` ro‘yxatidagi ID login qilsa Super Admin roli yaratilishi.
5. Faol bo‘lmagan yoki tasdiqlanmagan xodimning login qilolmasligi.
6. `EMPLOYEE` uchun `/api/v1/finance` → 403; CEO/Super Admin uchun ruxsat.
7. CTO faqat `technical`, COO faqat `operations` bo‘limidagi loyihalarni ko‘rishi.
8. Xodim davomatni boshlashi va tugatishi; takroriy start rad etilishi.
9. Xodim vazifani yakunlasa `review`, rahbar tasdiqlasa `done` bo‘lishi.
10. Xavfli amal `X-Confirm-Action` siz yuborilsa → 428.
11. Wentric Card berilganda holat `pending`; alohida tasdiqlangach botda karta va QR ko‘rinishi.
12. QR tokenning oddiy matni DB’da saqlanmaganligi; kartani bloklaganda QR tekshiruvi rad etilishi.
13. Web va Telegram orqali ruxsat etilgan fayl yuklash; noto‘g‘ri kengaytma va katta fayl rad etilishi.
14. Xodim `terminated` bo‘lsa sessiya va karta bekor qilinishi, tarix saqlanishi.
15. 30 daqiqa davomida API so‘rovi bo‘lmasa sessiya tugashi.
16. Deadline reminder bir xil vazifani bir kunda ko‘p marotaba spam qilmasligi.
17. PDF/Excel hisobotlari tegishli bo‘lim doirasida yuklanishi; moliya eksporti faqat CEO/Super Admin uchun bo‘lishi.
18. `backup.ps1` orqali nusxa yaratish; alohida sinov bazasida `restore.ps1` bilan qayta tiklash.

Testlarda faqat soxta ma’lumotlardan foydalaning; haqiqiy xodimlar va moliya ma’lumotlarini tekshiruv uchun yuklamang.
