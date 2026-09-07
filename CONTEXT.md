# Контекст разработки — BM Push Bot

## Текущий статус (2026-09-07)

### Реализовано

| Этап | Описание | Статус |
|------|----------|--------|
| 0 | Каркас проекта (Django + aiogram + Docker) | ✅ |
| 1 | MVP: POST /api/v1/leads/ → Telegram | ✅ |
| 2 | Продакшен: сервер, HTTPS, бэкапы | ✅ |
| 3 | Коды приглашения: /start, /stop | ✅ |
| 4 | Шаблоны, Delivery, предпросмотр | ✅ |
| 5 | Кнопки: «Взял в работу» → «Обработана» | ✅ |
| 6 | Админ-команды: /projects, /invite, /last, /send, /off | ✅ |

### Осталось

| Этап | Описание |
|------|----------|
| 7 | Приём внешних вебхуков (Tilda и др.) |
| 8 | Эксплуатация: инструкции, автоудаление заявок |

## Инфраструктура

### Серверы
- **lidopad_static** (82.147.71.77) — основной VPS, Ubuntu 26.04
  - Docker + docker-compose
  - Nginx Proxy Manager (порт 81)
  - SSH SOCKS5 туннель на localhost:9998 (через 178.104.249.205)
- **2german** (178.104.249.205) — прокси-сервер для Telegram

### Контейнеры
- **bm_push_bot-web-1** — Django + uvicorn (API + админка, порт 8000)
- **bm_push_bot-bot-1** — aiogram polling (получает обновления от Telegram)

### Домен
- bmbot.yuriy-konkov.ru → 82.147.71.77
- HTTPS через Let's Encrypt (NPM)

### Токены
- Bot token: в .env на сервере
- Тестовый проект: slug=test-site, токен=bmp_live_hg-Nzxibnjh0eHxzSAisorFCmXj6k648wVijTFv6PDI
- Ваш chat_id: 1291130800, is_admin=True

## Известные проблемы

### Webhook не работает
Telegram получает "Connection timed out" при попытке подключиться к webhook.
Временно используется polling.

**Возможные причины:**
- Firewall на уровне облачного провайдера
- Telegram IP заблокированы

**Решение:** пока оставить polling, позже разобраться с webhook.

## Команды

### Локально
```bash
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000
python -m bot.polling  # в отдельном терминале
```

### На сервере
```bash
ssh lidopad_static
cd /opt/bm_push_bot
docker compose -f docker-compose.prod.yml logs bot
docker compose -f docker-compose.prod.yml restart bot
```

### Деплой
```bash
./scripts/deploy.sh
```

## Следующие шаги

1. **Этап 7 — Tilda webhook:**
   - Создать `POST /api/v1/hooks/<project_token>/`
   - Адаптер для формата Tilda
   - Тестирование с реальной формой

2. **Этап 8 — Эксплуатация:**
   - Management команда для автоудаления заявок старше 90 дней
   - Инструкции для сотрудников и клиентов

3. **Опционально:**
   - Разобраться с webhook (почему Connection timed out)
   - Rate limiting на API
   - Логирование в файл
