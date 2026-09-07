# Интеграция сайта с BM Push Bot

Одна точка входа: сайт отправляет POST-запрос — заявка приходит в Telegram.

## Эндпоинт

```
POST https://bmbot.yuriy-konkov.ru/api/v1/leads/
Authorization: Bearer bmp_live_...
Content-Type: application/json
```

Токен выдаётся на проект (создание проекта в админке или `manage.py create_project`).
Показывается один раз при создании — восстановить нельзя, только перевыпустить.

## Тело запроса

| Поле | Тип | Описание |
|------|-----|----------|
| `fields` | object | Пары «подпись → значение». Порядок сохраняется, ключи попадают в сообщение как есть |
| `text` | string | Готовый текст сообщения. Если задан — шаблон проекта игнорируется |
| `source` | string | Откуда заявка: «форма в подвале», «квиз на главной». Доступно в шаблоне |

Нужно передать `fields` **или** `text`, иначе `400`.

## Ответы

| Код | Тело | Когда |
|-----|------|-------|
| 201 | `{"id": 42, "delivered": 2}` | Заявка принята, `delivered` — сколько чатов получили |
| 201 | `{"id": 42, "delivered": 0, "duplicate": true}` | Повтор по `Idempotency-Key` |
| 400 | `{"detail": ...}` | Пустое тело / нет `fields` и `text` |
| 401 | `{"detail": "Неверный токен"}` | Токен неверен или проект выключен |

`delivered: 0` при `201` без `duplicate` означает: заявка сохранена, но получателей нет
или Telegram недоступен. Заявка не теряется — её видно в админке.

## Идемпотентность

Заголовок `Idempotency-Key` с уникальным значением на отправку формы: повторный
запрос с тем же ключом не создаёт дубль и не шлёт второе сообщение. Нужен при
ретраях и двойных сабмитах.

## Примеры

### curl

```bash
curl -X POST https://bmbot.yuriy-konkov.ru/api/v1/leads/ \
  -H 'Authorization: Bearer bmp_live_...' \
  -H 'Content-Type: application/json' \
  -d '{"fields": {"Имя": "Иван", "Телефон": "+79999999999"}, "source": "форма в подвале"}'
```

### JS (через свой бэкенд)

Токен нельзя класть в клиентский код — иначе кто угодно сможет слать заявки.
Браузер шлёт на свой обработчик, обработчик — в API.

```js
// на своём сервере
await fetch("https://bmbot.yuriy-konkov.ru/api/v1/leads/", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.BM_PUSH_TOKEN}`,
    "Content-Type": "application/json",
    "Idempotency-Key": submissionId,
  },
  body: JSON.stringify({
    fields: { "Имя": name, "Телефон": phone, "Комментарий": comment },
    source: "форма в подвале",
  }),
});
```

### PHP

```php
$ch = curl_init('https://bmbot.yuriy-konkov.ru/api/v1/leads/');
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => [
        'Authorization: Bearer ' . getenv('BM_PUSH_TOKEN'),
        'Content-Type: application/json',
    ],
    CURLOPT_POSTFIELDS => json_encode([
        'fields' => ['Имя' => $name, 'Телефон' => $phone],
        'source' => 'форма обратного звонка',
    ], JSON_UNESCAPED_UNICODE),
    CURLOPT_TIMEOUT => 15,
]);
$response = curl_exec($ch);
```

## Как подключить чат-получатель

1. Администратор в боте: `/invite <slug проекта>` — бот вернёт код и две ссылки.
2. **Личный чат:** клиент открывает ссылку `?start=INV-XXXXXX`.
3. **Группа:** ссылка `?startgroup=INV-XXXXXX` добавляет бота в выбранный чат.
   Если бот уже в группе — отправить туда сообщением `/start INV-XXXXXX`.
4. Отключение: `/stop` в этом чате или `/off <slug> <chat_id>` у администратора.

Один проект может слать в несколько чатов, один чат может получать несколько проектов.

## Чек-лист интеграции

- Токен лежит в переменных окружения сайта, не в клиентском JS.
- Ответ формы пользователю не зависит от ответа API — уведомление не должно ронять форму.
- Таймаут 10–15 секунд, при ошибке — ретрай с тем же `Idempotency-Key`.
- Названия полей в `fields` пишутся так, как их нужно видеть в Telegram.
- Проверка после подключения: тестовая заявка через curl → сообщение в чате → карточка в админке.
