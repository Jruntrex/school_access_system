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
cp .env.example .env          # і за потреби відредагуй значення
docker compose up -d          # піднімає Postgres на localhost:5432
python manage.py migrate      # створює схему school_access + довідники
python manage.py createsuperuser
```

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
| `/admin/` | Django admin — CRUD усіх 12 таблиць |

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
  models.py             # 12 таблиць схеми school_access
  admin.py               # Django admin для всіх моделей
  selectors.py             # звітні запити (харчовий звіт, присутні/відсутні, ...)
  services/                 # бізнес-логіка: scan-обробка, картки, учні, імпорт
  api.py                     # Django Ninja: /api/access/*, /api/cards/*, /api/reports/*
  views.py, urls.py           # сторінки: дашборд, учні, класи, охорона, картки, звіт
  management/commands/         # import_students
firmware/school-rfid/          # прошивка ESP32
school_access_schema.sql       # еталонна SQL-специфікація
docker-compose.yml              # локальний Postgres
```
