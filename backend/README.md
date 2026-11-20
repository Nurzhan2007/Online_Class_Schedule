# KBTU University Information System — Backend

FastAPI + SQLite + SQLAlchemy + JWT. Бэкенд также раздаёт существующий фронтенд
из папки `online-class-schedule/`, поэтому после запуска всё приложение открывается
по одному адресу: <http://127.0.0.1:8000>.

> Статус: **Фаза 5** — фронтенд полностью подключён к бэкенду: вход, регистрация, выход,
> каталог, запись на курсы, «Мои курсы», панель и расписание работают с базой данных.
> (Фаза 4: запись и расписание; Фаза 3: курсы и преподаватели; Фаза 2: аутентификация,
> PBKDF2, JWT, блокировка, отзыв токенов, RBAC.)
> Отдельные экраны для преподавателя и администратора — следующая фаза.

## Требования

- Windows 10/11, PowerShell
- Python 3.10 или новее (`python --version`). При установке Python отметьте «Add python.exe to PATH».

## 1. Установка (Windows PowerShell)

Все команды выполняются из папки `backend`:

```powershell
cd путь\к\KBTU-University-Information-System\backend

python -m venv .venv

# Если PowerShell пишет "running scripts is disabled", сначала выполните
# (разрешение действует только для текущего окна):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

После активации в начале строки появится `(.venv)`. В каждом новом окне PowerShell
окружение нужно активировать заново.

> Обновляетесь с Фазы 1? Повторите `pip install -r requirements.txt` — добавлены
> `PyJWT` и `python-multipart`.

## 2. Настройка окружения

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
notepad .env
```

Вставьте сгенерированную строку в `SECRET_KEY=` и сохраните файл.

**`SECRET_KEY` обязателен.** Без него (или если он короче 32 символов) сервер
не запустится и напишет, как сгенерировать ключ. Запасного «ключа по умолчанию»
нет намеренно: иначе любой мог бы подделать токен администратора.

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `SECRET_KEY` | — (обязательно, ≥ 32 символов) | ключ подписи JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | срок действия входа |
| `MAX_LOGIN_ATTEMPTS` | 3 | неверных паролей подряд до блокировки |
| `LOCKOUT_MINUTES` | 5 | длительность блокировки |
| `DATABASE_URL` | `backend/kbtu.db` | путь к SQLite |
| `CORS_ORIGINS` | порт 5500 | нужен только для Live Server |

## 3. Инициализация базы данных

```powershell
python -m app.seed
```

Создаёт таблицы и заполняет базу:

- 3 демо-аккаунта из исходного фронтенда (пароли хранятся только как хеши):

  | Email | Пароль | Роль |
  |---|---|---|
  | student@kbtu.kz | student123 | student |
  | teacher@kbtu.kz | teacher123 | teacher (без курсов) |
  | admin@kbtu.kz | admin123 | admin |

- 16 аккаунтов преподавателей — по одному на каждого преподавателя из исходных курсов,
  email вида `имя.фамилия@kbtu.kz` (`john.smith@kbtu.kz`, `issabek.a@kbtu.kz`, …),
  демо-пароль `teacher123`;
- 21 исходный курс из `js/api.js` с теми же id (1–21), кодами, текстами на трёх языках,
  кредитами, днями, временем, аудиториями и количеством мест; каждый курс привязан
  к аккаунту своего преподавателя.

Ожидаемый вывод при первом запуске:

```
Created: 3 demo accounts, 16 teacher accounts, 21 courses.
In database: 19 users, 21 courses.
```

Команду можно запускать повторно: пользователи сравниваются по email, курсы — по коду;
создаётся только то, чего не хватает, ничего не дублируется и **не перезаписывается**
(изменения администратора сохраняются). Повторный запуск: `Created: 0 ..., 0 ..., 0 courses.`

> Обновляетесь с Фазы 2? Существующую `kbtu.db` удалять не нужно: просто снова выполните
> `python -m app.seed` — будут созданы новые таблицы, преподаватели и курсы.

Начать с чистой базы: `Remove-Item kbtu.db; python -m app.seed`.

## 4. Запуск

```powershell
uvicorn app.main:app --reload
```

- Приложение: <http://127.0.0.1:8000>
- Документация API (Swagger): <http://127.0.0.1:8000/api/docs>
  — кнопка **Authorize**: в поле `username` введите email, затем `password`.
- Проверка работоспособности: <http://127.0.0.1:8000/api/health>

Остановить сервер: `Ctrl+C`.

## 5. Автоматические тесты

```powershell
pytest
```

