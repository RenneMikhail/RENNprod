# RENN Prod — состояние интеграции, 2026-10-31

Изменения локальные, не закоммичены и не опубликованы. Исходная точка: 17dfac304d1ecea1957ba89576bc4b013bc9efea.

## Реализовано
- Серверные права finances:read и contacts:read выдаются отдельно владельцем через API. Проекции specialists/state/intakes/workspace скрывают защищённые поля. Произвольные описания с возможными контактами и ценами доступны менеджеру только при наличии обоих прав.
- Форма shooting требует город и контакт, передаёт их серверу. Подтверждение показывается только после успешного сохранения. При ошибке введённый текст остаётся в форме; черновик сохраняется в sessionStorage на 24 часа и восстанавливается после перезагрузки той же вкладки. После подтверждения записи удаляется только отправленная версия; новые правки во время запроса сохраняются. При недоступном хранилище форма продолжает работать без гарантии восстановления.
- Атомарная запись заявки и очереди уведомлений. request_id предотвращает дубликат при повторе; повтор ключа с другим содержимым отклоняется.
- CRM читает /api/intakes и показывает реальные заявки таблицей с городом, описанием и контактом согласно правам. Добавлены обновление и явная ошибка загрузки. Статусы новых заявок, «В работе» и «Архив» сохраняются в общей базе через /api/intake/status. Изменение доступно владельцу и менеджеру с tasks:approve; сотруднику запрещено. История обращений группируется по совпадающему контакту среди загруженных заявок, без создания фиктивной истории выполненных проектов.
- Диспетчер Telegram отправляет идентификатор новой заявки без контактов и цен. Запускается сервером каждые 30 секунд; повторяет неудачи до 10 попыток. Отправленные записи повторно не выбираются. После сбоя между отправкой и отметкой возможен повтор сообщения; многопроцессный запуск диспетчера не поддержан.
- Исправлены подмена actor, обход проверки участия менеджера в заказе, отрицательная длина HTTP-тела, дубликат аккаунта и ставки NaN/Infinity.

## Подтверждённые проверки
- `rtk test python3 -m unittest discover -s src/team-routing -p 'test*.py'`: 47 тестов, OK, 12.478 с.
- HTTP-тест: заявка → временная общая база → API CRM с правами → очередь → имитация успешного Telegram sendMessage.
- HTTP-проверка статусов: отказ сотруднику и менеджеру без права, успешное сохранение владельцем, чтение сохранённого статуса, отказ неизвестному статусу.
- Проверены повтор отправки без дубликата заявки, повтор после ошибки транспорта и отдельные права финансов/контактов.
- Проверена возможность записи второй заявки во время сетевой отправки: блокировки базы нет (автокоммит SQLite); дополнительного исправления блокировки не потребовалось.
- Node VM: успешная загрузка CRM, защита от параллельного обновления, очистка записей и сообщение при сетевой ошибке — PASS.
- `node --check`: CRM app.js, team-api-adapter.js, shooting app.js — код 0.
- `rtk git diff --check` — код 0.

## Не подтверждено / осталось
- Живая доставка Telegram: в окружении этой оболочки отсутствуют TELEGRAM_BOT_TOKEN и RENN_MANAGER_CHAT_ID. Секреты не читались и не печатались. Нужен запуск сервера с этими переменными из защищённой конфигурации, затем проверка сообщения в целевом чате.
- Публичная сквозная связка: нет подтверждённого размещения HTTPS backend и его конфигурации. По AGENTS.md docs/ остаётся статической демонстрацией; публичные файлы не менялись и реальные данные туда не переносились.
- Полноценная сущность клиента и история выполненных проектов, создание проектов из заявок, полная синхронизация предложений/кабинетов/Telegram в этом проходе не реализованы. Реализована только история обращений по совпадающему контакту.
- Черновик восстанавливается после перезагрузки вкладки; фоновой очереди автоматической отправки нет. Закрытие вкладки завершает срок sessionStorage.
- Глобальная изоляция менеджеров по всем проектам и произвольным текстовым полям требует отдельной проверки; текущие тесты не являются полным аудитом безопасности.
- Визуальная проверка обновлённого интерфейса на мобильном устройстве и повторная сверка обоих документов ревью со скриншотами не выполнены.

