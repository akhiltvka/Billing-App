# Meat Products of India — Billing & Inventory Management App

Flask-based Billing and Inventory Management System with role-based access control, batch tracking (FEFO), credit sales, dual unit conversion, and accounts receivable/payable management.

---

## Environment Setup & Secret Key

1. Copy `.env.example` to `.env` or set environment variables before running:
   ```bash
   export APP_SECRET_KEY="your_secure_random_secret_key_here"
   export DB_PATH="data/meatshop.db"
   ```

2. If `APP_SECRET_KEY` is not configured, the desktop app creates and persists a random local secret under the application data directory. Set `APP_SECRET_KEY` explicitly for managed deployments.

For cloud-backed licensing and encrypted backups, configure these additional variables in the outlet application's environment:

```text
CLOUD_LICENSE_SERVER_URL=https://your-license-server.example.com
CLOUD_LICENSE_API_TOKEN=<same 32+ character token configured as OUTLET_API_TOKEN>
CLOUD_BACKUP_TOKEN=<same 32+ character token configured as BACKUP_UPLOAD_TOKEN>
CLOUD_BACKUP_ENCRYPTION_KEY=<Fernet key configured as BACKUP_ENCRYPTION_KEY>
```

Generate a Fernet key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and store it in a secrets manager. Losing this key prevents recovery of encrypted cloud backups.

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

---

## Building Standalone Installers (.exe)

- **Standard Windows 10/11 (64-bit)**: Run `build_exe.bat` to generate `dist\MPI_Billing_Software_Installer.exe`.
- **Legacy Windows 7 / 8 (32-bit x86)**: Run `build_win7_32bit.bat` to generate `dist\MPI_Billing_Software_Installer_Win7_32bit.exe`. See [WINDOWS7_32BIT_BUILD_GUIDE.md](file:///d:/Programs%20-%20New/Billing%20and%20Inventory%20App/WINDOWS7_32BIT_BUILD_GUIDE.md) for details.