Тесты используют временную базу и не трогают `kbtu.db`.
Ожидаемый результат Фазы 5: **517 passed** (478 из Фаз 1–4 и 39 новых), без ошибок,
пропусков и `ResourceWarning`. Браузерные тесты запускаются отдельно (раздел «Фаза 5»).

| Файл | Что проверяет |
|---|---|
| `test_config.py` | настройки, обязательный и достаточно длинный `SECRET_KEY` |
| `test_security.py` | PBKDF2 (600 000 итераций, уникальная соль), JWT, подделка/истечение токенов |
| `test_schemas.py` | проверка входных данных, запрет выбора роли при регистрации |
| `test_lockout_rules.py` | правила блокировки как чистые функции |
| `test_auth_api.py` | регистрация, вход, `/me`, выход и отзыв токена |
| `test_lockout_api.py` | реальная блокировка через API и базу данных |
| `test_rbac.py` | матрица прав student / teacher / admin, admin-эндпоинты |
| `test_seed.py` | демо-аккаунты |
| `test_app.py` | health-check, раздача фронтенда, CORS |
| `test_seed_data.py` | данные seed **полностью совпадают** (каждое поле каждого курса) с массивом `COURSES` в `js/api.js` — тест читает сам файл фронтенда |
| `test_catalog.py` | поиск (в т.ч. кириллица и казахский), фильтры, сортировка, казахский алфавит |
| `test_course_schemas.py` | проверка данных курса для администратора |
| `test_courses_api.py` | каталог через API: 21 курс без изменений, связь с преподавателями, фильтры, места |
| `test_admin_courses.py` | создание / изменение / удаление курсов, конфликты расписания, права |
| `test_course_constraints.py` | ограничения базы данных (CHECK, UNIQUE, внешние ключи) |
| `test_teacher_courses.py` | каждый из 16 преподавателей видит ровно свои курсы |
| `test_seed_courses.py` | идемпотентность seed, сохранение id, изменения администратора не затираются |
| `test_enrollment_rules.py` | правила записи; смежные занятия (10:00 / 10:00) не пересекаются; конфликты исходного расписания |
| `test_enrollment_sql.py` | атомарный SQL записи на настоящем SQLite, в т.ч. 60 параллельных запросов на 10 мест |
| `test_enrollment_api.py` | все эндпоинты `/api/me/registrations`, права, «только свои записи», ошибки |
| `test_enrollment_concurrency.py` | параллельная запись через сервис и SQLAlchemy: нет переполнения, дублей и конфликтов |
| `test_frontend_contract.py` | фронтенд вызывает только существующие эндпоинты; все коды ошибок переведены на 3 языка; пароли не хранятся в браузере; порядок скриптов |

## 6. Ручная проверка из PowerShell

Сервер должен быть запущен (шаг 4). Откройте второе окно PowerShell:

```powershell
$api = "http://127.0.0.1:8000/api"

# Вход
$body = @{ email = "student@kbtu.kz"; password = "student123" } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType "application/json" -Body $body
$login.user
$headers = @{ Authorization = "Bearer $($login.access_token)" }

# Текущий пользователь
Invoke-RestMethod -Uri "$api/auth/me" -Headers $headers

# Студенту запрещён admin-эндпоинт (ожидается 403 auth.denied)
try { Invoke-RestMethod -Uri "$api/admin/users" -Headers $headers }
catch { "$($_.Exception.Response.StatusCode.value__) $($_.ErrorDetails.Message)" }

# Выход: токен отзывается, повторный запрос даёт 401
Invoke-RestMethod -Method Post -Uri "$api/auth/logout" -Headers $headers
try { Invoke-RestMethod -Uri "$api/auth/me" -Headers $headers }
catch { "$($_.Exception.Response.StatusCode.value__) $($_.ErrorDetails.Message)" }
```

Демонстрация блокировки (после неё аккаунт студента заблокирован на 5 минут):

```powershell
$bad = @{ email = "student@kbtu.kz"; password = "wrong" } | ConvertTo-Json
1..4 | ForEach-Object {
    try { Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType "application/json" -Body $bad }
    catch { "$($_.Exception.Response.StatusCode.value__) $($_.ErrorDetails.Message)" }
}
# 401 ... "n":2 / 401 ... "n":1 / 429 ... "seconds":300 / 429 ... (идёт отсчёт)
```

Курсы (Фаза 3). Войдите заново под администратором, если выполнили выход выше:

