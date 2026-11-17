# all bot texts in 3 languages
LANGS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

T = {
    "choose_lang": {
        "uz": "Tilni tanlang:",
        "ru": "Выберите язык:",
        "en": "Choose your language:",
    },
    "lang_set": {
        "uz": "✅ Til: O'zbekcha",
        "ru": "✅ Язык: Русский",
        "en": "✅ Language: English",
    },
    "welcome": {
        "uz": "Salom! 🚌 Karvon — Farg'ona avtobuslari jonli rejimda.\n\n"
              "🗺 Xaritada avtobus qayerda, qachon keladi va qanchalik to'laligini ko'ring.\n"
              "🤖 Menga savol yozing, masalan: \"Hozir 1-yo'nalish to'lami?\"\n"
              "📍 Joylashuvingizni yuborsangiz, eng yaqin bekatni aytaman.",
        "ru": "Привет! 🚌 Karvon — автобусы Ферганы в реальном времени.\n\n"
              "🗺 На карте видно, где автобус, когда придёт и насколько он заполнен.\n"
              "🤖 Задайте мне вопрос, например: \"Маршрут 1 сейчас заполнен?\"\n"
              "📍 Отправьте геолокацию — скажу ближайшую остановку.",
        "en": "Hi! 🚌 Karvon shows Fergana's buses live.\n\n"
              "🗺 See on the map where the bus is, when it arrives and how full it is.\n"
              "🤖 Ask me anything, e.g. \"Is route 1 full now?\"\n"
              "📍 Send your location and I'll tell you the nearest stop.",
    },
    "open_map": {"uz": "🗺 Xaritani ochish", "ru": "🗺 Открыть карту", "en": "🗺 Open bus map"},
    "map_hint": {
        "uz": "Xaritani oching — avtomatik kirasiz:",
        "ru": "Откройте карту — вход автоматический:",
        "en": "Open the map, you'll be logged in automatically:",
    },
    # reply keyboard buttons
    "btn_loc": {"uz": "📍 Joylashuvim", "ru": "📍 Моя геолокация", "en": "📍 Send my location"},
    "btn_settings": {"uz": "⚙️ Sozlamalar", "ru": "⚙️ Настройки", "en": "⚙️ Settings"},
    "btn_help": {"uz": "❓ Yordam", "ru": "❓ Помощь", "en": "❓ Help"},
    "btn_phone": {"uz": "📱 Raqamni yuborish", "ru": "📱 Отправить номер", "en": "📱 Share my phone number"},
    "share_phone": {
        "uz": "📱 Kirish uchun telefon raqamingizni yuboring (pastdagi tugma).",
        "ru": "📱 Чтобы войти, отправьте свой номер (кнопка внизу).",
        "en": "📱 Share your phone number to log in (button below).",
    },
    "menu_below": {"uz": "Menyu pastda 👇", "ru": "Меню внизу 👇", "en": "Menu is below 👇"},
    "help": {
        "uz": "❓ Nima qila olaman:\n"
              "• 🗺 Xarita: avtobuslar, kelish vaqti, to'liqlik, eslatma\n"
              "• 🤖 Har qanday savol yozing: \"Qaysi avtobus bozorga boradi?\", \"Qachon kamroq gavjum?\"\n"
              "• 📍 Joylashuv: eng yaqin bekat va avtobuslar\n"
              "• ⚙️ Sozlamalar: til, ism, telefon",
        "ru": "❓ Что я умею:\n"
              "• 🗺 Карта: автобусы, время прибытия, заполненность, напоминание\n"
              "• 🤖 Задайте любой вопрос: \"Какой автобус идёт к базару?\", \"Когда меньше людей?\"\n"
              "• 📍 Геолокация: ближайшая остановка и автобусы\n"
              "• ⚙️ Настройки: язык, имя, телефон",
        "en": "❓ What I can do:\n"
              "• 🗺 Map: buses, arrival time, how full, arrival alert\n"
              "• 🤖 Ask anything: \"Which bus goes to the bazaar?\", \"When is it least crowded?\"\n"
              "• 📍 Location: nearest stop and buses\n"
              "• ⚙️ Settings: language, name, phone",
    },
    # settings
    "settings": {
        "uz": "⚙️ Sozlamalar\n\n👤 Ism: {name}\n📱 Telefon: {phone}\n🎭 Rol: {role}\n🌐 Til: {language}",
        "ru": "⚙️ Настройки\n\n👤 Имя: {name}\n📱 Телефон: {phone}\n🎭 Роль: {role}\n🌐 Язык: {language}",
        "en": "⚙️ Settings\n\n👤 Name: {name}\n📱 Phone: {phone}\n🎭 Role: {role}\n🌐 Language: {language}",
    },
    "not_set": {"uz": "kiritilmagan", "ru": "не указано", "en": "not set"},
    "no_role": {
        "uz": "xaritani bir marta oching",
        "ru": "откройте карту один раз",
        "en": "open the map once",
    },
    "s_lang": {"uz": "🌐 Tilni o'zgartirish", "ru": "🌐 Сменить язык", "en": "🌐 Change language"},
    "s_name": {"uz": "✏️ Ismni o'zgartirish", "ru": "✏️ Изменить имя", "en": "✏️ Change name"},
    "s_phone": {"uz": "📱 Telefonni o'zgartirish", "ru": "📱 Изменить телефон", "en": "📱 Change phone"},
    "s_close": {"uz": "✖️ Yopish", "ru": "✖️ Закрыть", "en": "✖️ Close"},
    "ask_name": {
        "uz": "Yangi ismingizni yozing (yoki /cancel):",
        "ru": "Напишите новое имя (или /cancel):",
        "en": "Type your new name (or /cancel):",
    },
    "name_saved": {"uz": "✅ Ism saqlandi: {name}", "ru": "✅ Имя сохранено: {name}", "en": "✅ Name saved: {name}"},
    "name_bad": {
        "uz": "Ism 2–60 belgidan iborat bo'lsin.",
        "ru": "Имя должно быть от 2 до 60 символов.",
        "en": "The name must be 2–60 characters.",
    },
    "ask_phone": {
        "uz": "Pastdagi tugma bilan yangi raqamni yuboring:",
        "ru": "Отправьте новый номер кнопкой внизу:",
        "en": "Send your new number with the button below:",
    },
    "cancelled": {"uz": "Bekor qilindi.", "ru": "Отменено.", "en": "Cancelled."},
    "phone_saved": {
        "uz": "✅ Raqam saqlandi: {phone}",
        "ru": "✅ Номер сохранён: {phone}",
        "en": "✅ Number saved: {phone}",
    },
    "phone_not_yours": {
        "uz": "Iltimos, o'zingizning raqamingizni tugma orqali yuboring.",
        "ru": "Пожалуйста, отправьте СВОЙ номер кнопкой.",
        "en": "Please share YOUR number with the button.",
    },
    "save_error": {
        "uz": "⚠️ Saqlab bo'lmadi ({code}). Keyinroq urinib ko'ring.",
        "ru": "⚠️ Не удалось сохранить ({code}). Попробуйте позже.",
        "en": "⚠️ Could not save ({code}). Try again later.",
    },
    "near_me_q": {
        "uz": "Menga eng yaqin bekatlar qaysi va u yerdan qaysi avtobuslar o'tadi?",
        "ru": "Какие остановки ближе всего ко мне и какие автобусы там ходят?",
        "en": "Which bus stops are nearest to me, and which buses stop there?",
    },
    "ask_usage": {
        "uz": "Savolni /ask dan keyin yozing, masalan: /ask Qaysi avtobus bozorga boradi?",
        "ru": "Напишите вопрос после /ask, например: /ask Какой автобус идёт к базару?",
        "en": "Write your question after /ask, e.g. /ask Which bus goes to the bazaar?",
    },
    # AI errors (keys from assistant.py)
    "slow": {"uz": "Bittadan savol bering 🙂", "ru": "По одному вопросу, пожалуйста 🙂", "en": "One question at a time, please 🙂"},
    "limit": {
        "uz": "Bugungi savollar limiti tugadi. Ertaga urinib ko'ring.",
        "ru": "Лимит вопросов на сегодня исчерпан. Попробуйте завтра.",
        "en": "You've reached today's question limit. Try again tomorrow.",
    },
    "no_key": {"uz": "⚠️ AI hali sozlanmagan.", "ru": "⚠️ AI ещё не настроен.", "en": "⚠️ The AI is not set up yet."},
    "timeout": {
        "uz": "⚠️ AI juda uzoq javob berdi. Qayta urinib ko'ring.",
        "ru": "⚠️ AI отвечал слишком долго. Попробуйте ещё раз.",
        "en": "⚠️ The AI took too long. Please try again.",
    },
    "busy": {
        "uz": "⚠️ AI band. Bir daqiqadan keyin urinib ko'ring.",
        "ru": "⚠️ AI занят. Попробуйте через минуту.",
        "en": "⚠️ The AI is busy. Try again in a minute.",
    },
    "problem": {
        "uz": "⚠️ AI da muammo. Keyinroq urinib ko'ring.",
        "ru": "⚠️ Проблема с AI. Попробуйте позже.",
        "en": "⚠️ The AI had a problem. Try again later.",
    },
    "empty": {
        "uz": "Kechirasiz, javob bera olmadim. Boshqacha so'rab ko'ring.",
        "ru": "Извините, не смог ответить. Спросите по-другому.",
        "en": "Sorry, I couldn't answer that. Try asking another way.",
    },
    "error": {
        "uz": "⚠️ Xatolik. Birozdan keyin urinib ko'ring.",
        "ru": "⚠️ Ошибка. Попробуйте чуть позже.",
        "en": "⚠️ Something went wrong. Try again in a moment.",
    },
}


def t(key: str, lang: str, **kw) -> str:
    s = T[key].get(lang) or T[key]["en"]
    return s.format(**kw) if kw else s


def labels(key: str) -> set[str]:
    # a button's text in every language (to recognise it)
    return set(T[key].values())
