# Weeping Ghosts — Eve Echoes Discord Bot

Полнофункциональный Discord-бот для корпорации **Weeping Ghosts** в Eve Echoes.

---

## ✨ Возможности

| Модуль | Команды |
|---|---|
| **Регистрация** | `/register` `/whois` |
| **Баланс & ISK** | `/balance` `/deposit` `/transactions` |
| **Очки (PvP/PvE)** | `/kill_submit` `/points` `/leaderboard` |
| **Заказы** | `/orders` `/order_add` `/order_take` `/order_complete` `/order_approve` |
| **Товары** | `/goods` `/good_add` `/good_restock` `/buy` |
| **Компенсации** | `/compensation_claim` `/compensation_approve` `/compensation_reject` `/compensation_list` |
| **ИИ-агент** | `/ask` `/ask_clear` |
| **Калькуляторы** | `/calc_profit` `/calc_implant` `/calc_mining` `/calc_production` `/calc_help` |
| **Киллборд** | `/killboard` `/kills` |
| **Администрирование** | `/admin_grant_isk` `/admin_deduct_isk` `/admin_grant_points` `/admin_deduct_points` `/admin_grant_role` `/admin_revoke_role` `/admin_members` `/admin_verify` |
| **Авторасширение ролей** | `/sync_roles` `/reward_roles` |

---

## 🚀 Быстрый старт

### 1. Предварительные требования

- Python 3.11+
- [Discord-приложение](https://discord.com/developers/applications) с включёнными привилегиями: **Server Members Intent** и **Message Content Intent**
- (Опционально) OpenAI API ключ для OCR на базе GPT-4o и ИИ-агента

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Настройка

```bash
cp .env.example .env
# Заполни DISCORD_TOKEN, GUILD_ID и OPENAI_API_KEY
nano .env
```

### 4. Запуск

```bash
python main.py
```

---

## 📁 Структура проекта

```
├── main.py                  # Точка входа
├── requirements.txt
├── .env.example
└── bot/
    ├── config.py            # Настройки из .env
    ├── database.py          # SQLite + aiosqlite
    ├── cogs/
    │   ├── registration.py  # Регистрация по скриншоту
    │   ├── economy.py       # ISK баланс и зачисление
    │   ├── points.py        # PvP/PvE очки
    │   ├── orders.py        # Заказы корпорации
    │   ├── goods.py         # Товары корпорации
    │   ├── compensation.py  # Компенсация за корабль
    │   ├── ai_agent.py      # ИИ-ассистент
    │   ├── calculators.py   # Калькуляторы
    │   ├── killboard.py     # Киллборд
    │   ├── admin.py         # Административные команды
    │   └── auto_roles.py    # Авторасширение ролей
    └── utils/
        ├── ocr.py           # OCR по скриншотам
        └── helpers.py       # Общие утилиты
```

---

## 🤖 OCR и скриншоты

Бот использует **GPT-4o Vision** (по умолчанию) для анализа скриншотов из Eve Echoes.

Поддерживаемые типы скриншотов:
- Страница персонажа (регистрация)
- Кошелёк / транзакция (зачисление ISK)
- Килл-мейл / лог боя (очки PvP/PvE)
- Уведомление о потере корабля (компенсация)

Для переключения на локальный Tesseract OCR установи `OCR_BACKEND=tesseract` в `.env`
и выполни `pip install pytesseract`.

---

## ⚙️ Переменные окружения

| Переменная | Описание |
|---|---|
| `DISCORD_TOKEN` | Токен Discord-бота |
| `GUILD_ID` | ID сервера Discord |
| `OPENAI_API_KEY` | Ключ OpenAI API |
| `OPENAI_MODEL` | Модель OpenAI (по умолчанию `gpt-4o`) |
| `OCR_BACKEND` | `openai` или `tesseract` |
| `MEMBER_ROLE_ID` | ID роли для участников |
| `VERIFIED_ROLE_ID` | ID роли для верифицированных |
| `ADMIN_ROLE_ID` | ID роли администратора |
| `REWARD_ROLES` | Пороги ISK и ID ролей-наград |
| `KILLBOARD_CHANNEL_ID` | Канал для публичного киллборда |
| `LOG_CHANNEL_ID` | Канал для логов (админ) |
| `COMPENSATION_RATE` | Коэффициент компенсации (0–1) |
| `DB_PATH` | Путь к базе данных SQLite |

---

## 📜 Лицензия

MIT