```powershell
$body = @{ email = "admin@kbtu.kz"; password = "admin123" } | ConvertTo-Json
$admin = @{ Authorization = "Bearer $((Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType "application/json" -Body $body).access_token)" }

# Все курсы: 21
(Invoke-RestMethod -Uri "$api/courses" -Headers $admin).Count

# Поиск, фильтры, сортировка (параметры как в фильтрах фронтенда)
Invoke-RestMethod -Uri "$api/courses?category=math&sortBy=credits&sortDir=desc" -Headers $admin |
    Format-Table code, instructor, credits, day, start, end, seatsLeft

# Один курс и варианты фильтров
Invoke-RestMethod -Uri "$api/courses/21" -Headers $admin
Invoke-RestMethod -Uri "$api/courses/meta" -Headers $admin

# Курсы преподавателя (вход под John Smith)
$body = @{ email = "john.smith@kbtu.kz"; password = "teacher123" } | ConvertTo-Json
$john = @{ Authorization = "Bearer $((Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType "application/json" -Body $body).access_token)" }
Invoke-RestMethod -Uri "$api/teacher/courses" -Headers $john | Format-Table code, day, start, end
```

Запись на курсы (Фаза 4) — под студентом:

```powershell
$body = @{ email = "student@kbtu.kz"; password = "student123" } | ConvertTo-Json
$st = @{ Authorization = "Bearer $((Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType "application/json" -Body $body).access_token)" }

# Проверка без записи (dry run) и запись на CS101 (id 1)
Invoke-RestMethod -Method Post -Uri "$api/me/registrations/check" -Headers $st -ContentType "application/json" -Body '{"courseId": 1}'
Invoke-RestMethod -Method Post -Uri "$api/me/registrations" -Headers $st -ContentType "application/json" -Body '{"courseId": 1}'

# Мои курсы и сумма кредитов
$my = Invoke-RestMethod -Uri "$api/me/registrations" -Headers $st
$my.courses | Format-Table code, day, start, end, seatsLeft
$my.totalCredits

# Повторная запись -> 409 err.alreadyRegistered
try { Invoke-RestMethod -Method Post -Uri "$api/me/registrations" -Headers $st -ContentType "application/json" -Body '{"courseId": 1}' }
catch { "$($_.Exception.Response.StatusCode.value__) $($_.ErrorDetails.Message)" }

# Пересечение: STAT201 (id 6, пн 13:00-14:50), затем CS330 (id 15, пн 14:00-15:50) -> 409 err.conflict
Invoke-RestMethod -Method Post -Uri "$api/me/registrations" -Headers $st -ContentType "application/json" -Body '{"courseId": 6}' | Out-Null
try { Invoke-RestMethod -Method Post -Uri "$api/me/registrations" -Headers $st -ContentType "application/json" -Body '{"courseId": 15}' }
catch { "$($_.Exception.Response.StatusCode.value__) $($_.ErrorDetails.Message)" }

# Отмена записи
Invoke-RestMethod -Method Delete -Uri "$api/me/registrations/1" -Headers $st
```

> Тексты на казахском и русском лучше смотреть в Swagger (`/api/docs`) или в PowerShell 7.
> Старый Windows PowerShell 5.1 иногда показывает кириллицу из API «кракозябрами» —
> это особенность отображения в консоли, в базе данных текст хранится правильно.

## API

| Метод и путь | Доступ | Описание |
|---|---|---|
| `POST /api/auth/register` | все | регистрация студента (`name`, `studentId`, `email`, `password`) |
| `POST /api/auth/login` | все | вход (JSON), возвращает JWT на 30 минут |
| `POST /api/auth/token` | все | вход формой — для кнопки Authorize в Swagger |
| `GET /api/auth/me` | любой вошедший | текущий пользователь |
| `POST /api/auth/logout` | любой вошедший | отзыв текущего токена |
| `GET /api/admin/users` | admin | список пользователей; `?role=teacher` — только преподаватели |
| `POST /api/admin/users` | admin | создание аккаунта с любой ролью (например, преподавателя) |
| `GET /api/courses` | любой вошедший | каталог с поиском, фильтрами и сортировкой (см. ниже) |
| `GET /api/courses/meta` | любой вошедший | варианты для фильтров: категории, преподаватели, кредиты, дни |
| `GET /api/courses/{id}` | любой вошедший | один курс |
| `GET /api/teacher/courses` | teacher | курсы, закреплённые за вошедшим преподавателем |
| `POST /api/admin/courses` | admin | создание курса |
| `PUT /api/admin/courses/{id}` | admin | полное изменение курса (все поля и все три языка) |
| `DELETE /api/admin/courses/{id}` | admin | удаление курса (нельзя, если есть записанные студенты) |
| `GET /api/me/registrations` | student | мои курсы, их количество и сумма кредитов |
| `POST /api/me/registrations` | student | запись на курс |
| `POST /api/me/registrations/check` | student | проверка записи без сохранения (dry run) |
| `DELETE /api/me/registrations/{course_id}` | student | отмена своей записи |

