# Streamlit Migration - Deployment Guide

This guide will help you deploy the Streamlit version of the Partner Survey Application.

## 📋 Prerequisites

- GitHub account
- Database credentials (host, port, username, password)
- Database schema already set up (uses same schema as React/Node.js app)

## 🚀 Quick Start - Deploy to Streamlit Community Cloud

### Step 1: Prepare GitHub Repository

You have two options:

#### Option A: Add to Existing Repository (Recommended)

The `streamlit-migration` folder is already in your project. Just commit and push:

```bash
# From your project root directory
git add streamlit-migration/
git commit -m "Add Streamlit migration"
git push origin main
```

#### Option B: Create Separate Repository

```bash
cd streamlit-migration
git init
git add .
git commit -m "Initial commit - Streamlit Partner Survey App"
git branch -M main
git remote add origin https://github.com/yourusername/partner-survey-streamlit.git
git push -u origin main
```

### Step 2: Deploy to Streamlit Cloud

1. **Go to Streamlit Cloud:**
   - Visit: https://share.streamlit.io
   - Click "Sign in" (use your GitHub account)

2. **Create New App:**
   - Click "New app" button
   - Fill in the form:
     - **Repository:** Select your repository
     - **Branch:** `main` (or your default branch)
     - **Main file path:** 
       - If using existing repo: `streamlit-migration/app.py`
       - If separate repo: `app.py`
   - Click "Deploy!"

3. **Configure Secrets:**
   - While deployment is starting, click on "Advanced settings" or wait for deployment
   - Go to "Settings" (⚙️ icon) → "Secrets"
   - Paste your database credentials:
     ```toml
     DB_HOST = "35.202.207.181"
     DB_PORT = 5432
     DB_NAME = "postgres"
     DB_USER = "postgres"
     DB_PASSWORD = "{bUN?x2=;c.x~<K"
     ```
   - Click "Save"

4. **Wait for Deployment:**
   - Deployment takes 2-5 minutes
   - You'll see logs in real-time
   - Once complete, your app will be live!

### Step 3: Access Your App

Your app will be available at:
```
https://[your-username]-[repo-name]-[random-string].streamlit.app
```

Example:
```
https://pvsarolkar-ps-survey-streamlit-abc123.streamlit.app
```

## 🔒 Security Best Practices

### 1. Remove Secrets from Git

**IMPORTANT:** Before pushing to GitHub, ensure secrets are not committed:

```bash
# Add to .gitignore (already included)
echo ".streamlit/secrets.toml" >> .gitignore

# If you already committed secrets, remove them:
git rm --cached .streamlit/secrets.toml
git commit -m "Remove secrets from git"
git push
```

### 2. Use Streamlit Cloud Secrets

Always configure secrets through Streamlit Cloud's interface, not in the repository.

### 3. Database Security

- Use strong passwords
- Restrict database access by IP (whitelist Streamlit Cloud IPs)
- Use SSL connections for production databases
- Consider using a dedicated database user with limited permissions

## 🌐 Alternative Deployment Options

### Option 1: Run Locally

Perfect for development and testing:

```bash
cd streamlit-migration
pip install -r requirements.txt
streamlit run app.py
```

Access at: `http://localhost:8501`

### Option 2: Deploy to Heroku

1. **Create `Procfile`:**
   ```
   web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
   ```

2. **Deploy:**
   ```bash
   heroku create your-app-name
   heroku config:set DB_HOST="35.202.207.181"
   heroku config:set DB_PORT=5432
   heroku config:set DB_NAME="postgres"
   heroku config:set DB_USER="postgres"
   heroku config:set DB_PASSWORD="{bUN?x2=;c.x~<K"
   git push heroku main
   ```

### Option 3: Deploy to AWS EC2

1. **Launch EC2 Instance** (Ubuntu 20.04 or later)

2. **Install Dependencies:**
   ```bash
   sudo apt update
   sudo apt install python3-pip
   pip3 install -r requirements.txt
   ```

3. **Configure Secrets:**
   ```bash
   mkdir -p ~/.streamlit
   nano ~/.streamlit/secrets.toml
   # Paste your credentials
   ```

4. **Run with PM2:**
   ```bash
   npm install -g pm2
   pm2 start "streamlit run app.py --server.port=8501" --name partner-survey
   pm2 save
   pm2 startup
   ```

