# Automation Hub Auth & Management Server (Vercel + Neon Edition)

Full-stack **Next.js** Serverless backend for the **PyQt5 Desktop Automation Hub** with **Neon PostgreSQL** database.

Designed specifically for zero-config **1-click deployment on Vercel** with connection pooling, modern dark-themed administration console, and 100% backward compatibility with desktop client `.php` API requests.

---

## 🚀 Features (100% Parity with PHP Backend)

- **Authentication & Security:**
  - Bcrypt password hashing (`bcryptjs`)
  - HMAC-SHA256 JWT access tokens (15m TTL) & secure refresh tokens (7d TTL)
  - Hardware Fingerprint (Device ID & PC Name) registration and binding via WMI
  - Single active session enforcement (`single_session`)
  - Rate limiting (5 attempts/min on login)
  - Application key protection (`X-App-Key`)
- **Real-Time Monitoring:**
  - 45-second heartbeat loop
  - Remote killswitch: immediate lock on user ban or Force Logout
  - Live link logging: captures every URL submitted in the desktop app
  - Audit trail of administrative actions and login history
- **Administration Dashboard:**
  - Modern dark-themed UI built with Tailwind CSS and Lucide icons
  - Real-time metrics: Online sessions, Links today, Registered devices
  - User management: Create, ban/unban, disable/enable, reset password, update license
  - Live Link Logs viewer with search, copy-to-clipboard, and external link
  - Active Sessions manager with one-click "Force Logout"
  - Device authorization manager
  - Security & session settings
- **Automatic .php Rewrites:**
  - Desktop client calls `/api/login.php`, `/api/heartbeat.php`, etc.
  - Vercel automatically rewrites these to `/api/login`, `/api/heartbeat` with zero code changes needed on the client.

---

## 🛠️ Step-by-Step Vercel & Neon Deployment

### 1. Create a Neon PostgreSQL Database
1. Go to [Neon.tech](https://neon.tech) and create a free account.
2. Create a new project (e.g. `automation-auth`).
3. Copy your connection string (e.g. `postgres://user:pass@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require`).

### 2. Deploy to Vercel
1. Push this `server-vercel` folder to a GitHub repository.
2. Open [Vercel](https://vercel.com) and click **"Add New Project"**.
3. Import your repository.
4. Under **Environment Variables**, add:
   - `DATABASE_URL`: Your Neon PostgreSQL connection string (pooled recommended).
   - `JWT_SECRET`: A secure random string (64+ chars).
   - `APP_API_KEY`: Secret matching your desktop app (default: `dev-desktop-app-key-change-me`).
   - `SESSION_SECRET`: Random string for admin cookies.
5. Click **"Deploy"**.

### 3. Initialize Database Schema
Once deployed, initialize the tables with a single click:
- Visit in your browser:  
  `https://your-vercel-app.vercel.app/api/setup?secret=YOUR_APP_API_KEY`
- This runs `schema.sql` on Neon and creates the default superadmin:
  - **Username:** `superadmin`
  - **Password:** `Admin@12345`

### 4. Configure Desktop App
In the desktop app `config.json`, set:
```json
"auth": {
  "enabled": true,
  "api_base": "https://your-vercel-app.vercel.app",
  "app_key": "same-as-Vercel-APP_API_KEY",
  "heartbeat_seconds": 45,
  "verify_ssl": true
}
```

---

## 💻 Local Testing

```bash
# 1. Install dependencies
npm install

# 2. Copy .env.example to .env and set your DATABASE_URL
cp .env.example .env

# 3. Initialize database
npm run db:init

# 4. Start development server
npm run dev
```

Open [http://localhost:3000/admin](http://localhost:3000/admin) to log in to the admin panel.