Параметры `GET /api/courses` (названия как в фильтрах фронтенда):
`term`, `category`, `day`, `instructor`, `teacherId`, `credits`, `onlyAvailable`,
`sortBy` (`code` / `name` / `instructor` / `credits` / `seats` / `day`),
`sortDir` (`asc` / `desc`), `lang` (`en` / `ru` / `kk` — язык для сортировки по названию).
Значение `all` у `category`, `day`, `instructor` означает «без фильтра».

Курс в ответе имеет ту же форму, что и в исходном `js/api.js`, плюс два поля:

```json
{
  "id": 21, "code": "INFT3107", "category": "cs",
  "name": {"en": "Basics of Information Systems", "ru": "Основы информационных систем", "kk": "Ақпараттық жүйелер негіздері"},
  "description": {"en": "...", "ru": "...", "kk": "..."},
  "instructor": "Issabek A.", "teacherId": 19,
  "credits": 3, "day": "fri", "start": "13:00", "end": "13:50",
  "room": {"kind": "room", "no": "222"},
  "seats": 74, "seatsLeft": 74
}
```

`teacherId` — ссылка на аккаунт преподавателя, `seatsLeft` = `seats` − число записанных студентов
(никогда не меньше 0).

Новые коды ошибок Фазы 3 (переводы для них добавятся во фронтенд в Фазе 8,
до этого `t()` просто покажет код):

| HTTP | `code` | Когда |
|---|---|---|
| 404 | `err.notFound` | курса с таким id нет (ключ уже есть в `i18n.js`) |
| 409 | `err.codeTaken` `{code}` | код курса уже занят |
| 422 | `err.teacherNotFound` `{teacherId}` | преподаватель не найден или аккаунт не с ролью teacher |
| 409 | `err.teacherConflict` `{code}` | преподаватель уже ведёт другой курс в это время |
| 409 | `err.roomConflict` `{code}` | аудитория уже занята в это время |
| 409 | `err.seatsBelowRegistered` `{registered}` | мест меньше, чем уже записано студентов |
| 409 | `err.courseHasRegistrations` `{count}` | нельзя удалить курс с записанными студентами |

## Фаза 5: фронтенд + бэкенд

### Запуск всего приложения

```powershell
cd путь\к\KBTU-University-Information-System\backend
.\.venv\Scripts\Activate.ps1
python -m app.seed                  # один раз (повторно — безопасно)
uvicorn app.main:app --reload
```

Откройте <http://127.0.0.1:8000> — это и фронтенд, и API (тот же адрес, CORS не нужен).
Документация API: <http://127.0.0.1:8000/api/docs>.
Если сервер не запущен, войти нельзя: старого «локального» входа больше нет.

### Демо-аккаунты (создаются `python -m app.seed`)

Только для демонстрации на локальном компьютере — это не рабочие учётные данные.

| Роль | Email | Пароль | Что можно |
|---|---|---|---|
| Студент | `student@kbtu.kz` | `student123` | каталог, запись и отмена, «Мои курсы», расписание |
| Преподаватель | `teacher@kbtu.kz` | `teacher123` | каталог и расписание; запись на курсы запрещена (403) |
| Преподаватель курса | `john.smith@kbtu.kz` (и ещё 15 `имя.фамилия@kbtu.kz`) | `teacher123` | то же; свои курсы — `GET /api/teacher/courses` |
| Администратор | `admin@kbtu.kz` | `admin123` | каталог и расписание; управление курсами пока через `/api/docs` |

Новые студенты регистрируются через форму «Register» на странице входа.

### Как устроена интеграция

```
index.html → i18n.js → http.js → api.js → auth.js → app.js
```

| Файл | Роль |
|---|---|
| `js/http.js` (новый) | **единственное** место с `fetch()`: базовый адрес `/api`, заголовок `Authorization: Bearer`, разбор JSON, ошибки → `ApiError(status, code, params)`, сетевые ошибки, 401/403, хранение токена |
| `js/auth.js` | вход, регистрация, `/auth/me`, выход через бэкенд; удаляет старые данные localStorage (в т.ч. пароли открытым текстом) |
| `js/api.js` | `CourseAPI`: кэш в памяти, заполняемый с `/api/courses`, `/api/courses/meta`, `/api/me/registrations`; поиск/фильтры/сортировка работают по загруженным данным; запись/отмена — запросы к API |
| `js/app.js` | те же 7 экранов и та же разметка; асинхронные действия, загрузка/ошибка с кнопкой «Повторить», защита от двойного нажатия, фиксированное расписание вместо выбора секции |
| `js/i18n.js` | +22 ключа на каждом языке (коды ошибок бэкенда, сеть/сервер, загрузка, названия полей) |
| `index.html` | одна строка: подключение `js/http.js` |