## Ключевые файлы
- src/team-routing/privacy.py — серверная фильтрация полей.
- src/team-routing/intake_delivery.py — сохранение и очередь Telegram.
- src/team-routing/server.py, access.py, auth.py — маршруты, права, диспетчер.
- src/team-routing/test_server_auth.py, test_intake_delivery.py — регрессии интеграции.
- src/shooting-landing/app.js — контакт/город и подтверждение сохранения.
- src/crm-prototype/team-api-adapter.js, app.js — заявки в таблице CRM.

Локальный Qwen использовался для ограниченной проверки политики actor в предыдущем проходе; неверное ограничение прав владельца отклонено. Текущие проверки выполнены детерминированными инструментами.

## Проверка текущего прохода
- Node test_draft.cjs: 3 теста, 0 ошибок — восстановление полей/request_id, TTL и повреждённые данные, отказ хранилища.
- node --check src/shooting-landing/app.js и rtk git diff --check: код 0.
- GitHub API: Pages собран из main:/docs. Эти локальные изменения относятся к src/ и ещё не опубликованы. Настроенного развёртывания backend среди проверенных файлов репозитория не найдено.
- GitHub авторизация доступна; доступность GitHub не подтверждает размещение Python backend и доставку Telegram.

## Очередь Telegram: диагностика и повтор (31.10.2026)
- Добавлены GET /api/delivery/status и POST /api/delivery/retry: только владелец; POST требует существующую проверку сессии/CSRF. Ответ не содержит токенов, контактов или текста заявок.
- В настройках локальной CRM владелец видит настройку отправки, счётчики queued/sent/retry_exhausted. По ID можно сбросить 10 неудачных попыток; уже отправленное уведомление повторно не ставится. Отправка асинхронна существующим серверным обработчиком.
- Свежая проверка Python: 48 тестов, OK, 13.204 с; проверены 401/403, CSRF, успешный повтор и отказ повтора отправленного/несуществующего уведомления.
- Node VM: отображение очереди, payload повтора, отказ роли manager, ошибка HTTP и некорректные счётчики — PASS. Это проверка логики, не визуальная проверка браузером.
- Node test_draft.cjs: код 0, ошибок 0; node --check CRM app.js и git diff --check: код 0.
- Текущее окружение: server/bot остановлены, порты 8766/8767 не слушают; TELEGRAM_BOT_TOKEN и RENN_MANAGER_CHAT_ID отсутствуют, корневой .env отсутствует. Живая доставка НЕ выполнена.
- Изменения остаются локальными в src/, публикации backend и обновления GitHub Pages в этом проходе нет.
- Локальный Qwen выполнил короткое ревью диагностики; неподходящие предложения (несуществующий owner_id, запрет повтора исчерпавшей попытки записи) отклонены по исходному коду и назначению функции.

## Рабочие проекты CRM (31.10.2026)
- Устранена подмена серверных проектов локальными демо-заказами: рабочий дашборд читает orders из защищённого /api/state, город, сроки, статус и принятого менеджера из базы. Демо-режим сохранён отдельно.
- При ошибке API очищаются проекты, заявки и сотрудники; устаревшие записи не выдаются за актуальные.
- Добавлены test_registry.cjs: загрузка серверного проекта, очистка при HTTP 503, отсутствие fallback на демо. Два теста PASS; node --check обоих изменённых JS и git diff --check — код 0.
- Локальный Qwen выполнил чтение/ревью адаптера. Три замечания отклонены: запросы same-origin, отказ при неуспешном HTTP намеренный, AbortSignal.timeout использует TimeoutError. Код проверен детерминированными тестами.
- Публикации и проверки живой Telegram-доставки в этом проходе нет.

## Telegram: отклики сотрудника (31.10.2026)
- /offers показывает до пяти собственных актуальных предложений: проект, город, начало, результат, оплата; кнопки «Взять / Отказаться».
- Отклик проходит общую доменную проверку владельца предложения, срока и версии внутри транзакции Telegram update; повтор update не меняет состояние дважды. После отказа запускается повторный подбор.
- Принятие не объявляется назначением: для обычного проекта остаётся подтверждение менеджера, сохранено существующее auto_assign.
- Добавлен регрессионный test_bot_offers.py: чужой Telegram ID, отклик, повтор события, устаревшая кнопка, запрет группового чата. Перед правкой тест падал.
- Живой транспорт не запускался: переменные TELEGRAM_BOT_TOKEN, RENN_MANAGER_CHAT_ID, RENN_PUBLIC_ORIGIN отсутствуют; порт 8766 закрыт. Доступ к секретам не выполнялся. Публикации нет.

