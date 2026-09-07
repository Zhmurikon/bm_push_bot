# Benchmark Push Bot

Сервис уведомлений о заявках с сайтов — в Telegram, напрямую владельцу сайта.

Бот: [@bm_push_bot](https://t.me/bm_push_bot)  
Домен: `bmbot.yuriy-konkov.ru`

## Что это

Веб-студия Benchmark делает сайты. Заявка с формы → мгновенно в Telegram владельцу. Без CRM, без паролей — только уведомления.

## Возможности

- **API для сайтов:** `POST /api/v1/leads/` с авторизацией по токену проекта
- **Коды приглашения:** клиент подключается по ссылке, без участия студии
- **Несколько получателей:** один сайт → несколько чатов, один чат → несколько сайтов
- **Кнопки статусов:** «Взял в работу» → «Обработана» — видно в групповом чате
- **Шаблоны:** настраиваемый текст сообщения для каждого проекта
- **Админ-команды:** `/projects`, `/invite`, `/last`, `/send`, `/off`
- **Delivery tracking:** для каждой доставки сохраняется message_id, статус, ошибки

## Стек

| Слой | Решение |
|------|---------|
| Web | Django 5.1 + DRF |
| Bot | aiogram 3.17 (polling) |
| DB | SQLite |
| Deploy | Docker + docker-compose |
| HTTPS | Nginx Proxy Manager + Let's Encrypt |

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Отредактировать .env — указать BOT_TOKEN

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000

# В отдельном терминале:
python -m bot.polling
```

Админка: http://localhost:8000/admin/

## Продакшен

```bash
# Деплой
./scripts/deploy.sh

# Логи
ssh lidopad_static "docker compose -f /opt/bm_push_bot/docker-compose.prod.yml logs"

# Рестарт бота
ssh lidopad_static "docker compose -f /opt/bm_push_bot/docker-compose.prod.yml restart bot"
```

## API

Подробная инструкция по интеграции: [docs/API.md](docs/API.md).

### Отправка заявки

```bash
curl -X POST https://bmbot.yuriy-konkov.ru/api/v1/leads/ \
  -H 'Authorization: Bearer bmp_live_...' \
  -H 'Content-Type: application/json' \
  -d '{
    "fields": {"Имя": "Иван Иванов", "Телефон": "+79999999999"},
    "source": "форма в подвале"
  }'
```

Ответ: `{"id": 42, "delivered": 2}`

### Идемпотентность

```bash
curl ... -H 'Idempotency-Key: unique-key-123' ...
```

Повторный запрос с тем же ключом не создаёт дубль.

## Подключение группового чата

1. `/invite <slug>` у администратора — бот вернёт код и ссылку `?startgroup=...`.
2. Ссылка добавляет бота в выбранную группу. Если бот уже в группе — отправить туда `/start INV-XXXXXX`.
3. Менять настройки в BotFather не нужно: команды и нажатия кнопок доходят до бота и при
   включённом privacy mode.

## Админ-команды (для администраторов)

| Команда | Описание |
|---------|----------|
| `/projects` | Список проектов |
| `/invite <slug>` | Создать код приглашения |
| `/last <slug>` | Последние 5 заявок |
| `/send <slug> <текст>` | Ручная рассылка |
| `/off <slug> <chat_id>` | Отключить получателя |

## Структура

```
config/           — Django settings, ASGI
notifier/         — модели, API, админка
  models.py       — Project, Recipient, Subscription, Lead, Delivery, Invite
  views.py        — POST /api/v1/leads/
  admin.py        — Django admin
  services.py     — Telegram API, шаблоны
  telegram_webhook.py — webhook endpoint (не используется, polling вместо него)
bot/              — aiogram handlers
  handlers.py     — /start, /stop, кнопки, админ-команды
  polling.py      — запуск в polling-режиме
deploy/           — nginx конфиг, .env.prod шаблон
scripts/          — deploy.sh
```

## Прокси

Telegram API требует прокси (SOCKS5). Настраивается через `PROXY_URL` в .env:

```
PROXY_URL=socks5://localhost:9998
```

На сервере работает SSH-туннель (systemd-сервис `ssh-tunnel-telegram`).
