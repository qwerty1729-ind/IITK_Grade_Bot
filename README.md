# IITK Grade Bot 📊

A comprehensive Telegram bot that provides detailed grade distribution data for courses at IITK.

**➡️ Try the live bot here: [@gradiator_iitk_bot](https://t.me/gradiator_iitk_bot)**

---

## Features

* **📚 Course & Professor Search:** Instantly find grade statistics by course code, title, or professor's name.
* **📈 Detailed Grade Stats:** View the exact number and percentage of students for each grade.
* **🖼️ Visual Plots:** Automatically sends a plot image visualizing the grade distribution for quick analysis.
* **📢 Admin Broadcast System:** A background broadcasting system for admins to send messages to all subscribed users.
* **🚀 Fully Containerized:** The entire application stack is managed with Docker Compose for seamless deployment.

---

## Tech Stack

* **Backend:** FastAPI, Python 3.11
* **Database:** PostgreSQL & Alembic
* **Bot Framework:** `python-telegram-bot`
* **Async Task Queue:** Celery & Redis
* **Containerization:** Docker & Docker Compose