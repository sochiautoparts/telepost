# Telepost Bot (@telepostspace_bot)

Бот для маркетплейса Telepost.Space — принимает объявления и организации от пользователей, размещает их в Telegram-канале @telepost_space.

## Возможности

- 📝 Приём объявлений через пошаговый диалог (FSM)
- 🏪 Добавление организаций на карту
- 📸 Загрузка фото товаров
- 🤖 AI-модерация через Cloudflare Workers AI (опционально)
- ⭐ Приём донатов через Telegram Stars
- 📊 Статистика для админов
- 🚫 Бан пользователей
- 📢 Авто-реакции на посты канала

## Команды

- `/start` — главное меню
- `/new` — создать объявление
- `/place` — добавить организацию
- `/my` — мои объявления
- `/myplaces` — мои организации
- `/donate` — поддержать проект
- `/stats` — статистика (админ)
- `/ban <id>` — заблокировать пользователя (админ)
- `/unban <id>` — разблокировать (админ)
- `/broadcast <text>` — пост в канал (админ)
- `/aistats` — статистика AI (админ)
- `/cancel` — отменить действие

## Запуск

### Локально
```bash
pip install -r requirements.txt
export BOT_TOKEN=your_token
export CHANNEL_USERNAME=telepost_space
export SITE_URL=https://telepost.space
python -m bot.main
```

### GitHub Actions (24/7)
Секреты: BOT_TOKEN, CHANNEL_USERNAME, CF_ACCOUNT_ID, CF_API_TOKEN

## AI (опционально)

Бот работает без нейросетей. При наличии CF_ACCOUNT_ID и CF_API_TOKEN:
- Модерация текста (спам, мат, мошенничество)
- Улучшение описаний
- Авто-определение категории

Модель: `@cf/meta/llama-4-scout-17b-16e-instruct` (Cloudflare Workers AI, бесплатно)

## Лицензия
MIT