5. **Configure Nginx (optional):**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8501;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
       }
   }
   ```

### Option 4: Deploy with Docker

1. **Create `Dockerfile`:**
   ```dockerfile
   FROM python:3.9-slim
   
   WORKDIR /app
   
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   COPY . .
   
   EXPOSE 8501
   
   CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
   ```

2. **Build and Run:**
   ```bash
   docker build -t partner-survey-streamlit .
   docker run -p 8501:8501 \
     -e DB_HOST="35.202.207.181" \
     -e DB_PORT=5432 \
     -e DB_NAME="postgres" \
     -e DB_USER="postgres" \
     -e DB_PASSWORD="{bUN?x2=;c.x~<K" \
     partner-survey-streamlit
   ```

3. **Deploy to Docker Hub:**
   ```bash
   docker tag partner-survey-streamlit yourusername/partner-survey-streamlit
   docker push yourusername/partner-survey-streamlit
   ```

## 🔧 Configuration

### Database Connection

The app reads database credentials from Streamlit secrets or environment variables:

**Priority:**
1. Streamlit secrets (`.streamlit/secrets.toml` or Streamlit Cloud Secrets)
2. Environment variables (`DB_HOST`, `DB_PORT`, etc.)
3. Default values (localhost)

### Custom Configuration

Edit `app.py` to customize:
- Page title and icon
- Color scheme
- Default values
- Validation rules

## 📊 Monitoring

### Streamlit Cloud

- View logs in real-time from the Streamlit Cloud dashboard
- Monitor app health and usage
- Set up email alerts for errors

### Custom Monitoring

Add to `app.py`:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log important events
logger.info(f"Survey submitted: {submission_id}")
logger.error(f"Database error: {error}")
```

## 🧪 Testing Before Deployment

1. **Test Locally:**
   ```bash
   streamlit run app.py
   ```

2. **Test Database Connection:**
   - Check sidebar for "✅ Database Connected"
   - Try uploading a survey template
   - Try submitting a response

3. **Test All Features:**
   - [ ] Admin: Upload template
   - [ ] Admin: View surveys
   - [ ] Admin: Export data
   - [ ] Partner: Search customer
   - [ ] Partner: Fill survey
   - [ ] Partner: Update response

## 🐛 Troubleshooting

### Issue: "Database Connection Failed"

**Solutions:**
1. Check database credentials in secrets
2. Verify database is accessible from Streamlit Cloud
3. Check firewall rules
4. Ensure PostgreSQL accepts remote connections

### Issue: "Module not found"

**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: "Secrets not loading"

**Solutions:**
1. Ensure secrets are configured in Streamlit Cloud (not just in git)
2. Check TOML syntax (no extra quotes or spaces)
3. Restart the app from Streamlit Cloud dashboard

### Issue: "App is slow"

**Solutions:**
1. Use `@st.cache_resource` for database connections (already implemented)
2. Add database indexes (already in schema)
3. Optimize queries
4. Consider upgrading Streamlit Cloud plan

## 📈 Scaling

### For High Traffic:

1. **Database:**
   - Use connection pooling
   - Add read replicas
   - Optimize queries with indexes

2. **Application:**
   - Use Streamlit Cloud's paid tiers
   - Deploy multiple instances
   - Use CDN for static assets

3. **Caching:**
   ```python
   @st.cache_data(ttl=3600)  # Cache for 1 hour
   def get_surveys():
       return execute_query("SELECT * FROM templates")
   ```

## 🔄 Updates and Maintenance

### Update the App:

1. **Make changes locally**
2. **Test thoroughly**
3. **Commit and push:**
   ```bash
   git add .
   git commit -m "Update: description of changes"
   git push
   ```
4. **Streamlit Cloud auto-deploys** (if enabled)

### Manual Reboot:

From Streamlit Cloud dashboard:
- Click "⋮" menu → "Reboot app"

## 📞 Support

### Resources:
- [Streamlit Documentation](https://docs.streamlit.io)
- [Streamlit Community Forum](https://discuss.streamlit.io)
- [Streamlit Cloud Status](https://status.streamlit.io)

### Common Commands:

```bash
# Run locally
streamlit run app.py

# Run on specific port
streamlit run app.py --server.port 8502

# Run with custom config
streamlit run app.py --server.headless true

# Clear cache
streamlit cache clear
```

## ✅ Deployment Checklist

- [ ] Database schema is set up
- [ ] Database credentials are correct
- [ ] Code is pushed to GitHub
- [ ] `.streamlit/secrets.toml` is in `.gitignore`
- [ ] Secrets configured in Streamlit Cloud
- [ ] App deployed successfully
- [ ] Database connection working
- [ ] All features tested
- [ ] Documentation updated
- [ ] Team notified of new URL

---

**Ready to deploy?** Follow Step 1 above to get started! 🚀

