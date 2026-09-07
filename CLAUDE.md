# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Проект

BM Push Bot — уведомления о заявках с сайтов в Telegram. Django (API + админка) и aiogram-бот работают
над **одной SQLite-базой** в `data/db.sqlite3`, как два отдельных процесса/контейнера.

Рабочий язык проекта — русский: имена моделей, `verbose_name`, тексты сообщений, коммиты, документация.

## Команды

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver 0.0.0.0:8000   # API + /admin/
python -m bot.polling                     # бот, отдельный терминал
python manage.py create_project "Имя" --slug my-site   # создаёт проект, печатает токен один раз
```

```bash
python manage.py test                    # все тесты
python manage.py test bot                # только бот
python manage.py test notifier.tests.LeadApiTests.test_bad_token_rejected   # один тест
```

Тесты бота (`bot/tests.py`) гоняют апдейты через настоящий `Dispatcher` с поддельной
`BaseSession`, поэтому проверяются и фильтры. Два ограничения: `router` — модуль-синглтон,
поэтому `Dispatcher` создаётся один раз на модуль; классы наследуют `TransactionTestCase`,
иначе обращения к ORM из потока `sync_to_async` упираются в «database table is locked».

Линтеров/форматтеров не настроено.

Деплой: `./scripts/deploy.sh` (rsync на `lidopad_static:/opt/bm_push_bot` → `docker compose up -d --build`
→ `migrate` → `collectstatic`). Логи/рестарт — `docker compose -f docker-compose.prod.yml logs|restart bot`.

## Архитектура

**Поток заявки.** `POST /api/v1/leads/` (`notifier/views.py`) → авторизация по `Authorization: Bearer bmp_live_…`,
сверка SHA-256 с `Project.token_hash` (сам токен нигде не хранится) → дедупликация по заголовку
`Idempotency-Key` → рендер текста → синхронная рассылка **в цикле по активным подпискам** прямо в
обработчике запроса, по одной `Delivery` на получателя. Ошибки `bot was blocked` / `chat not found`
автоматически гасят `Recipient.is_active`.

**Две реализации Telegram API — не путать:**
- `notifier/services.py` — «сырые» вызовы Bot API через aiohttp (`sendMessage`, `editMessageText`).
  Используется веб-частью и вызывается из синхронного кода через `async_to_sync`.
- `bot/app.py` — aiogram `Bot` с `AiohttpSession`. Используется процессом бота.

Обе читают `PROXY_URL` из окружения: Telegram доступен только через SOCKS5-прокси (на сервере — SSH-туннель
`ssh-tunnel-telegram` на `localhost:9998`). Без прокси локально отправка не пройдёт.

**Бот** (`bot/handlers.py`) — асинхронный, но всю работу с ORM оборачивает в `@sync_to_async` функции,
которые вызывают `_ensure_django()` и импортируют модели **внутри тела функции**. Этот шаблон нужно
сохранять при добавлении хендлеров.

**Кнопки статусов.** Клавиатура строится в `services.build_lead_keyboard(lead_id, status)` по схеме
`callback_data = "lead:<id>:<action>"`, состояния: `new → in_progress → done`. При нажатии бот правит
сообщение у **всех** получателей заявки — по сохранённым в `Delivery.message_id`.

**Групповые чаты.** В группе `message.chat.id` — id группы, а не пользователя, поэтому админ-права
проверяются по `message.from_user.id` (`_is_admin(message)`). Подключение группы: ссылка
`?startgroup=<code>` (`Invite.group_invite_link`) либо `/start <code>` сообщением в чат. Превращение
группы в супергруппу меняет `chat_id`: это ловится и в боте (`migrate_to_chat_id`), и на отправке —
Telegram возвращает `parameters.migrate_to_chat_id`, `views.create_lead` обновляет получателя и
повторяет отправку один раз.

**Модели** (`notifier/models.py`): `Project` ⇄ `Recipient` через `Subscription` (many-to-many с флагом
активности); `Lead` → много `Delivery`; `Invite` — код `INV-XXXXXX`, подключение через deep link
`https://t.me/bm_push_bot?start=<CODE>`, валидность считает `Invite.is_valid`.

**Шаблоны сообщений.** `Project.template` — обычный Django-шаблон, рендерится в `render_lead_text`
с контекстом `project, fields, created_at, source`. Пустой шаблон → `DEFAULT_TEMPLATE`. В админке проекта
есть живой предпросмотр на фиктивных данных.

## Webhook (не используется)

`notifier/telegram_webhook.py` и `bot/app.telegram_webhook_app` — рабочий, но **отключённый** путь:
Telegram не может достучаться до сервера (Connection timed out). В проде используется polling-контейнер.
Не «чинить» и не подключать webhook без явной просьбы.

## Планы

`ROADMAP.md` — этапы 0–8, `CONTEXT.md` — текущий статус, инфраструктура и следующие шаги
(этап 7: приём вебхуков Tilda; этап 8: автоудаление старых заявок). При изменении статуса работ
обновляйте `CONTEXT.md`.
