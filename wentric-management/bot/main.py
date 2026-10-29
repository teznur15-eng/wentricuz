import asyncio
import logging
from io import BytesIO
from pathlib import Path
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BufferedInputFile
from pydantic_settings import BaseSettings, SettingsConfigDict
ROOT = Path(__file__).resolve().parents[1]

class Config(BaseSettings):
    telegram_bot_token: str = ''
    bot_api_secret: str = ''
    api_base_url: str = 'http://127.0.0.1:8000/api/v1'
    model_config = SettingsConfigDict(env_file=str(ROOT / '.env'), env_file_encoding='utf-8', extra='ignore')
cfg = Config()
logging.basicConfig(level=logging.INFO)
dp = Dispatcher()
pending_invites: dict[int, str] = {}
keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='👤 Profilim'), KeyboardButton(text='✅ Ishni boshlash')], [KeyboardButton(text='🏁 Ishni tugatish'), KeyboardButton(text='📋 Vazifalarim')], [KeyboardButton(text='🔔 Bildirishnomalar'), KeyboardButton(text='📣 E’lonlar')], [KeyboardButton(text='🪪 Wentric Card'), KeyboardButton(text='⛔ Kartani bloklash')], [KeyboardButton(text='📝 Xodimlik arizasi')], [KeyboardButton(text='💡 Taklif / muammo')]], resize_keyboard=True, input_field_placeholder='Bo‘limni tanlang')

async def post(path: str, telegram_id: int, extra: dict | None=None):
    payload = {'telegram_id': telegram_id, **(extra or {})}
    async with httpx.AsyncClient(timeout=12) as client:
        return await client.post(cfg.api_base_url + path, json=payload, headers={'X-Bot-Secret': cfg.bot_api_secret})

async def employee_message(message: Message, path: str, empty_text: str, formatter):
    if not message.from_user:
        return
    try:
        r = await post(path, message.from_user.id)
        if r.status_code == 403:
            await message.answer('Bu bo‘limdan foydalanish uchun administrator tasdiqlagan faol xodim hisobingiz bo‘lishi kerak.', reply_markup=keyboard)
            return
        r.raise_for_status()
        data = r.json()
        await message.answer(formatter(data) if data else empty_text, reply_markup=keyboard)
    except Exception:
        await message.answer('Server bilan bog‘lanib bo‘lmadi. Backend ishga tushgani va .env sozlamalarini tekshiring.', reply_markup=keyboard)

@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    if m.from_user and command.args and command.args.startswith('invite-'):
        pending_invites[m.from_user.id] = command.args[len('invite-'):]
        await m.answer('Taklif kodi qabul qilindi. Xodimlik arizasi tugmasini bosib, ma’lumotlaringizni yuboring.', reply_markup=keyboard)
        return
    await m.answer('Assalomu alaykum! 👋\n\nWentric IT Group ichki boshqaruv botiga xush kelibsiz. Bu yerda profil, davomat, vazifalar, e’lonlar va takliflar bilan ishlashingiz mumkin.', reply_markup=keyboard)

@dp.message(Command('help'))
async def help_cmd(m: Message):
    await m.answer('Asosiy menyudagi tugmalardan foydalaning. Ariza: Ism Familiya | Bo‘lim | Lavozim | Izoh\nTaklif: Sarlavha | Matn\nMuammo: Sarlavha | Matn', reply_markup=keyboard)

@dp.message(F.text == '👤 Profilim')
async def profile(m: Message):
    if not m.from_user:
        return

    async def fmt(d):
        return f"👤 {d['full_name']}\nBo‘lim: {d.get('department') or '—'}\nLavozim: {d.get('position') or '—'}\nRollar: {', '.join(d['roles'])}"
    await employee_message(m, '/integrations/bot/profile', 'Profil topilmadi', fmt)

@dp.message(F.text == '✅ Ishni boshlash')
async def start_att(m: Message):
    if not m.from_user:
        return
    try:
        r = await post('/integrations/bot/attendance/start', m.from_user.id, {'mode': 'remote'})
        if r.status_code == 409:
            await m.answer('Bugungi ish vaqti allaqachon boshlangan.', reply_markup=keyboard)
        else:
            r.raise_for_status()
            await m.answer('✅ Ish vaqti boshlandi. Xavfsiz ish kuni tilaymiz!', reply_markup=keyboard)
    except Exception:
        await m.answer('Davomatni yozib bo‘lmadi. Xodim tasdiqlanganmi va backend ishlayaptimi — tekshiring.', reply_markup=keyboard)

