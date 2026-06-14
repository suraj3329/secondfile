# Streamlit Cloud Deployment Guide

This guide details how to deploy the **Fact-Check Agent** to **Streamlit Community Cloud** for public or staging environments.

---

## 📋 Prerequisites

1. A **GitHub repository** containing the project codebase.
2. A **Streamlit Community Cloud Account** (sign up at [share.streamlit.io](https://share.streamlit.io) using your GitHub account).
3. Active API Keys:
   - **Google Gemini API Key** (Get one at [Google AI Studio](https://aistudio.google.com/)).
   - **Tavily API Key** (Get one at [Tavily](https://tavily.com/)) or **Serper API Key** (Get one at [Serper](https://serper.dev/)).

---

## 🚀 Deployment Steps

### Step 1: Push Code to GitHub
Ensure all your files, including `requirements.txt`, `app.py`, and the `src/` directory, are pushed to your GitHub repository:
```bash
git init
git add .
git commit -m "feat: init fact check agent truth layer"
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/fact-check-agent.git
git push -u origin main
```

### Step 2: Set Up App in Streamlit Cloud
1. Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
2. Click the **"New app"** button.
3. In the deployment form, select:
   - **Repository**: Choose `YOUR_USERNAME/fact-check-agent`
   - **Branch**: `main` (or the branch you pushed to)
   - **Main file path**: `app.py`
   - **App URL**: Choose a custom subdomain prefix if available (e.g. `fact-check-agent.streamlit.app`).

### Step 3: Configure Environment Secrets
Streamlit Community Cloud requires you to set your API keys as application secrets instead of placing a `.env` file on GitHub (which is insecure).

1. Before clicking deploy, click on the **"Advanced settings..."** button at the bottom of the page.
2. In the **Secrets** modal, paste your keys in TOML format:
   ```toml
   GEMINI_API_KEY = "AIzaSy..."
   TAVILY_API_KEY = "tvly-..."
   
   # Optional: Add Serper key if using Serper as primary/secondary
   SERPER_API_KEY = "..."
   ```
3. Click **Save**.

### Step 4: Deploy & Build
1. Click the **"Deploy!"** button.
2. The Streamlit cloud platform will spin up a container, install python dependencies from `requirements.txt`, configure environmental secrets, and start the app.
3. Once completed, you will see your Fact-Check Agent application live!

---

## 🛠️ Troubleshooting & Management

### Secrets Management
If you need to update your API keys after deployment:
1. Open your app on Streamlit Community Cloud.
2. Click on the **Settings** gear icon in the bottom-right corner.
3. Select **Secrets** from the left panel.
4. Modify the TOML definitions, then click **Save**. The app will reload automatically with the new secrets.

### Dependency Issues
Streamlit Cloud automatically matches versions in `requirements.txt`. If your build fails due to conflicting libraries, review the app log on the right side of the dashboard, clean up versions in `requirements.txt`, and push to GitHub to trigger a fresh deploy.
