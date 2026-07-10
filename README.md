# 🎓 EduSimpli — AI Course Content Simplification Agent

> Powered by **IBM Watsonx.ai** and **IBM Granite** models | Built with **Python Flask**

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 AI Simplification | Breaks down complex content using IBM Granite LLM |
| 📤 Document Upload | Supports PDF, DOCX, and TXT files |
| 💬 AI Chat | Conversational tutor with document context |
| 🧪 Quiz Generator | Auto-generates multiple-choice quizzes |
| 🃏 Flashcards | AI-powered term/definition flashcards |
| 📖 Glossary | Extracts and defines key technical terms |
| 📋 Summaries | Topic-wise structured document summaries |
| 🔖 Bookmarks | Save important documents |
| 📊 Progress Tracking | Monitor study topics and quiz scores |
| 👤 Student Profiles | Personalized learning level & domain |
| 🌙 Dark Mode | Full dark/light theme support |
| 📱 Mobile Responsive | Works on all screen sizes |

---

## 🚀 Quick Start — Local Setup

### Prerequisites
- Python 3.9+
- IBM Cloud account with Watsonx.ai access
- IBM API Key and Project ID

### 1. Clone & Navigate
```bash
cd course-simplifier
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
# Copy the example env file
copy .env.example .env       # Windows
cp .env.example .env         # macOS/Linux
```

Open `.env` and fill in your credentials:
```env
IBM_API_KEY=your_actual_ibm_cloud_api_key
IBM_PROJECT_ID=your_watsonx_project_id
IBM_WATSONX_URL=https://us-south.ml.cloud.ibm.com
SECRET_KEY=change-this-to-a-long-random-string
```

### 5. Run the Application
```bash
python app.py
```

Visit **http://localhost:5000** in your browser.

**Demo login:** `demo` / `demo1234`

---

## 🔑 Getting IBM Watsonx.ai Credentials