@dp.message(F.text == '🏁 Ishni tugatish')
async def finish_att(m: Message):
    if not m.from_user:
        return
    try:
        r = await post('/integrations/bot/attendance/finish', m.from_user.id)
        if r.status_code == 400:
            await m.answer('Avval ‘Ishni boshlash’ tugmasini bosing.', reply_markup=keyboard)
        else:
            r.raise_for_status()
            await m.answer('🏁 Ish vaqti tugadi. Yozuv saqlandi.', reply_markup=keyboard)
    except Exception:
        await m.answer('Davomatni yakunlab bo‘lmadi. Backendni tekshiring.', reply_markup=keyboard)

@dp.message(F.text == '📋 Vazifalarim')
async def tasks(m: Message):

    async def fmt(data):
        if not data:
            return 'Hozir sizga biriktirilgan vazifa yo‘q.'
        return '📋 Vazifalaringiz:\n\n' + '\n\n'.join((f"#{t['id']} · {t['title']}\nHolat: {t['status']} · Ustuvorlik: {t['priority']}\nMuddat: {t.get('deadline') or 'belgilanmagan'}" for t in data))
    await employee_message(m, '/integrations/bot/tasks', 'Hozircha vazifalar yo‘q', fmt)

@dp.message(F.text == '🔔 Bildirishnomalar')
async def notifications(m: Message):

    async def fmt(data):
        return '🔔 Bildirishnomalar:\n\n' + '\n\n'.join((f"• {x['title']}\n{x['body']}" for x in data)) if data else 'Yangi bildirishnoma yo‘q.'
    await employee_message(m, '/integrations/bot/notifications', 'Yangi bildirishnoma yo‘q', fmt)

@dp.message(F.text == '📣 E’lonlar')
async def announcements(m: Message):

    async def fmt(data):
        return '📣 So‘nggi e’lonlar:\n\n' + '\n\n'.join((f"• {x['title']}\n{x['body']}" for x in data)) if data else 'Hozircha e’lon yo‘q.'
    await employee_message(m, '/integrations/bot/announcements', 'Hozircha e’lon yo‘q', fmt)

@dp.message(F.text == '🪪 Wentric Card')
async def card(m: Message):
    if not m.from_user:
        return
    try:
        r = await post('/integrations/bot/cards', m.from_user.id)
        r.raise_for_status()
        cards = r.json()
        if not cards:
            await m.answer('Sizga hali Wentric Card chiqarilmagan.', reply_markup=keyboard)
            return
        for item in cards:
            caption = (
                f"🪪 Wentric Card\n{item['card_number']}\n"
                f"Xodim: {item.get('employee_name') or '—'}\n"
                f"Bo‘lim: {item.get('department') or '—'}\n"
                f"Lavozim: {item.get('position') or '—'}\n"
                f"Rollar: {', '.join(item.get('roles') or [])}\n"
                f"Holat: {item['status']}"
            )
            if item.get('status') == 'active' and item.get('qr_token'):
                import qrcode
                image = qrcode.make('wentric-card:' + item['qr_token'])
                buffer = BytesIO()
                image.save(buffer, format='PNG')
                await m.answer_photo(BufferedInputFile(buffer.getvalue(), filename=f"{item['card_number']}.png"), caption=caption, reply_markup=keyboard)
            else:
                await m.answer(caption + '\nQR-kod karta faollashtirilgandan keyin ko‘rinadi.', reply_markup=keyboard)
    except Exception:
        await m.answer('Kartalarni ko‘rib bo‘lmadi. Backend va xodim hisobingizni tekshiring.', reply_markup=keyboard)

@dp.message(F.text == '⛔ Kartani bloklash')
async def block_own_card(m: Message):
    if not m.from_user:
        return
    try:
        r = await post('/integrations/bot/cards/block-request', m.from_user.id)
        if r.status_code == 404:
            await m.answer('Bloklanadigan faol karta topilmadi.', reply_markup=keyboard)
        else:
            r.raise_for_status()
            await m.answer('🛑 Karta bloklandi. Xavfsizlik uchun administratorlarga xabar yuborildi.', reply_markup=keyboard)
    except Exception:
        await m.answer('Kartani bloklab bo‘lmadi. Xodim hisobingiz va server sozlamalarini tekshiring.', reply_markup=keyboard)

@dp.message(F.text == '📝 Xodimlik arizasi')
async def apply_help(m: Message):
    await m.answer('Quyidagi formatda yuboring:\n\nIsm Familiya | Bo‘lim | Lavozim | Qisqa izoh\n\nMasalan:\nAli Valiyev | Development | Python developer | Backend tajribam bor', reply_markup=ReplyKeyboardRemove())

