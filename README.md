# School Access & Meal Attendance

RFID-based school entry tracking and class-grouped meal attendance — MVP
implementation of the `school_access_schema.sql` spec. Django 6 + Django
Ninja + PostgreSQL.

## Стек

- **Django 6** — ORM, admin, серверний рендеринг сторінок
- **Django Ninja** — typed JSON API для ESP32-сканів і звітів (`/api/docs`)
- **PostgreSQL** — таблиці `school_access.*` (реальна виділена схема)
- **Tailwind CDN** — верстка без збірки/npm

## Перший запуск

Потрібні: Python 3.12+, Docker Desktop.

```bash
pip install -r requirements.txt
cp .env.example .env          # і за потреби відредагуй значення (в т.ч. TELEGRAM_*)
docker compose up -d          # піднімає Postgres на localhost:5432
python manage.py migrate      # створює схему school_access + довідники
python manage.py seed_users   # створює хардкоджені акаунти admin/guard (див. нижче)
```

## Ролі та вхід

Немає самореєстрації — два хардкоджені акаунти, створені `seed_users`:

| Роль | Логін | Пароль (дефолт) | Доступ |
|---|---|---|---|
| Адмін | `admin` | `Admin#2026` | Все: дашборд + CRUD (учні, класи, охорона, картки, звіти, налаштування) + `/admin/` |
| Охорона | `guard` | `Guard#2026` | Лише `/` (дашборд), read-only |

Вхід — `/login/` (кастомна форма, не `/admin/login/`). Змінити паролі:
`python manage.py seed_users --admin-password "..." --guard-password "..."`,
або через `/admin/` (доступний лише `admin`, бо тільки в нього `is_staff`/`is_superuser`).

## Запуск (2 термінали)

**Термінал 1 — сервер** (лишається відкритим):
```bash
python manage.py runserver 0.0.0.0:8000
```
`0.0.0.0`, а не `127.0.0.1` — інакше RFID-зчитувач по Wi-Fi не достукається.

**Термінал 2 — одноразові/допоміжні команди**, поки сервер працює:
```bash
python manage.py shell
python manage.py import_students students.csv --academic-year "2026/2027"
```

Відкрити:
- `http://127.0.0.1:8000/` — дашборд
- `http://127.0.0.1:8000/api/docs` — Swagger

## Екрани

| URL | Призначення |
|---|---|
| `/` | Дашборд: присутні/відсутні сьогодні, харчовий список, картки |
| `/students/` | Список учнів, додавання/редагування |
| `/students/import/` | Імпорт учнів з CSV |
| `/classes/` | Навчальні роки та класи |
| `/guard/` | Ручний запис входу (без картки) |
| `/cards/` | Прив'язка/заміна RFID-картки |
| `/reports/meal/` | Харчовий звіт по класах + CSV-експорт |
| `/settings/` | Час щоденного Telegram-звіту, кнопка "надіслати зараз" |
| `/admin/` | Django admin — CRUD усіх таблиць |

Усі сторінки, крім дашборду, доступні лише `admin` (див. "Ролі та вхід").

## Щоденний звіт у Telegram

Кожного дня, коли настає час, вказаний на `/settings/` (адміном), і звіт
за сьогодні ще не надсилався, команда `send_daily_report` формує та шле в
Telegram повідомлення виду:

```
Звіт відвідуваності — 07.08.2026

Клас - 5-А
Кількість - 23
Клас - 5-Б
Кількість - 19

Загалом: 42
```

"Кількість" — учні, присутні за даними охорони (`AttendanceDaily`) на
момент запуску команди.

Команда сама по собі нічого не планує — вона лише перевіряє, чи настав
час, і виходить, якщо ні, або якщо вже надсилала сьогодні. Тому її треба
запускати періодично (кожні 5 хв) через **Windows Task Scheduler**:

```powershell
schtasks /create /tn "SchoolRFID Daily Report" /sc minute /mo 5 ^
  /tr "\"C:\path\to\venv\Scripts\python.exe\" \"C:\Users\user\My_Works\SCHOOL-RFID\manage.py\" send_daily_report" ^
  /st 07:00
```

(Онови шлях до `python.exe` під свій venv, і `/st` — час, з якого Task
Scheduler починає день опитувань.) Або через GUI: Task Scheduler →
Create Task → Trigger "Daily, repeat every 5 minutes" → Action "Start a
program" → вкажи `python.exe` і аргументи `manage.py send_daily_report`
з робочою директорією проєкту.

Налаштування бота — `TELEGRAM_BOT_TOKEN` (від @BotFather) і
`TELEGRAM_CHAT_ID` в `.env` (див. `.env.example`).

## Імпорт учнів (CSV)

Заголовок + колонки `last_name,first_name,class_name,meal_option_code`
(`meal_option_code` необов'язковий, дефолт `STANDARD`):

```csv
last_name,first_name,class_name,meal_option_code
Іваненко,Іван,5-А,STANDARD
Петренко,Марія,5-А,NO_MEAL
```

Через веб — `/students/import/`, через термінал:
```bash
python manage.py import_students students.csv --academic-year "2026/2027"
```

## RFID-прошивка (ESP32 + PN532)

`firmware/school-rfid/school-rfid.ino`. Перед прошивкою заповнити в шапці
файлу:

- `networks[]` — свій Wi-Fi (SSID/пароль)
- `SERVER_HOST`, `SERVER_PORT` — де крутиться Django (LAN IP машини для
  локального тесту, `0.0.0.0:8000` на сервері)
- `READER_CODE` — має збігатись зі значенням `code` рядка в `rfid_readers`
  (сідиться `VESTIBULE_ENTRY_1` за замовчуванням)
- `HMAC_SECRET` — має дорівнювати `CARD_SCAN_API_KEY` з `.env` сервера

⚠️ Файл із заповненими реальними Wi-Fi-паролем/ключем **не комітити** —
тримати робочу копію локально поза git або через окремий незакомічений
конфіг.

## Верифікація/тести

Формальних unit-тестів поки немає; логіка перевірялась вручну через
`manage.py shell` (сценарії скану/дублю/відвідуваності, CRUD, guard-flow)
і Django test client. `python manage.py check` — базова перевірка
цілісності проєкту.

## Структура

```
school_rfid_project/   # settings, urls, wsgi
school_access/
  models.py             # 12 таблиць схеми school_access + DailyReportSettings
  admin.py               # Django admin для всіх моделей
  auth.py                 # admin_required — гейт для CRUD-сторінок (роль admin)
  selectors.py              # звітні запити (харчовий звіт, присутні/відсутні, ...)
  services/                  # бізнес-логіка: scan-обробка, картки, учні, імпорт,
                              # telegram_report (щоденний звіт)
  api.py                      # Django Ninja: /api/access/*, /api/cards/*, /api/reports/*
  views.py, urls.py            # сторінки: дашборд, логін, учні, класи, охорона,
                                # картки, звіти, налаштування
  management/commands/          # import_students, seed_users, send_daily_report
firmware/school-rfid/          # прошивка ESP32
school_access_schema.sql       # еталонна SQL-специфікація
docker-compose.yml              # локальний Postgres
```