- **Токен** хранится в `sessionStorage` (`kbtu_access_token` и время истечения): переживает
  обновление страницы, исчезает при закрытии вкладки. Пароли нигде не сохраняются.
  После обновления страницы пользователь восстанавливается запросом `GET /api/auth/me`.
- **Блокировка входа** считается только на сервере. Фронтенд показывает ответ сервера:
  «Attempts left: N» (`auth.invalid {n}`) и «Access is locked for 4 min 37 sec» (`auth.locked {seconds}`).
- **Запись:** сначала `POST /api/me/registrations/check` (ошибка показывается до окна подтверждения),
  затем `POST /api/me/registrations` с телом `{"courseId": N}` — без id пользователя и без расписания.
  После записи/отмены каталог, места и «Мои курсы» перезагружаются с сервера.
- **Ошибки** показываются на выбранном языке. Для `err.conflict` название курса приходит с сервера
  на трёх языках, фронтенд выбирает нужный. Ответы 5xx и «не-JSON» никогда не показываются
  пользователю как есть — только «Ошибка сервера. Попробуйте позже».
- **401** (токен истёк, отозван или подделан) → сообщение и возврат на страницу входа;
  **403** → «Доступ запрещён»; **сеть недоступна** → «Нет связи с сервером» и кнопка «Повторить».
- Бэкенд в Фазе 5 **не менялся**: фронтенд адаптирован к реальным контрактам API.

### Браузерные тесты (необязательно, Playwright)

36 тестов в `backend/e2e/` открывают приложение в настоящем браузере и проходят все сценарии:
регистрация, вход, неверный пароль, блокировка и её окончание, обновление страницы, выход с отзывом
токена, 21 курс, поиск и фильтры, страница курса, запись, дубль, полный курс, конфликт, отмена,
места, «Мои курсы», недельное расписание, три языка, недостаточные права, двойное нажатие,
сетевая ошибка, скрытие ошибок сервера.

Тесты создают аккаунты и записи, поэтому запускайте их на **отдельной базе**:

```powershell
# окно 1 — сервер на отдельной базе e2e.db
cd путь\к\KBTU-University-Information-System\backend
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL = "sqlite:///e2e.db"
python -m app.seed
uvicorn app.main:app --port 8000

# окно 2 — тесты
cd путь\к\KBTU-University-Information-System\backend
.\.venv\Scripts\Activate.ps1
pip install playwright
python -m playwright install chromium
$env:E2E_BASE_URL = "http://127.0.0.1:8000"
$env:E2E_DB_PATH = "e2e.db"
pytest e2e
```

Ожидаемо: **36 passed**. `$env:E2E_HEADED = "1"` — показывать окно браузера.
Обычный `pytest` эти тесты не запускает и Playwright не требует.

### Ручная проверка (чек-лист)

| # | Действие | Ожидаемый результат |
|---|---|---|
| 1 | Register → заполнить форму → Create Account | «Registration successful!», затем вход с новым аккаунтом работает |
| 2 | Войти `student@kbtu.kz` / `student123` | «Welcome, Student Demo!», «Student ID: DEMO-ST-001» |
| 3 | Войти с неверным паролем | «Invalid email or password. Attempts left: 2» |
| 4 | Ещё 2 неверных пароля, затем верный | «Access is locked for 5 min 0 sec», верный пароль тоже отклонён |
| 5 | Подождать 5 минут, войти | вход работает |
| 6 | F5 на любой странице | остаётся в системе (панель) |
| 7 | Logout, затем «Назад» / F5 | страница входа; старый токен недействителен |
| 8 | All Courses | «Courses found: 21» |
| 9 | Поиск «calculus», «программ», фильтры категории/преподавателя/кредитов, сортировка | как в исходной версии |
| 10 | View Details у CS101 | официальное расписание (пн 09:00–10:50, Room 301), выбора секции нет |
| 11 | Register for Course → OK | «Successfully registered…», курс в «My Courses» |
| 12 | Снова открыть CS101 | кнопка «Already Registered» неактивна |
| 13 | Курс без мест | кнопка «No seats left» |
| 14 | Записаться на STAT201, затем CS330 | «schedule conflict with Statistics!» |
| 15 | My Courses → Unregister → OK | курс исчез |
| 16 | Свободные места CS101 до/после записи и отмены | 20 → 19 → 20 |
| 17 | Home | число курсов и сумма кредитов совпадают с «My Courses» |
| 18 | Home → My Weekly Schedule | курсы в нужных днях и времени |
| 19 | Переключить язык на «Русский» и «Қазақша» | весь интерфейс, курсы и ошибки на выбранном языке |
| 20 | Войти как `teacher@kbtu.kz` → курс → Register | «Access denied! Insufficient permissions.» |
| 21 | Остановить сервер (Ctrl+C) и нажать All Courses | «Cannot connect to the server…» и кнопка «Try again» |