### Step 1: Create an IBM Cloud Account
1. Go to [https://cloud.ibm.com](https://cloud.ibm.com)
2. Sign up for a free Lite account

### Step 2: Get Your API Key
1. Log in to IBM Cloud
2. Click your profile icon → **Manage** → **Access (IAM)**
3. Go to **API Keys** → **Create an IBM Cloud API key**
4. Copy and save the key (shown only once)

### Step 3: Create a Watsonx.ai Project
1. Go to [https://dataplatform.cloud.ibm.com](https://dataplatform.cloud.ibm.com)
2. Create a new **Watsonx.ai** project
3. Copy the **Project ID** from the project settings

### Step 4: Associate a Watson Machine Learning Service
1. In your project, go to **Manage** → **Services & integrations**
2. Add a **Watson Machine Learning** service instance (Lite tier is free)

---

## 🛠 Project Structure

```
course-simplifier/
├── app.py                  # Flask application + all API routes
├── db_models.py            # SQLAlchemy database models
├── watsonx_agent.py        # IBM Watsonx.ai integration + AGENT_INSTRUCTIONS
├── sample_data.json        # Sample educational content
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .env                    # Your actual credentials (DO NOT COMMIT)
├── uploads/                # Uploaded documents (auto-created)
├── instance/               # SQLite DB location (auto-created)
├── static/
│   ├── css/
│   │   └── style.css       # Custom CSS (light/dark theme)
│   └── js/
│       └── app.js          # Frontend JavaScript
└── templates/
    └── index.html          # Single-page HTML template
```

---

## ⚙️ Customizing the AI Agent

All agent behavior is controlled by the `AGENT_INSTRUCTIONS` dictionary in [`watsonx_agent.py`](watsonx_agent.py).

```python
AGENT_INSTRUCTIONS = {
    "agent_name":        "EduSimpli",
    "response_tone":     "friendly",    # friendly | formal | socratic | encouraging | concise
    "explanation_style": "analogy-first", # analogy-first | example-first | step-by-step | ...
    "educational_domain": "Computer Science",  # Set your subject area
    "model_id":          "ibm/granite-3-3-8b-instruct",

    # Per-level vocabulary, depth, and token budgets
    "level_profiles": {
        "Beginner":     { "vocab": "everyday language", "max_tokens": 600 },
        "Intermediate": { "vocab": "domain terms with definitions", "max_tokens": 800 },
        "Advanced":     { "vocab": "full technical vocabulary", "max_tokens": 1000 },
        "Expert":       { "vocab": "peer-level terminology", "max_tokens": 1200 },
    },

    # Safety rules enforced in every prompt
    "safety_rules": [
        "Never produce harmful content.",
        "Do not fabricate citations.",
        ...
    ],
}
```

---

## 🗄 Database

### Default: SQLite
No setup required. The database file is created automatically at `instance/course_simplifier.db`.

### Optional: MySQL
1. Install the MySQL driver:
   ```bash
   pip install PyMySQL cryptography
   ```
2. Update `.env`:
   ```env
   DATABASE_URL=mysql+pymysql://username:password@localhost:3306/course_simplifier
   ```
3. Create the database in MySQL:
   ```sql
   CREATE DATABASE course_simplifier CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

---

## ☁️ IBM Cloud Deployment (Lite Tier)

### Option A: IBM Cloud Foundry

1. **Install IBM Cloud CLI:**
   ```bash
   # Windows (PowerShell)
   iex (New-Object Net.WebClient).DownloadString('https://raw.githubusercontent.com/IBM-Cloud/ibm-cloud-cli-release/master/download/bx-win.ps1')
   ```

2. **Login and target:**
   ```bash
   ibmcloud login --sso
   ibmcloud target --cf
   ```

3. **Create `manifest.yml`:**
   ```yaml
   applications:
   - name: edusimpli-agent
     memory: 512M
     buildpacks:
       - python_buildpack
     command: gunicorn app:app --bind 0.0.0.0:$PORT
     env:
       IBM_API_KEY: your_key_here
       IBM_PROJECT_ID: your_project_id_here
       IBM_WATSONX_URL: https://us-south.ml.cloud.ibm.com
       SECRET_KEY: your-secret-key
   ```

4. **Add `Procfile`:**
   ```
   web: gunicorn app:app --bind 0.0.0.0:$PORT
   ```

5. **Push:**
   ```bash
   ibmcloud cf push
   ```

### Option B: IBM Code Engine (Serverless Containers)

1. **Build Docker image — create `Dockerfile`:**
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   EXPOSE 8080
   CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2"]
   ```

2. **Build & push image:**
   ```bash
   docker build -t edusimpli .
   docker tag edusimpli icr.io/your-namespace/edusimpli:latest
   docker push icr.io/your-namespace/edusimpli:latest
   ```

3. **Deploy on Code Engine:**
   ```bash
   ibmcloud ce application create \
     --name edusimpli \
     --image icr.io/your-namespace/edusimpli:latest \
     --env IBM_API_KEY=your_key \
     --env IBM_PROJECT_ID=your_project_id \
     --env SECRET_KEY=your_secret
   ```

---

## 🔒 Security Notes

- **Never commit `.env`** — it's listed in `.gitignore`
- The `SECRET_KEY` must be a long random string in production
- File uploads are limited to 16 MB and sanitized with `secure_filename`
- All API routes require authenticated sessions
- Passwords are hashed with Werkzeug's `generate_password_hash`

---

## 📦 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/register` | Register |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/documents` | List documents |
| POST | `/api/documents/upload` | Upload file |
| DELETE | `/api/documents/<id>` | Delete document |
| POST | `/api/simplify` | AI simplification |
| POST | `/api/quiz/generate` | Generate quiz |
| POST | `/api/quiz/<id>/submit` | Submit quiz answers |
| POST | `/api/flashcards/generate` | Generate flashcards |
| POST | `/api/glossary/generate` | Generate glossary |
| POST | `/api/summary/generate` | Generate summary |
| GET | `/api/recommendations` | AI study recommendations |
| POST | `/api/chat/send` | Send chat message |
| GET | `/api/progress` | Study progress stats |
| PUT | `/api/profile` | Update profile |
| POST | `/api/bookmarks` | Add bookmark |

---

## 🛠 Troubleshooting

| Issue | Solution |
|---|---|
| `IBM_API_KEY not configured` | Add your key to `.env` and restart |
| `IBM_PROJECT_ID not configured` | Add project ID from Watsonx.ai console |
| `Upload fails` | Check file size < 16MB, type is PDF/DOCX/TXT |
| `Database error` | Delete `instance/course_simplifier.db` to reset |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Quiz shows "Could not parse" | AI output was not valid JSON; retry |

---

## 📜 License

MIT License — free to use, modify, and distribute.

---

*Built with ❤️ using IBM Watsonx.ai, IBM Granite, Python Flask, and Bootstrap 5.*
