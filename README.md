# KBTU University Information System

Онлайн-расписание и запись на курсы KBTU: фронтенд на HTML/CSS/JavaScript
(`online-class-schedule/`) и бэкенд на FastAPI + SQLite + SQLAlchemy + JWT (`backend/`).
Интерфейс на казахском, русском и английском.

## Быстрый старт (Windows PowerShell)

```powershell
cd путь\к\KBTU-University-Information-System\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # при ошибке: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # вставьте в SECRET_KEY= в файле .env
notepad .env
python -m app.seed                    # таблицы, 21 курс, демо-аккаунты
uvicorn app.main:app --reload
```

Приложение: <http://127.0.0.1:8000> · API: <http://127.0.0.1:8000/api/docs>

Демо-вход: `student@kbtu.kz` / `student123` (студент), `teacher@kbtu.kz` / `teacher123`
(преподаватель), `admin@kbtu.kz` / `admin123` (администратор).

Тесты: `pytest` в папке `backend` (517 тестов). Подробности, браузерные тесты, чек-лист ручной
проверки и ограничения — в [backend/README.md](backend/README.md).