### Известные ограничения

- Токен в `sessionStorage` доступен JavaScript-коду страницы: при XSS-уязвимости его можно
  украсть. Риск снижен тем, что все данные с сервера экранируются (`esc()`), а токен живёт 30 минут
  и отзывается при выходе. Вариант для продакшена — httpOnly-cookie + защита от CSRF.
- Refresh-токенов нет: через 30 минут нужно войти снова (как в исходной версии).
- После обновления страницы открывается панель (Home), а не последняя открытая страница
  (как в исходной версии — маршрутизации по URL нет).
- Состояние записи обновляется при переходе между страницами и после действий, а не в реальном
  времени: если место заняли в другой вкладке, сервер всё равно откажет с понятной ошибкой.
- Отдельных экранов для преподавателя и администратора пока нет — это следующая фаза
  (API уже готов).
- Мои браузерные тесты в среде разработки выполнялись против тестового сервера, который
  повторяет контракт API на тех же модулях бизнес-логики; против настоящего бэкенда их нужно
  запустить по инструкции выше.

## Запись на курсы (Фаза 4)

Все четыре эндпоинта доступны **только студентам** (teacher и admin получают 403 `auth.denied`).
Студент всегда берётся из JWT: в URL и в теле запроса нет id пользователя, поэтому создать,
посмотреть или отменить чужую запись невозможно.

### `POST /api/me/registrations` — записаться

Тело: `{"courseId": 1}` — и больше ничего. День, время, аудитория и преподаватель — это
фиксированное расписание курса; попытка передать `day`, `start`, `instructor`, `section`,
`userId` и т.п. даёт 422 `err.validation`.

Ответ **201**: курс в формате каталога с обновлённым `seatsLeft` и временем записи `registeredAt` (UTC).

Проверки — в том же порядке, что и в исходном `CourseAPI.canRegister`:

| HTTP | `code` | Когда |
|---|---|---|
| 404 | `err.notFound` | курса нет |
| 409 | `err.alreadyRegistered` | студент уже записан на этот курс |
| 409 | `err.noSeats` | свободных мест нет |
| 409 | `err.conflict` `{name, code, courseId}` | пересечение с курсом, на который студент уже записан |

Все эти коды уже есть в `js/i18n.js`. Для `err.conflict` параметр `name` содержит все три языка
(`{"en": "Statistics", "ru": "Статистика", "kk": "Статистика"}`) — фронтенд выберет нужный через `loc()`.

**Пересечение:** два занятия пересекаются, только если в один день одно начинается раньше, чем
кончается другое. Занятия «встык» (одно до 10:00, другое с 10:00) разрешены.
В исходном расписании ровно три пары пересекаются: STAT201 / CS330 (пн),
MATH301 / UX201 (вт), CS250 / ECON101 (пт).

### `POST /api/me/registrations/check` — проверить без записи

Тело то же. Ответ 200 `{"ok": true, "seatsLeft": 20}` или **та же ошибка**, что вернул бы
`POST /api/me/registrations`. Ничего не сохраняет (аналог `canRegister` перед окном подтверждения).

### `GET /api/me/registrations` — мои курсы

```json
{"courses": [ {...курс..., "seatsLeft": 19, "registeredAt": "2026-11-13T08:15:02.123456"} ],
 "count": 1, "totalCredits": 5}
```

Курсы в порядке каталога (по id), как в `myCourses()` фронтенда.

### `DELETE /api/me/registrations/{course_id}` — отменить запись

Ответ **204**. Если студент не был записан, тоже 204 (ничего не меняется — как в исходном
фронтенде). 404 `err.notFound`, если курса не существует. Удаляется только запись самого студента.

### Защита от переполнения курса

