# Partner Survey System - Streamlit Edition

A comprehensive survey management system built with Streamlit and PostgreSQL, migrated from the React/Node.js version.

## 🎯 Overview

This is a Streamlit-based implementation of the Partner Survey Application that uses the **same PostgreSQL database schema** as the existing React/Node.js application. Both applications can run simultaneously and share the same data.

## ✨ Features

### Admin Mode
- 📤 **Upload Survey Templates**: Upload Excel/CSV files with survey questions
- 📋 **View Surveys**: Browse all available surveys and their questions
- 📊 **Export Data**: Download all submissions as Excel files

### Partner Mode
- 🔍 **Customer Search**: Search and select customers from the database
- 📝 **Fill Surveys**: Complete surveys with dynamic form rendering
- ✏️ **Update Responses**: Edit previously submitted responses
- 📈 **Progress Tracking**: Real-time progress indicator
- ✅ **Validation**: Required field validation

### Question Types Supported
- Text input
- Text area
- Single select (dropdown)
- Multi-select
- Rating slider (1-5 or custom range)
- Matrix questions
- Conditional logic (show/hide based on dependencies)

## 🗄️ Database Schema

This application uses the **exact same database schema** as the React/Node.js app:

- `customers` - Customer/account information
- `partners` - Partner user information
- `templates` - Survey templates with JSONB questions
- `submissions` - Survey submission records
- `responses` - Individual question responses

**Note:** Both applications can access the same database simultaneously without conflicts.

## 🚀 Deployment Options

### Option 1: Streamlit Community Cloud (Recommended)

1. **Push to GitHub:**
   ```bash
   cd streamlit-migration
   git init
   git add .
   git commit -m "Initial Streamlit migration"
   git remote add origin https://github.com/yourusername/your-repo.git
   git push -u origin main
   ```

2. **Deploy to Streamlit Cloud:**
   - Go to https://share.streamlit.io
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Set main file: `streamlit-migration/app.py`
   - Click "Deploy"

3. **Configure Secrets:**
   - In Streamlit Cloud dashboard, go to Settings → Secrets
   - Copy contents from `.streamlit/secrets.toml`
   - Save

### Option 2: Run Locally

1. **Install Dependencies:**
   ```bash
   cd streamlit-migration
   pip install -r requirements.txt
   ```

2. **Configure Database:**
   - Edit `.streamlit/secrets.toml` with your database credentials

3. **Run the App:**
   ```bash
   streamlit run app.py
   ```

4. **Access:**
   - Opens automatically at `http://localhost:8501`

### Option 3: Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:
```bash
docker build -t partner-survey-streamlit .
docker run -p 8501:8501 partner-survey-streamlit
```

## 📁 File Structure

```
streamlit-migration/
├── app.py                    # Main Streamlit application (single file)
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── .streamlit/
    └── secrets.toml          # Database credentials (DO NOT commit to public repos)
```

## ⚙️ Configuration

### Database Connection

Edit `.streamlit/secrets.toml`:

```toml
DB_HOST = "your_database_host"
DB_PORT = 5432
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "your_password"
```

### Environment Variables (Alternative)

You can also use environment variables:

```bash
export DB_HOST="your_database_host"
export DB_PORT=5432
export DB_NAME="postgres"
export DB_USER="postgres"
export DB_PASSWORD="your_password"
```

## 🔒 Security Notes

1. **Never commit `secrets.toml` to public repositories**
   - Add `.streamlit/secrets.toml` to `.gitignore`
   - Use Streamlit Cloud's Secrets Management for production

2. **Database Access**
   - Ensure your database accepts connections from Streamlit Cloud IPs
   - Use strong passwords
   - Consider using SSL connections for production

3. **Network Security**
   - If database is on your PC, configure firewall rules
   - For production, use cloud-hosted databases (AWS RDS, Google Cloud SQL, etc.)

## 🆚 Comparison with React/Node.js Version

| Feature | React/Node.js | Streamlit |
|---------|---------------|-----------|
| **Lines of Code** | ~2,500+ | ~800 |
| **Technologies** | React, Node.js, Express | Python, Streamlit |
| **Deployment** | 2 servers (frontend + backend) | 1 server |
| **Database** | PostgreSQL | PostgreSQL (same schema) |
| **File Upload** | Multer | Built-in |
| **Excel Export** | XLSX library | Pandas |
| **State Management** | React hooks | Session state |
| **Development Time** | Weeks | Days |

## 📊 Database Schema Setup

If you need to set up the database from scratch, run this SQL:

```sql
-- See survey-backend/database-schema.sql in the parent directory
-- Or run the complete schema from the React/Node.js app
```

The schema is located at: `../survey-backend/database-schema.sql`

## 🧪 Testing

1. **Test Database Connection:**
   - Check the sidebar for "✅ Database Connected" indicator

2. **Test Admin Mode:**
   - Upload a sample survey template
   - View the uploaded survey

3. **Test Partner Mode:**
   - Search for a customer
   - Select a survey
   - Fill and submit responses

## 📝 Sample Survey Template Format

Create an Excel/CSV file with these columns:

| QuestionID | Type | Question | Section | Required | Options | MinRating | MaxRating |
|------------|------|----------|---------|----------|---------|-----------|-----------|
| Q1 | text | What is your company name? | Introduction | Yes | | | |
| Q2 | multiple_choice_single_select | How satisfied are you? | Feedback | Yes | Very Satisfied,Satisfied,Neutral,Dissatisfied | | |
| Q3 | rating | Rate our service | Feedback | Yes | | 1 | 5 |

## 🐛 Troubleshooting

### Database Connection Failed
- Check database credentials in `secrets.toml`
- Verify database is running and accessible
- Check firewall rules
- Ensure PostgreSQL accepts remote connections

### File Upload Issues
- Check file format (Excel or CSV)
- Verify column names match expected format
- Check file size (max 200MB by default)

### Performance Issues
- Add database indexes (already included in schema)
- Use connection pooling for high traffic
- Consider caching with `@st.cache_data`

## 📚 Additional Resources

- [Streamlit Documentation](https://docs.streamlit.io)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Streamlit Community Cloud](https://share.streamlit.io)

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section
2. Review Streamlit documentation
3. Check database connection and schema

## 📄 License

This application uses the same license as the parent React/Node.js application.

---

**Note:** This Streamlit version is a complete, standalone implementation that shares the same database with the React/Node.js version. Both can run simultaneously without conflicts.

