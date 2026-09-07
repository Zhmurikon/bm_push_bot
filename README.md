# Benchmark Push Bot

Сервис уведомлений о заявках с сайтов — в Telegram, напрямую владельцу сайта.

Бот: [@bm_push_bot](https://t.me/bm_push_bot)
Домен: `bmbot.yuriy-konkov.ru`

## Зачем это

Веб-студия Benchmark делает сайты. У каждого сайта есть форма заявки, и заявка
должна дойти до владельца бизнеса. Telegram человек читает всегда.

**Продукт:** клиент подключает свой чат к боту один раз, дальше каждая заявка с
его сайта приходит сообщением в течение секунды.

## Локальный запуск

### Требования

- Python 3.12+
- Docker + docker-compose (для контейнерного запуска)

### Быстрый старт (локально, без Docker)

```bash
# 1. Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Настроить переменные окружения
cp .env.example .env
# Отредактировать .env — указать BOT_TOKEN от BotFather

# 4. Применить миграции
python manage.py migrate

# 5. Создать суперпользователя (для доступа к админке)
python manage.py createsuperuser

# 6. Запустить dev-сервер
python manage.py runserver 0.0.0.0:8000
```

Админка: http://localhost:8000/admin/

### Запуск бота в режиме polling (для локальной разработки)

В отдельном терминале:

```bash
source .venv/bin/activate
python -m bot.polling
```

### Запуск через Docker

```bash
cp .env.example .env
# Отредактировать .env

docker compose up --build
```

Сервис доступен на http://localhost:8000/

## Структура проекта

```
config/          — настройки Django, ASGI/WSGI
notifier/        — основное приложение (модели, API, админка)
bot/             — Telegram-бот (aiogram)
  app.py         — создание бота, интеграция webhook в ASGI
  handlers.py    — обработчики команд
  polling.py     — локальный запуск без webhook
```

## Прокси для Telegram

При локальной разработке и если сервер не имеет прямого доступа к Telegram API,
используется SOCKS5h прокси. Укажите в `.env`:

```
PROXY_URL=socks5h://0.0.0.0:9998
```
