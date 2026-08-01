# Central License Server — Deployment Guide (Render.com + Supabase)

This central server manages outlet auto-activations, machine pings, and payment approvals for the Meat Products of India Billing App.

---

## 1. Supabase Setup (PostgreSQL Database)
1. Sign up / Log in to [Supabase.com](https://supabase.com).
2. Create a new project named `mpi-license-db`.
3. Under **Project Settings -> Database**, copy the **URI Connection String** (e.g. `postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres`).

---

## 2. Render.com Setup (Web Service)
1. Sign up / Log in to [Render.com](https://render.com).
2. Click **New +** -> **Web Service**.
3. Connect your Git Repository or upload the `cloud_license_server` directory.
4. Configure Build & Start settings:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r cloud_license_server/requirements.txt`
   - **Start Command**: `gunicorn cloud_license_server.app:app`
5. Add Environment Variables:
   - `DATABASE_URL`: Your Supabase connection string from Step 1.
   - `ADMIN_PASSWORD`: Your secret developer password for logging into the portal (e.g. `Admin@5000`).
6. Click **Create Web Service**. Your server URL will be live (e.g., `https://mpi-license-server.onrender.com`).

---

## 3. How to Use:
1. When a customer pays ₹5,000 via UPI, open your Render URL (e.g., `https://mpi-license-server.onrender.com`).
2. Log in with your `ADMIN_PASSWORD`.
3. Locate the customer's outlet name / Machine ID in the table.
4. Click **`⚡ Approve 1 Year (₹5000)`**.
5. As soon as the customer's desktop app connects online, it will automatically detect your approval and activate for 365 days!
