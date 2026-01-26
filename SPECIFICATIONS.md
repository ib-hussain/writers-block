## 🗄️ Database Schema

### Tables

#### `BlogData`
Stores complete blog posts.
```sql
CREATE TABLE BlogData (
    blogID INT PRIMARY KEY,
    blogText TEXT NOT NULL
);
```

#### `BlogParts`
Stores individual blog sections.
```sql
CREATE TABLE BlogParts (
    blogID INT PRIMARY KEY,
    intro TEXT NOT NULL,
    final_cta TEXT NOT NULL,
    FAQs TEXT NOT NULL,
    business_description TEXT NOT NULL,
    integrate_references TEXT DEFAULT NULL,
    short_cta TEXT NOT NULL,
    FOREIGN KEY (blogID) REFERENCES BlogData(blogID)
);
```

#### `PromptData`
Stores prompt templates for content generation.
```sql
CREATE TABLE PromptData (
    promptID INT PRIMARY KEY,
    writing TEXT NOT NULL,
    intro TEXT NOT NULL,
    final_cta TEXT NOT NULL,
    FAQs TEXT NOT NULL,
    business_description TEXT NOT NULL,
    integrate_references TEXT DEFAULT NULL,
    short_cta TEXT NOT NULL
);
```

#### `progress`
Tracks daily agent completion status.
```sql
CREATE TABLE progress (
    id BIGSERIAL,
    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
    entry TIMESTAMPTZ NOT NULL,
    writing BOOLEAN DEFAULT FALSE,
    intro BOOLEAN DEFAULT FALSE,
    final_cta BOOLEAN DEFAULT FALSE,
    faqs BOOLEAN DEFAULT FALSE,
    integrate_references BOOLEAN DEFAULT FALSE,
    business_description BOOLEAN DEFAULT FALSE,
    short_cta BOOLEAN DEFAULT FALSE,
    CONSTRAINT progress_entry_date_uniq UNIQUE (entry_date)
);
```

#### `profileHistory`
Stores chat history and user interactions.
```sql
CREATE TABLE profileHistory (
    id SERIAL PRIMARY KEY,
    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
    entry TIMESTAMPTZ NOT NULL,
    userprompt TEXT DEFAULT NULL,
    chatresponse TEXT DEFAULT NULL,
    FOREIGN KEY (entry_date) REFERENCES progress(entry_date)
);
```

---

## 📁 Project Structure

```
writers-block/
├── app.py                      # Flask application & API routes
├── requirements.txt            # Python dependencies
├── render.yaml                 # Render.com deployment config
├── .env                        # Environment variables (not in git)
├── .gitignore                  # Git ignore rules
│
├── chatbots/                   # AI agent modules
│   ├── orchestrater.py        # Agent orchestration & coordination
│   ├── FullAgents.py          # Full blog writing agent
│   ├── SingularAgents.py      # Individual section agents
│   └── reasoning.py           # Classification logic (deprecated)
│
├── data/                       # Database layer
│   ├── database_postgres.py   # Database connection & helpers
│   ├── schema.sql             # PostgreSQL schema
│   ├── counter.txt            # Progress counter
│   └── ignore/                # Sample data (not in git)
│
└── web_files/                  # Frontend assets
    ├── chatbot.html           # Main chat interface
    ├── databaseView.html      # Database viewer
    ├── profile.html           # User profile
    ├── navbar.html            # Navigation component
    │
    ├── css/                   # Stylesheets
    │   ├── chatbot.css
    │   ├── databaseView.css
    │   ├── navbar.css
    │   └── profile.css
    │
    ├── js/                    # JavaScript modules
    │   ├── chatbot.js         # Chat logic & variable management
    │   ├── dbOverview.js      # Database overview
    │   ├── dbTablePage.js     # Table viewing
    │   ├── navbar.js          # Navigation logic
    │   └── profile.js         # Profile management
    │
    └── pictures/              # Images & icons
```

---

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `EMPTY_MESSAGE` | 400 | Message field is empty or missing |
| `MISSING_DATE` | 400 | Date parameter is missing |
| `BAD_DATE_FORMAT` | 400 | Date format is invalid (use YYYY-MM-DD) |
| `MISSING_TABLE` | 400 | Table name is missing |
| `TABLE_EXCLUDED` | 403 | Table is excluded from public access |
| `UNKNOWN_TABLE` | 404 | Table does not exist |
| `NO_ROWS_FOR_DATE` | 404 | No data found for the specified date |
| `POOL_EXHAUSTED` | 500 | Database connection pool is exhausted |
| `DB_ERROR` | 500 | Database operation failed |
| `CHAT_FAILED` | 500 | Chat processing failed |
| `DB_TABLE_FAIL` | 500 | Failed to load table |
| `TOKENS_MONTH_FAIL` | 500 | Failed to compute token statistics |
| `PROFILE_HISTORY_FAIL` | 500 | Failed to load profile history |

---

## Troubleshooting

### Common Issues

#### Database Connection Errors

**Problem:** `POOL_EXHAUSTED` or connection timeout errors

**Solutions:**
1. Check PostgreSQL is running: `pg_isready`
2. Verify database credentials in `.env`
3. Increase connection pool size in `app.py`:
   ```python
   POOL_MAX = 20  # Increase from default 10
   ```
4. Check for unclosed connections in your code

---

#### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'langchain'`

**Solutions:**
1. Ensure virtual environment is activated
2. Reinstall dependencies: `pip install -r requirements.txt`
3. Check Python version: `python --version` (must be 3.12+)

---

#### Empty Chat Responses

**Problem:** API returns empty or error responses

**Solutions:**
1. Verify all required variables are provided in the request
2. Check that example blog IDs exist in the database
3. Review application logs for detailed error messages
4. Ensure AI model API keys are configured correctly

---

#### Timezone Issues with Chat History

**Problem:** Chat history not showing for the correct date

**Solutions:**
1. Check the `entry_date` column in the database
2. Verify server timezone matches your expected timezone
3. Use the diagnostics in the error response to identify timezone mismatches
4. Consider adjusting the date query by ±1 day

---

#### Performance Issues

**Problem:** Slow response times or timeouts

**Solutions:**
1. Enable database query caching
2. Reduce the number of examples fetched (use 3-5 instead of 10)
3. Optimize prompts to be more concise
4. Consider using faster AI models for non-critical sections
5. Implement request queuing for high-traffic scenarios

---