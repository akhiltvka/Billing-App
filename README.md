# Meat Products of India — Billing & Inventory Management App

Flask-based Billing and Inventory Management System with role-based access control, batch tracking (FEFO), credit sales, dual unit conversion, and accounts receivable/payable management.

---

## Environment Setup & Secret Key

1. Copy `.env.example` to `.env` or set environment variables before running:
   ```bash
   export APP_SECRET_KEY="your_secure_random_secret_key_here"
   export DB_PATH="data/meatshop.db"
   ```

2. If `APP_SECRET_KEY` is not configured, the app will display a console warning and fallback to a default secret key for local development.

---

## Scheduled Automated Database Backups

The project includes a standalone backup script `backup_scheduler.py` that copies the database file into a timestamped file inside `backups/` and automatically deletes backup files older than 30 days.

### 1. Setting up on Linux / macOS (Cron Job)
Add a entry to your user crontab (`crontab -e`) to execute daily at 2:00 AM:
```cron
0 2 * * * /usr/bin/python3 /path/to/Billing\ and\ Inventory\ App/backup_scheduler.py >> /path/to/Billing\ and\ Inventory\ App/backups/backup.log 2>&1
```

### 2. Setting up on Windows (Task Scheduler)
1. Open **Task Scheduler** (`taskschd.msc`).
2. Click **Create Basic Task...** and name it `MPI_Daily_Database_Backup`.
3. Set Trigger to **Daily** at your preferred time (e.g. 2:00 AM).
4. Set Action to **Start a program**:
   - **Program/script**: `python.exe` (or full path like `C:\Python312\python.exe`)
   - **Add arguments**: `backup_scheduler.py`
   - **Start in**: `D:\Programs - New\Billing and Inventory App`
5. Click **Finish**. You can right-click the task and select **Run** to test manually.