Запись выполняется **одним атомарным SQL-оператором** `INSERT … SELECT … WHERE`, который вставляет
строку, только если в момент записи: аккаунт — студент, `число записей < seats`, нет пересечения
с курсами этого студента. SQLite выполняет оператор записи, удерживая блокировку записи базы,
поэтому между «проверить» и «записать» ничего не может измениться: два одновременных запроса
не займут одно последнее место. Повторная запись блокируется ограничением
`UNIQUE (user_id, course_id)`. Перед вставкой выполняется обычная проверка, чтобы вернуть понятную
ошибку; если за это время ситуация изменилась, вставка не происходит и ошибка определяется заново.
Это проверено тестами: 60 параллельных запросов на 10 мест дают ровно 10 записей.

### Изменения администратора

Администратор не может перенести курс на время, когда у уже записанного студента идёт другой
его курс: 409 `err.studentScheduleConflict` `{count}` (count — число таких студентов).
Курс с записанными студентами нельзя удалить (409 `err.courseHasRegistrations`) и нельзя уменьшить
число мест ниже числа записанных (409 `err.seatsBelowRegistered`).

## Схема базы данных

```
users                          courses                                  registrations
─────────────────────          ───────────────────────────────          ─────────────────────
id            PK               id             PK (AUTOINCREMENT)        id         PK
name                           code           UNIQUE                    user_id    FK → users.id   (CASCADE)
student_id    UNIQUE NULL      category                                 course_id  FK → courses.id (RESTRICT)
email         UNIQUE           name_en / name_ru / name_kk              created_at
password_hash                  description_en / _ru / _kk               UNIQUE (user_id, course_id)
role          CHECK            teacher_id     FK → users.id (RESTRICT)
created_at                     credits, day, start_time, end_time
                               room_kind, room_no, seats
login_attempts                 created_at, updated_at
revoked_tokens (user_id FK → users.id CASCADE)
```

- **Преподаватель ↔ курсы**: `courses.teacher_id` → `users.id`, один преподаватель — много курсов.
  Имя преподавателя не хранится в курсе отдельным текстом: `instructor` в ответе API — это имя
  связанного аккаунта. Назначить курс можно только аккаунту с ролью teacher (проверка в сервисе).
  `ON DELETE RESTRICT`: аккаунт преподавателя с курсами удалить нельзя.
- **Тексты на трёх языках** — отдельные обязательные колонки `*_en`, `*_ru`, `*_kk`.
- **`registrations`** — записи студентов на курсы (Фаза 4). `UNIQUE (user_id, course_id)` запрещает
  дубли, `RESTRICT` не даёт удалить курс с записанными студентами, `CASCADE` удаляет записи вместе
  с аккаунтом студента. Свободные места = `seats` − число строк этого курса.
- **AUTOINCREMENT** у курсов: id удалённого курса никогда не выдаётся повторно (фронтенд опирается
  на id — например, фото преподавателя для курса 21).

Ограничения CHECK в таблице `courses` (действуют, даже если обойти API):

| Ограничение | Правило |
|---|---|
| `ck_courses_code_length` | длина кода 5–10 символов |
| `ck_courses_category` | `cs`, `math`, `languages`, `physics`, `economics`, `design` (для них есть переводы во фронтенде) |
| `ck_courses_names_present` / `ck_courses_descriptions_present` | все три языка не пустые |
| `ck_courses_credits` | 1–10 |
| `ck_courses_day` | `mon`–`fri` |
| `ck_courses_time_format` | время в формате `ЧЧ:ММ` |
| `ck_courses_time_order` | начало раньше конца |
| `ck_courses_room_kind` / `ck_courses_room_no` | `room` или `lab`; номер 1–10 символов |
| `ck_courses_seats` | 1–500 |

Правила, которые проверяет сервис (их нельзя выразить простым CHECK): преподаватель не может
вести два курса в пересекающееся время; аудитория не может быть занята двумя курсами одновременно
(курсы «встык», например 09:00–10:50 и 10:50–12:00, допускаются); число мест нельзя сделать
меньше числа записанных студентов.

**Почему поиск выполняется в Python, а не в SQL:** в SQLite функции `LOWER()` и `LIKE` без учёта
регистра работают только для латиницы, поэтому поиск «программ» или «ҚАЗАҚ» в SQL не нашёл бы
курсы. Каталог небольшой, поэтому курсы загружаются одним запросом, а фильтрация и сортировка
(с правильным порядком казахских букв ә, ғ, қ, ң, ө, ұ, ү, һ, і) выполняются в Python.

Коды ошибок совпадают с ключами перевода в `js/i18n.js`:

