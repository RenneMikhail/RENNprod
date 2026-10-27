# Кабинет сотрудника — проверка 26.10.2026

Страница `?view=employee` сохраняет recruitment, client и brief рядом. Работает со своим отдельным вымышленным профилем и ключом localStorage `renn-employee-demo-v1`. Исходный `demo-api.js` и его прошлые незакоммиченные изменения сохранены; добавлены только роли cg/fpv и допуск cg/generative к remote в демо-подборе.

Первый рабочий блок — месячный календарь с легендой: синяя собственная занятость, оранжевые назначения RENN, отметки интервалов в timezone сотрудника. Можно добавить, изменить и снять свою занятость; пересечение с назначенной сменой запрещено. Пустая дата не означает подтверждённую доступность. Демо-предложения и календарь первоначально показывают следующий месяц, чтобы примеры не были заведомо в прошлом.

Личные предложения показывают только условия вымышленного сотрудника: даты/время, место, тип, описание, вознаграждение, менеджер. «Взять» доступно после подтверждения условий, простое предложение назначает смену, второе сохраняет отклик до решения менеджера. Вопрос сохраняется как локальный черновик, не отправляется. Профиль: роли включая CG/FPV/AI, город, техника, формат работы. Навигация employee не содержит owner panel/CRM. Это не авторизация: все статические данные вымышлены, localStorage подконтролен браузеру.

## Реально выполнено

- `node docs/team/test_employee.cjs` — PASS: изолированный mock, конфликт интервалов, назначение, повтор ключа, отклик без назначения, профиль, вопрос, сохранение/сброс и синтаксис inline scripts.
- `node docs/team/test_demo.cjs` — PASS: предыдущие профиль/бриф/подбор/manager gate/assignment/workspace privacy не регрессировали.
- `node --check` для employee.js и demo-api.js — PASS.
- Browser: employee view открыт на локальном статическом preview. На 320/360/390/430 px scrollWidth равен viewport, дни >=44x44 px, текстовые inputs/select/textarea 16px, в header ноль ссылок panel.
- Browser: подтверждение условий → «Взять» → назначенная смена; профиль изменён → reload → новое значение сохранено.
- Telegram API, poller и исходный runtime не запускались/не изменялись этой UI-задачей. Core/bot переданы интеграционному чату до внесения правок.

## Source adapter, передача backend-задаче

`src/team-routing/employee.js` совпадает с UI-модулем demo. Source `index.html` грузит `/employee.js`, ветка `/employee` требует `/api/me` с role=employee. Backend должен раздавать `/employee` и `/employee.js` (server.py здесь не менялся).

`GET /api/employee/state`: только свои данные, `{profile, availability, assignments, offers, questions}`. Profile — объект полей либо specialist с вложенным profile. Для assignments обязательны start/end/title; offers содержат id/status/version плюс terms JSON или объект с start/end/fee/currency, а также желательно title/location/type/description/manager. Времена ISO с offset. Доверенную identity устанавливает server-side auth, не actor браузера.

Действия source adapter:

- `POST /api/block`: start/end/timezone для нового интервала; сервер устанавливает self.
- `POST /api/block-update`: id для отмены; id/start/end/timezone для изменения своей блокировки.
- `POST /api/respond`: offer/decision/version/key; сервер устанавливает self.
- `POST /api/profile`: city/roles/equipment/mobility; сервер устанавливает self, не принимает чужой id или qualification.
- `POST /api/employee/question`: offer/body/key; сохранить вопрос в проект без ложного статуса внешней доставки. Если backend не реализовал, показывает ошибку вместо ложного успеха.

Интеграция с настоящей auth/API пока не проверялась в этом UI-проходе. Реальные профили/ставки не использовались. В статике timezone demo поддерживает UTC/Moscow/Tbilisi; другие timezone требуют backend ZoneInfo. Английский employee UI пока не переведён, существующие публичные RU/EN сохранены.

OLMO запрошена с 12s timeout для узкого callback-validator. Полученный код некорректен, не использован. Код UI написан вручную и проверен указанными тестами.
