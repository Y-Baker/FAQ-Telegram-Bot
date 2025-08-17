# Telegram FAQ Bot

A simple FAQ bot for Telegram that allows users to quickly search for answers to common questions. Admins can manage the FAQ database by adding, updating, deleting, and retrieving entries.

---

## Features

- Search for FAQs directly in Telegram.
- Admin commands to manage FAQ entries.
- SQLite database for lightweight storage and Cache for faster fetching.
- Docker support for easy deployment.

---

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/QA-Telegram.git
   cd QA-Telegram
   ```

2. Complete a `.env` file in the project root using `.env.example`:

   ```env
   # .env.example -> copy to .env and fill values
   BOT_TOKEN=123456:ABC-DEF-...

   DB_PATH=/app/data/faq.db

   ADMIN_IDS=12345678,87654321

   MENTION_THRESHOLD=60
   NORMAL_THRESHOLD=70

   QA_CACHE_TTL=30
   QA_CACHE_AUTO_REFRESH=false
   QA_CACHE_AUTO_INTERVAL=120

   APOLOGY_MSG="عذراً، لا أملك إجابة على هذا السؤال. يمكنك التواصل مع الدعم."

   ```

3. Build the Docker image:

   ```bash
   docker compose build
   ```

4. Run migrations (to set up the database):

   ```bash
   docker compose run --rm migrate
   ```

5. Start the bot:

   ```bash
   docker compose up -d faq-bot
   ```

---

## Development (without Docker)

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Run migrations:

   ```bash
   python src/cli.py --migrate data/qa.json
   ```

3. Start the bot:

   ```bash
   python -m src.bot
   ```

---

## Usage (الاستخدام)

[Bot_Telegram](https://t.me/MU_ME_bot)

### 📌 كـ مستخدم عادي:

- في الجروب
  - يقوم البوت بالرد علي الاسئلة الواضحه فقط .
  - اذا اتعمل منشن او ريبلاي سوف يقوم بالرد علي السؤال او يعتذر اذا لم يعرف اجابه
- في شات البوت الخاص
  - يمكن ان تسال البوت كما تشاء
  - يمكن الحصول علي ال id بسهوله من خلال امر /lookup

### 📌 كـ مسؤول (Admin):

يمكن استخدام اوامر ال (Admin) فقط في شات الوت الخاص

1. **إضافة سؤال وإجابة جديدة**

   ```
   /add_qna
   ```

2. **تعديل سؤال او اجابه باستخدام المعرف (ID):**

   ```
   /update_qna
   ```

3. **حذف سؤال باستخدام المعرف (ID):**

   ```
   /delete_qna
   ```

4. **عرض جميع الأسئلة مع معرفاتها:**

   ```
   /list_qas
   ```

5. **عرض سؤال وإجابته باستخدام المعرف (ID):**

   ```
   /get_qna {id}
   ```

---