| HTTP | `code` | Когда |
|---|---|---|
| 401 | `auth.invalid` `{n}` | неверный email или пароль; `n` — оставшиеся попытки |
| 429 | `auth.locked` `{seconds}` | аккаунт временно заблокирован (+ заголовок `Retry-After`) |
| 409 | `auth.emailTaken` / `auth.idTaken` | email или студенческий ID уже заняты |
| 401 | `auth.loginFirst` | нет токена, токен неверный или отозван |
| 401 | `auth.sessionExpired` | срок токена истёк |
| 403 | `auth.denied` | недостаточно прав |
| 422 | `err.validation` `{fields}` | неверные входные данные (значения полей не возвращаются) |

## Безопасность: как это устроено

- **Пароли** — PBKDF2-HMAC-SHA256, 600 000 итераций (рекомендация OWASP), случайная
  16-байтовая соль для каждого пароля, сравнение за постоянное время. Формат:
  `pbkdf2_sha256$600000$<соль>$<хеш>`. Хеши со старым, меньшим числом итераций
  автоматически обновляются при следующем входе.
- **Блокировка** хранится в базе (таблица `login_attempts`), а не в браузере. Счётчик ведётся
  по email, в том числе для несуществующих адресов, а для неизвестного email всё равно
  выполняется полная проверка хеша — по ответу и времени ответа нельзя узнать, зарегистрирован ли email.
  Попытки входа обрабатываются последовательно, поэтому параллельные запросы не могут
  «проскочить» мимо счётчика.
- **RBAC** — роль всегда берётся из базы данных, а не из токена: если администратор изменит роль,
  это действует сразу, даже для уже выданных токенов. Публичная регистрация создаёт только студентов;
  преподавателей и администраторов создаёт администратор.
- **JWT** — HS256, обязательные поля `sub`, `jti`, `iat`, `exp`, `type`; токены с `alg: none`,
  чужой подписью или изменённым содержимым отклоняются.

### Выход и ограничения JWT

JWT — «stateless» токен: сервер проверяет подпись и срок, но сам по себе не может
«забыть» уже выданный токен. Поэтому реализован **отзыв токенов**:

- у каждого токена уникальный `jti`; `POST /api/auth/logout` записывает его в таблицу
  `revoked_tokens`, и все дальнейшие запросы с этим токеном получают 401;
- выход завершает только текущую сессию (другой браузер с другим токеном остаётся в системе);
- записи об отозванных токенах удаляются после истечения их срока — таблица не растёт бесконечно.

Оставшиеся ограничения (приемлемые для учебного проекта):

- если токен украден до выхода, он действует до выхода владельца или максимум 30 минут;
- refresh-токенов нет: через 30 минут нужно войти заново (так же, как в исходном фронтенде);
- последовательная обработка входов работает в рамках одного процесса uvicorn — именно так
  запускается этот проект; для нескольких процессов понадобилась бы блокировка на уровне базы;
- минимальная длина пароля — 6 символов, как в форме регистрации фронтенда; демо-пароли
  простые и предназначены только для демонстрации.

## Структура

```
backend/
├── app/
│   ├── main.py            # создание приложения, CORS, роутеры /api, раздача фронтенда
│   ├── config.py          # настройки из .env, проверка SECRET_KEY
│   ├── database.py        # SQLAlchemy engine, сессии, init_db / close_db
│   ├── models.py          # User, Course, Registration, LoginAttempt, RevokedToken
│   ├── roles.py           # Role: student / teacher / admin
│   ├── schemas.py         # проверка входных данных и формат ответов
│   ├── security.py        # PBKDF2 и JWT
│   ├── deps.py            # get_current_user, require_roles(...)
│   ├── errors.py          # единый формат ошибок
│   ├── seed.py            # python -m app.seed
│   ├── seed_data.py       # 21 исходный курс и 16 преподавателей (сверяется с js/api.js тестом)
│   ├── services/
│   │   ├── auth.py        # регистрация, вход с блокировкой, выдача и отзыв токенов
│   │   ├── lockout.py     # правила блокировки (чистые функции)
│   │   ├── catalog.py     # поиск, фильтры, сортировка, пересечение времени (чистые функции)
│   │   ├── courses.py     # курсы в базе: места, создание/изменение/удаление, конфликты
│   │   ├── enrollment.py  # правила записи и атомарный SQL записи (чистый модуль)
│   │   └── registrations.py # запись / отмена / мои курсы (база данных)
│   └── routers/
│       ├── health.py      # /api/health
│       ├── auth.py        # /api/auth/...
│       ├── courses.py     # /api/courses...
│       ├── me.py          # /api/me/registrations...
│       ├── teacher.py     # /api/teacher/courses
│       └── admin.py       # /api/admin/users, /api/admin/courses
├── tests/                 # pytest (517 тестов)
├── e2e/                   # браузерные тесты Playwright (запускаются отдельно)
├── requirements.txt
├── pytest.ini
└── .env.example
```