## 2026-10-31 — outbound employee offers
- Added staff_delivery.py and server notification-clock integration: private Telegram recipient from specialist.telegram_id, offer buttons, maximum 10 delivery attempts, stale/expired offer suppression.
- Removed false email fallback from core.tick: expired queued notifications are marked expired; email transport is not implemented.
- New regression test covers transport failure/retry, no resend after success, recipient and callback data, stale suppression, and DB writes during transport (no held write lock).
- Delivery is at-least-once: a process crash after Telegram accepts but before DB acknowledgement can duplicate a message. Callback processing remains versioned/idempotent. Worker lock is process-local; run one server notification worker.
- Local Qwen reviewed the module through LM Studio. Claimed packet loss on busy lock is not supported: rows stay queued. Crash/ack ambiguity is valid and documented above.
- Live delivery and publication remain unverified. This change does not implement manager/assignment notifications or account linking.

## 2026-10-31 — employee question notifications
- Added question_delivery.py to the server notification clock. Saved employee questions act as a durable queue; only the accepted project manager with a positive private Telegram ID receives a notice. Questions without a linked/assigned manager stay pending.
- Notices contain only the question ID and CRM instruction, never question text, contacts or financial terms. Maximum 10 transport attempts; a successful send is not repeated by subsequent normal polls. Single-process worker; crash-after-send duplication remains possible.
- Updated question-save response; it does not claim successful Telegram delivery.
- Regression test first failed on the missing module, then all 51 Python tests passed (13.396 s): no recipient before assignment, correct manager recipient, retry after transport failure, no private body, no resend after success.
- Local Qwen review performed. Rejected unsupported findings: static SQL is not injection, specialist JOIN supplies the recipient, separate transport/DB transactions intentionally avoid holding a database write lock across network I/O. No claim of exactly-once delivery.
- Not published or live-tested. Website-account Telegram binding, manager commands and production deployment remain separate unfinished work.


## 2026-10-31 — website account / Telegram binding
- Added telegram_link.py: 192-bit random bearer code, SHA-256 hash persisted, ten-minute expiry, one outstanding code per account, single-use consumption and account/Telegram uniqueness.
- Authenticated /api/account/telegram status/issue and /unlink use the session principal; mutation requires the existing CSRF guard. account.html offers issue/status/unlink controls. Send /link CODE in the bot's private chat; sender must match private chat ID.
- Binding rejects disabled accounts, existing/conflicting specialist Telegram ownership, and shared active specialist accounts. Specialist-linked accounts update the routing recipient; unlink clears only their own matching recipient. No auto-created specialist or expanded role permissions.
- Savepoints make code consumption, recipient changes and registration-state cleanup atomic. Regression coverage includes expiry/reissue/replay, identity mismatch, cross-account isolation, CSRF, disabled accounts, specialist conflict/unlink and a forced late DB failure followed by successful retry.
- Local Qwen review performed via LM Studio. Partial-write findings rejected: auth DB is only read, and routing mutations share a rollback savepoint; forced-failure regression verifies rollback. Cross-database account-deactivation concurrency is not claimed atomic.
- account.html inline JavaScript syntax and git diff whitespace checks passed. No mobile visual validation, publication or live Telegram verification in this pass.
- Remaining: manager accounts without specialist mapping are bound at account level only; notification routing must explicitly support that mapping. Production API/deployment and live receipt remain unverified. Existing deliveries remain at-least-once, not exactly-once.
- Full-suite check exposed an existing intermittent HTTP reset on logout: its request body was not consumed before closing the connection. Logout now parses the bounded body before revoking the session; the existing HTTP regression covers the route.
- A second full-suite run reproduced connection reset on an early 403 response too. Shared JSON and cookie response writers now include Content-Length, so clients read the bounded response rather than waiting for connection closure with unread request bytes.
- Final validation: 57/57 Python tests passed in 14.320 s; account.html inline JavaScript syntax passed; git diff --check passed. These are local automated results, not production/live delivery evidence.

## 2026-10-31 — уведомления привязанным аккаунтам управления
- Если RENN_MANAGER_CHAT_ID не задан, новые заявки уведомляют активные привязанные Telegram-аккаунты владельца и менеджеров, даже без specialist_id. При заданном общем чате сохранён прежний маршрут.
- Успех доставки учитывается отдельно для каждого получателя: при частичном сбое повтор отправляется только недоставленным адресатам. Контакты и бюджеты не отправляются.
- Регрессия сначала падала, после исправления полный серверный набор: 58/58, 14.413 s. git diff --check проходит.
- Локальная Qwen 9B проверила файл. Два замечания отклонены: общий sent намеренно требует всех получателей, а ручной сброс исчерпанных попыток является штатным повтором; отдельная таблица предотвращает повтор успешным адресатам.
- Ограничения: доставка at-least-once; один процесс отправки. Получатели пересчитываются на проход; уже завершённые заявки новым привязкам задним числом не рассылаются. Проверка с реальным Telegram и публикация не выполнялись.

