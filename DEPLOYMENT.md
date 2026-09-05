# Deploying Datavox to Render

This guide walks you through deploying your **Datavox** data assistant to [Render](https://render.com) so anyone can access it online with an HTTPS URL and provide their own API key (Gemini or OpenAI).

---

## 📋 Prerequisites
1. A **GitHub account** ([github.com](https://github.com)).
2. A free **Render account** ([render.com](https://render.com)).
3. A **Google Gemini API Key** (Free from [Google AI Studio](https://aistudio.google.com/app/apikey)) or an **OpenAI API Key**.

---

## 🚀 Step-by-Step Deployment

### Step 1: Push Your Code to GitHub

If you haven't committed your local changes yet, run in your terminal:
```bash
git add .
git commit -m "Deploy Datavox with BYOK API key support and Render deployment"
git push origin main
```

*(Note: `.env` is already in `.gitignore`, so your private keys will NOT be committed).*

---

### Step 2: Deploy on Render

#### Option A: One-Click Blueprint (Recommended)
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** in the top right and select **Blueprint**.
3. Connect your GitHub repository: `https://github.com/sunil276/langgraph-project.git`.
4. Render will automatically detect [`render.yaml`](./render.yaml).
5. Click **Apply**.
6. Render will automatically build the container and deploy your live app!

#### Option B: Manual Web Service Setup
If you prefer configuring manually:
1. In Render Dashboard, click **New +** ➔ **Web Service**.
2. Connect your GitHub repository.
3. Configure the following fields:
   - **Name**: `datavox`
   - **Environment / Runtime**: `Python 3`
   - **Region**: Any (e.g. *Oregon, US* or *Frankfurt, EU*)
   - **Branch**: `main`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && python scripts/init_sample_db.py
     ```
   - **Start Command**:
     ```bash
     uvicorn server:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: `Free`

4. Click **Create Web Service**.

---

### Step 3: How Users Use the Live Application

Once your Render service status turns **Live**:
1. Click on your Render public URL (e.g., `https://datavox.onrender.com`).
2. When users first arrive, they click the **"API Key" (⚙️)** button in the top right.
3. Users select their provider:
   - **Google Gemini** (Free Tier available from [Google AI Studio](https://aistudio.google.com/app/apikey))
   - **OpenAI** (from [platform.openai.com](https://platform.openai.com/api-keys))
4. Users paste their API key and click **Save Credentials**.
5. **Key Security**: The key is stored **only in the user's browser localStorage** and is sent directly per request. It is never logged on the server.
6. Users can now query existing data, upload multiple custom datasets, and inspect generated SQL and foreign-key links!

---

## ⚙️ Optional Server-Level Fallback Key

If you want the deployed app to work out-of-the-box even for users who haven't entered an API key yet:
1. In the Render Dashboard, go to your Web Service ➔ **Environment**.
2. Add an environment variable:
   - Key: `GEMINI_API_KEY`
   - Value: `<your-gemini-api-key>`
3. Save changes. Users who don't enter their own key will use your fallback key; users who enter their own key will use their own!

---

## 🗄️ Database & Persistent Disk (Optional)

On Render's Free tier, the filesystem resets when the container goes to sleep. The built-in sample tables (`customers`, `orders`, `products`, `regional_sales`) will always be automatically seeded.

If you want custom uploaded tables to persist permanently across container restarts:
1. In your Render Web Service settings, go to **Disks**.
2. Click **Add Disk**:
   - **Name**: `datavox-data`
   - **Mount Path**: `/app/data`
   - **Size**: 1 GB (Free on paid plan or attach SQLite path `sqlite:////app/data/datavox.db`).
   - Or connect a free **Cloud PostgreSQL** database (like [Neon.tech](https://neon.tech) or [Supabase](https://supabase.com)) by simply setting `DATABASE_URL=postgresql+psycopg://...` in your Render Environment Variables!
