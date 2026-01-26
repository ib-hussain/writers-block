# Writer's Block

A Flask-based blog writing assistant designed to help content creators generate SEO-optimized blog posts with customizable prompts and AI-powered content generation.

## 🎯 Overview

Writer's Block is a web application that streamlines blog content creation through:
- **Multi-section blog generation** (intro, CTAs, FAQs, business descriptions)
- **Customizable prompt templates** with variable substitution
- **Example-based learning** from existing blog content
- **Progress tracking** for multi-step content generation
- **PostgreSQL database** for content storage and history

## 🏗️ Architecture

```
┌─────────────────┐
│   Frontend      │  HTML/CSS/JavaScript
│   (chatbot.js)  │  Variable management & UI
└────────┬────────┘
         │ REST API
┌────────▼────────┐
│   Flask App     │  Request handling
│   (app.py)      │  Prompt preparation
└────────┬────────┘
         │
┌────────▼────────┐
│  Orchestrator   │  Agent coordination
│ (orchestrater)  │  Parallel execution
└────────┬────────┘
         │
┌────────▼────────┐
│   PostgreSQL    │  Content & history
│   Database      │  Progress tracking
└─────────────────┘
```

## 📋 Features

### ✅ Implemented

- **Web Interface**
  - Interactive chat interface for blog generation
  - Collapsible variable configuration panel
  - Real-time chat history loading
  - LocalStorage persistence for user preferences

- **Variable Management**
  - 26+ configurable variables (title, keywords, company info, etc.)
  - Blog type selection (Health vs Legal)
  - Temperature control for content generation
  - Dynamic example selection (up to 10 per section)

- **Database Layer**
  - Connection pooling for efficient database access
  - Safe transaction handling with automatic rollback
  - Blog content storage (full blogs and individual parts)
  - Chat history tracking with timestamps
  - Progress tracking for multi-step generation

- **API Endpoints**
  - `/api/chat` - Chat message handling
  - `/api/db/table/<table_name>` - Database table viewing
  - `/api/stats/tokens/month` - Monthly token statistics
  - `/api/profile/history` - Chat history by date

- **Prompt System**
  - Template-based prompts with variable substitution
  - Example fetching from database
  - Support for multiple blog sections (intro, CTA, FAQs, etc.)

### 🚧 In Development

- **AI Integration** - LLM provider integration for content generation
- **User Authentication** - Multi-user support with session management
- **Advanced Analytics** - Usage statistics and performance metrics

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 12+
- pip (Python package manager)

### Access the application
   
   Open your browser to: `https://writers-block-weup.onrender.com`

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

## 🗄️ Database Schema

### Tables

- **BlogData** - Complete blog posts
- **BlogParts** - Individual blog sections (intro, CTA, FAQs, etc.)
- **PromptData** - Prompt templates for content generation
- **progress** - Daily progress tracking for agent completion
- **profileHistory** - Chat history and user interactions


## 🔧 Configuration

### Blog Types

The application supports two blog types with different example ranges:

- **Legal** - Uses blog examples 11-20
- **Health** - Uses blog examples 1-10

### Prompt Variables

The system supports 26+ variables for prompt customization:

**Basic Information:**
- `TITLE`, `COMPANY_NAME`, `CALL_NUMBER`, `ADDRESS`, `STATE_NAME`, `LINK`, `COMPANY_EMPLOYEE`

**Content Variables:**
- `KEYWORDS`, `SOURCE`, `INSERT_INTRO_QUESTION`, `INSERT_FAQ_QUESTIONS`

**Example Selection:**
- `BLOGFOREXAMPLE` - Full blog examples (array of IDs)
- `BLOGPART_INTRO`, `BLOGPART_FINALCTA`, `BLOGPART_FAQS`, `BLOGPART_BUSINESSDESC`, `BLOGPART_SHORTCTA`

**Prompts:**
- `PROMPT_FULLBLOG`, `PROMPT_INTRO`, `PROMPT_FINALCTA`, `PROMPT_FULLFAQS`, `PROMPT_BUSINESSDESC`, `PROMPT_REFERENCES`, `PROMPT_SHORTCTA`

**Settings:**
- `TEMPERATURE` - Content generation temperature (0.0-1.0)

## 🌐 API Documentation
### Pricing  
<!-- make the below into a proper form once project is completed -->
# Pricing Per Million Tokens:                                Input   Output
# OpenAI/gpt-oss-20B                                         $0.05   $0.20   References
# openai/gpt-oss-120b                                        $0.15   $0.60   References, Final CTA
# google/gemma-3n-E4B-it                                     $0.02   $0.04   Short CTA
# Qwen/Qwen3-Next-80B-A3B-Instruct                           $0.15   $1.50   Buisness Description, Introduction
# Qwen/Qwen2.5-7B-Instruct-Turbo                             $0.30   $0.30   Buisness Description
# deepseek-ai/DeepSeek-V3.1                                  $0.60   $1.25   FAQs
# Qwen/Qwen2.5-72B-Instruct-Turbo                            $1.20   $1.20   FAQs
# meta-llama/Meta-Llama-3-8B-Instruct-Lite                   $0.10   $0.10   Final CTA
# deepseek-ai/DeepSeek-R1-0528-tput                          $0.55   $2.19   Intro Section
# Qwen/Qwen3-Next-80B-A3B-Instruct                           $0.15   $1.50   Intro Section
# deepseek-ai/DeepSeek-V3                                    $1.25   $1.25   Final Full Blog

### POST `/api/chat`

Handle chat messages and generate blog content.

**Request Body:**
```json
{
  "message": "Generate a blog about car accidents",
  "vars": {
    "TITLE": "What to Do After a Car Accident",
    "KEYWORDS": "lawyer, attorney, accident, claim",
    "TEMPERATURE": "0.70",
    "BLOGTYPE": "Legal",
    "COMPANY_NAME": "Smith & Associates",
    ...
  }
}
```

**Response:**
```json
{
  "success": true,
  "response": "Generated blog content...",
  "timestamp": "2026-01-26T05:00:00",
  "debug_info": {
    "blog_type": "Legal",
    "temperature": "0.70",
    "examples_fetched": {
      "full_blogs": 3,
      "intro_parts": 2,
      ...
    }
  }
}
```

### GET `/api/profile/history?date=YYYY-MM-DD`

Retrieve chat history for a specific date.

**Response:**
```json
{
  "success": true,
  "code": "OK",
  "date": "2026-01-26",
  "rows": [
    {
      "id": 1,
      "entry": "2026-01-26T05:00:00",
      "userprompt": "User message...",
      "chatresponse": "Bot response..."
    }
  ]
}
```

### GET `/api/stats/tokens/month`

Get token statistics for the current month.

**Response:**
```json
{
  "success": true,
  "month_label": "Jan 2026",
  "daily": [
    {
      "day": "01",
      "input_words": 150,
      "output_words": 1200
    }
  ]
}
```

### GET `/api/db/table/<table_name>`

View database table contents (excludes `profilehistory`).

**Response:**
```json
{
  "success": true,
  "table": {
    "name": "blogdata",
    "columns": ["blogID", "blogText"],
    "row_count": 20,
    "rows": [...]
  }
}
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📧 Contact

Email: ibrahimbeaconarion@gmail.com

---

**Note:** This project is under active development. The AI integration layer is currently being implemented. The application framework, database layer, and frontend are fully functional.