## 2026-10-31 — Telegram: очередь клиентских заявок

- Добавлена /requests: последние 10 клиентских заявок из общей routing DB; ID, город, услуга, текущий статус.
- Доступ только у привязанных активных owner/manager с tasks:read; актуальные права проверяются при каждом запросе. Сотрудник, посторонний Telegram и чужой чат отклоняются.
- Контакты, бриф и бюджет в сообщения не включаются. Команда только читает заявки, изменение статусов остаётся в CRM.
- Регрессия сначала воспроизведена (1 failure), затем весь Python-набор: 59/59 OK; отдельный тест привязки/прав после расширения: 6/6 OK; git diff --check OK. Qwen local проверила план тестов, код и тесты выполнены основным агентом.
- Изменения локальные. Живая доставка, перезапуск poller и публикация в этом проходе не выполнялись.

## 2026-10-31 — Telegram: управление статусами заявок

- /requests расширена кнопками «В работу» и «В архив»: new → working → archive в общей базе CRM. Это заменяет прежнее ограничение «команда только читает».
- Кнопки доступны только активному привязанному owner/manager с tasks:approve; доступ проверяется заново при каждом нажатии. Менеджер без этого права читает список.
- Проверены отзыв права, деактивация аккаунта, чужой чат, повтор update, устаревшая клавиатура и попытка изменить не-клиентскую запись. Контакты и финансы не включаются.
- TDD: новая регрессия сначала упала из-за отсутствия кнопок. После реализации весь серверный набор: 61/61 OK, 14.513 s; git diff --check OK. Локальная Qwen 9B проверила план, не выполняла правки или тесты.
- Runtime-проверка: локальные порты 8766/8767 закрыты; TELEGRAM_BOT_TOKEN, RENN_MANAGER_CHAT_ID, RENN_PUBLIC_ORIGIN отсутствуют в окружении текущего процесса. Секретные файлы не читались. Это не доказывает отсутствие конфигурации в других процессах/хранилищах.
- Изменения локальные, публикация и живая доставка не подтверждены.

## Вопросы сотрудников → CRM — проверено 2026-10-31
- Добавлен GET /api/questions: владелец видит все вопросы, менеджер с tasks:read — только вопросы проектов, где он принят менеджером. Сотрудникам маршрут запрещён.
- Текст вопроса доступен только при одновременных contacts:read и finances:read; без них отображается отметка об ограничении.
- Адаптер CRM загружает вопросы; раздел задач показывает отдельную таблицу с сотрудником, проектом, городом, датой и вопросом. Города вопросов включены в общий фильтр. Статус заявки из этой таблицы не изменяется.
- Проверки: Python unittest discover — 62 теста, OK (14.677 с); Node test_registry.cjs — без ошибок; node --check обоих изменённых JS — код 0; git diff --check — код 0.
- Qwen локально проверил ограниченный план доступа; код и проверки выполнены основным агентом.
- Визуальная проверка, публикация и живая доставка Telegram в этом проходе не выполнены.

## Заявка → проект в CRM — проверено 2026-10-31
- Добавлен POST /api/intake/project: владелец и менеджер с tasks:approve могут создать проект из клиентской заявки. Обязательны название, начало, окончание и часовой пояс; город берётся из заявки.
- Создание выполняется в транзакции; повторный запрос возвращает тот же проект. Архивные заявки и неверные интервалы отклоняются без частичной записи. Контакт клиента не копируется в бриф проекта.
- В таблице заявок CRM добавлена форма создания проекта. После сохранения загружается актуальное состояние API; у связанной заявки отображается ID проекта.
- Проверки: Python unittest discover — 64 теста OK (15.310 с); Node test_registry.cjs — 3 теста без ошибок, включая POST, CSRF-заголовок, расписание и отказ API.
- Локальная Qwen 9B использована только для ограниченного анализа транзакции; код и проверки выполнены основным агентом.
- Изменения в src/, публичная docs/ не менялась. Публикация, визуальное мобильное ревью и живая доставка Telegram в этом проходе не подтверждены.