@dp.message(F.text == '💡 Taklif / muammo')
async def suggestion_help(m: Message):
    await m.answer('Taklif yuborish: Taklif: Sarlavha | Batafsil matn\nMuammo yuborish: Muammo: Sarlavha | Batafsil matn', reply_markup=ReplyKeyboardRemove())

@dp.message(F.text.regexp('^(Taklif|Muammo):'))
async def suggestion_submit(m: Message):
    if not m.from_user:
        return
    parts = (m.text or '').split(':', 1)
    kind = 'suggestion' if parts[0] == 'Taklif' else 'problem'
    payload = parts[1].split('|', 1)
    if len(payload) < 2 or len(payload[0].strip()) < 2 or len(payload[1].strip()) < 2:
        await m.answer('Format: Taklif: Sarlavha | Batafsil matn', reply_markup=keyboard)
        return
    try:
        r = await post('/integrations/bot/suggestions', m.from_user.id, {'title': payload[0].strip(), 'body': payload[1].strip(), 'kind': kind})
        r.raise_for_status()
        await m.answer('✅ Xabaringiz qabul qilindi.', reply_markup=keyboard)
    except Exception:
        await m.answer('Xabar yuborilmadi. Xodim hisobingiz va server sozlamalarini tekshiring.', reply_markup=keyboard)

@dp.message(F.text.contains('|'))
async def application_submit(m: Message):
    if not m.from_user:
        return
    parts = [p.strip() for p in (m.text or '').split('|', 3)]
    if len(parts) < 2 or len(parts[0]) < 2:
        await m.answer('Format: Ism Familiya | Bo‘lim | Lavozim | Izoh', reply_markup=keyboard)
        return
    payload = {'telegram_id': m.from_user.id, 'full_name': parts[0], 'department': parts[1] or None, 'desired_position': parts[2] if len(parts) > 2 and parts[2] else None, 'message': parts[3] if len(parts) > 3 and parts[3] else None}
    if m.from_user.id in pending_invites:
        payload['invite_code'] = pending_invites[m.from_user.id]
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.post(cfg.api_base_url + '/integrations/applications', json=payload, headers={'X-Bot-Secret': cfg.bot_api_secret})
        if r.is_success:
            pending_invites.pop(m.from_user.id, None)
            await m.answer('✅ Arizangiz yuborildi. Administrator ko‘rib chiqadi.', reply_markup=keyboard)
        else:
            await m.answer('Ariza yuborilmadi. Bot va backend tokenlari sozlanganini tekshiring.', reply_markup=keyboard)
    except Exception:
        await m.answer('Server bilan bog‘lanib bo‘lmadi. Backend ishga tushganini tekshiring.', reply_markup=keyboard)

@dp.message(F.document)
async def telegram_document_upload(m: Message, bot: Bot):
    if not m.from_user or not m.document:
        return
    try:
        stream = BytesIO()
        await bot.download(m.document, destination=stream)
        content = stream.getvalue()
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(cfg.api_base_url + '/integrations/bot/files', data={'telegram_id': str(m.from_user.id)}, files={'file': (m.document.file_name or 'telegram_file.pdf', content, m.document.mime_type or 'application/octet-stream')}, headers={'X-Bot-Secret': cfg.bot_api_secret})
        if r.is_success:
            await m.answer(f"📎 Fayl Wentric tizimiga saqlandi: {r.json().get('original_name', 'fayl')}", reply_markup=keyboard)
        else:
            await m.answer(f"Fayl yuklanmadi: {r.json().get('detail', 'ruxsat yoki fayl turini tekshiring')}", reply_markup=keyboard)
    except Exception:
        await m.answer('Telegram faylini saqlab bo‘lmadi. Server va fayl hajmini tekshiring.', reply_markup=keyboard)

async def reminder_loop():
    while True:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(cfg.api_base_url + '/integrations/bot/reminders/run', headers={'X-Bot-Secret': cfg.bot_api_secret})
                if not r.is_success:
                    logging.warning('Deadline reminder ishlamadi: %s', r.status_code)
        except Exception as exc:
            logging.warning('Deadline reminder serverga ulanmayapti: %s', exc)
        await asyncio.sleep(3600)

async def main():
    if not cfg.telegram_bot_token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN .env faylida sozlanmagan')
    bot = Bot(token=cfg.telegram_bot_token)
    task = asyncio.create_task(reminder_loop())
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()
        await bot.session.close()
if __name__ == '__main__':
    asyncio.run(main())
