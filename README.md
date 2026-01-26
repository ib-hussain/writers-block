<div align="center">
<h1 align="center">Writer's Block</h1>

![Python Version](https://img.shields.io/badge/python-3.12.3%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Flask](https://img.shields.io/badge/Flask-3.1.0%2B-lightgrey)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15.12%2B-blue)

</div>

## Overview

Writer's Block is a Flask-based web application that streamlines blog content creation through AI-powered agents. Designed specifically for legal and health blog writing, it generates SEO-optimized content with customizable prompts, example-based learning, and multi-section blog generation.

### Key Features

- **Multi-Agent Architecture** - Parallel execution of specialized AI agents for different blog sections
- **Customizable Prompts** - Template-based system with 26+ configurable variables
- **PostgreSQL Integration** - Robust database layer for content storage and history tracking
- **Interactive Web Interface** - Real-time chat interface with collapsible configuration panel
- **Progress Tracking** - Monitor daily agent completion and token usage statistics
- **Example-Based Learning** - Fetch and utilize existing blog examples for consistent style

---

## Architecture

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
│   AI Agents     │  LangChain/LangGraph
│  (SingularAgents│  Content generation
│   FullAgents)   │
└────────┬────────┘
         │
┌────────▼────────┐
│   PostgreSQL    │  Content & history
│   Database      │  Progress tracking
└─────────────────┘
```

---

## Technology Stack

### Backend
- **Flask 3.1.0+** - Web framework
- **PostgreSQL 12+** - Database
- **psycopg2** - PostgreSQL adapter
- **LangChain** - LLM framework
- **LangGraph** - Agent orchestration
- **Gunicorn** - Production WSGI server

### Frontend
- **HTML5/CSS3** - Structure and styling
- **Vanilla JavaScript** - Interactive UI
- **LocalStorage API** - Client-side persistence

### AI
- **OpenAI Models** - GPT-based content generation
- **DeepSeek Models** - Cost-effective options
- **Qwen Models** - Specialized content generation

---

## Features

#### Web Interface
- Interactive chat interface for blog generation
- Collapsible variable configuration panel
- Real-time chat history loading
- LocalStorage persistence for user preferences
- Database table viewer
- Token usage statistics dashboard

#### Database Layer
- Connection pooling for efficient access
- Safe transaction handling with automatic rollback
- Blog content storage (full blogs and parts)
- Chat history tracking with timestamps
- Progress tracking for multi-step generation
- Token usage statistics

#### AI Agents
- **Intro Writing Agent** - Generates engaging introductions
- **Final CTA Agent** - Creates compelling calls-to-action
- **FAQs Agent** - Generates relevant FAQ sections
- **Business Description Agent** - Writes company descriptions
- **Short CTA Agent** - Creates brief CTAs
- **References Agent** - Integrates source citations
- **Full Blog Writer** - Assembles complete blog posts

### In Development

- **Enhanced AI Integration** - Additional LLM provider support
- **User Authentication** - Multi-user support with sessions
- **Advanced Analytics** - Detailed usage metrics and insights
- **Content Optimization** - SEO scoring and suggestions
- **Template Library** - Pre-built prompt templates

---

## Pricing & Cost Optimization

### AI Model Pricing

The application uses multiple AI models optimized for different blog sections. Pricing is per million tokens (input/output).

| Model | Input | Output | Use Case | Token Range |
|-------|-------|--------|----------|-------------|
| **OpenAI/gpt-oss-20B** | $0.05 | $0.20 | References | 128-512 tokens |
| **openai/gpt-oss-120b** | $0.15 | $0.60 | References, Final CTA | 128-512 tokens |
| **google/gemma-3n-E4B-it** | $0.02 | $0.04 | Short CTA | 64-256 tokens |
| **Qwen/Qwen3-Next-80B-A3B-Instruct** | $0.15 | $1.50 | Business Description, Introduction | 128-1024 tokens |
| **Qwen/Qwen2.5-7B-Instruct-Turbo** | $0.30 | $0.30 | Business Description | 128-1024 tokens |
| **deepseek-ai/DeepSeek-V3.1** | $0.60 | $1.25 | FAQs | 512-1024 tokens |
| **Qwen/Qwen2.5-72B-Instruct-Turbo** | $1.20 | $1.20 | FAQs | 512-1024 tokens |
| **meta-llama/Meta-Llama-3-8B-Instruct-Lite** | $0.10 | $0.10 | Final CTA | 128-512 tokens |
| **deepseek-ai/DeepSeek-R1-0528-tput** | $0.55 | $2.19 | Intro Section | 128-640 tokens |
| **deepseek-ai/DeepSeek-V3** | $1.25 | $1.25 | Final Full Blog | 1792-3584 tokens |

### Cost Per Blog Section

Estimated costs based on typical token usage:

| Section | Typical Tokens | Model Used | Est. Cost |
|---------|----------------|------------|-----------|
| **Introduction** | 400 tokens | Qwen3-Next-80B | $0.0006 - $0.006 |
| **Business Description** | 600 tokens | Qwen2.5-7B-Turbo | $0.0018 - $0.0018 |
| **FAQs** | 800 tokens | DeepSeek-V3.1 | $0.0048 - $0.010 |
| **Final CTA** | 300 tokens | gpt-oss-120b | $0.00045 - $0.0018 |
| **Short CTA** | 150 tokens | gemma-3n-E4B | $0.00003 - $0.00006 |
| **References** | 250 tokens | gpt-oss-20B | $0.000125 - $0.0005 |
| **Full Blog Assembly** | 2500 tokens | DeepSeek-V3 | $0.03125 - $0.03125 |

**Total Estimated Cost per Blog:** $0.04 - $0.05 USD

### Monthly Cost Estimates

| Usage Level | Blogs/Month | Est. Monthly Cost |
|-------------|-------------|-------------------|
| **Light** | 10 blogs | $0.40 - $0.50 |
| **Medium** | 50 blogs | $2.00 - $2.50 |
| **Heavy** | 200 blogs | $8.00 - $10.00 |
| **Enterprise** | 1000 blogs | $40.00 - $50.00 |

> **Note:** Costs are estimates based on typical usage. Actual costs may vary based on prompt complexity, example usage, and output length.

---

## 🌐 API Documentation

### Endpoints

#### 1. Generate Blog Content

**POST** `/api/chat`

Generate blog content using AI agents with customizable prompts and variables.

**Request Body:**
```json
{
  "message": "Generate a blog about car accidents in California",
  "vars": {
    "TITLE": "What to Do After a Car Accident in California",
    "KEYWORDS": "car accident lawyer, personal injury attorney, California accident claim",
    "TEMPERATURE": "0.70",
    "BLOGTYPE": "Legal",
    "COMPANY_NAME": "Smith & Associates Law Firm",
    "CALL_NUMBER": "1-800-555-0123",
    "ADDRESS": "123 Main Street, Los Angeles",
    "STATE_NAME": "California",
    "LINK": "https://smithlawfirm.com",
    "COMPANY_EMPLOYEE": "John Smith",
    "INSERT_INTRO_QUESTION": "What should you do immediately after a car accident?",
    "INSERT_FAQ_QUESTIONS": "How long do I have to file a claim? What damages can I recover?",
    "SOURCE": "California Vehicle Code Section 20001",
    "BLOGFOREXAMPLE": [11, 12, 13],
    "BLOGPART_INTRO": [11, 12],
    "BLOGPART_FINALCTA": [11, 12],
    "BLOGPART_FAQS": [11, 12],
    "BLOGPART_BUSINESSDESC": [11],
    "BLOGPART_SHORTCTA": [11, 12],
    "PROMPT_FULLBLOG": "Write a comprehensive blog post...",
    "PROMPT_INTRO": "Write an engaging introduction...",
    "PROMPT_FINALCTA": "Write a compelling call-to-action...",
    "PROMPT_FULLFAQS": "Generate 5-7 frequently asked questions...",
    "PROMPT_BUSINESSDESC": "Write a professional business description...",
    "PROMPT_REFERENCES": "Integrate the following references...",
    "PROMPT_SHORTCTA": "Write a brief call-to-action..."
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "response": "# What to Do After a Car Accident in California\n\n[Generated blog content...]",
  "timestamp": "2026-01-27T02:30:00",
  "debug_info": {
    "blog_type": "Legal",
    "temperature": "0.70",
    "examples_fetched": {
      "full_blogs": 3,
      "intro_parts": 2,
      "finalcta_parts": 2,
      "faqs_parts": 2,
      "businessdesc_parts": 1,
      "shortcta_parts": 2
    }
  }
}
```

**Error Response (400 Bad Request):**
```json
{
  "success": false,
  "code": "EMPTY_MESSAGE",
  "message": "Message cannot be empty",
  "timestamp": "2026-01-27T02:30:00"
}
```

---

#### 2. Get Chat History

**GET** `/api/profile/history?date=YYYY-MM-DD`

Retrieve chat history for a specific date.

**Query Parameters:**
- `date` (required) - Date in YYYY-MM-DD format

**Example Request:**
```bash
GET /api/profile/history?date=2026-01-26
```

**Response (200 OK):**
```json
{
  "success": true,
  "code": "OK",
  "date": "2026-01-26",
  "rows": [
    {
      "id": 1,
      "entry": "2026-01-26T05:00:00",
      "entry_date": "2026-01-26",
      "userprompt": "Generate a blog about car accidents",
      "chatresponse": "# Car Accident Guide\n\n[Blog content...]"
    },
    {
      "id": 2,
      "entry": "2026-01-26T06:30:00",
      "entry_date": "2026-01-26",
      "userprompt": "Generate a health blog about nutrition",
      "chatresponse": "# Nutrition Guide\n\n[Blog content...]"
    }
  ]
}
```

**Error Response (404 Not Found):**
```json
{
  "success": false,
  "code": "NO_ROWS_FOR_DATE",
  "message": "No profileHistory rows found for the given entry_date.",
  "requested_date": "2026-01-26",
  "diagnostics": {
    "total_rows": 150,
    "utc_match": 0,
    "pk_match": 0
  },
  "hint": "If utc_match > 0 or pk_match > 0, your data exists but entry_date does not match the selected date due to timezone/date derivation."
}
```

---

#### 3. Get Token Statistics

**GET** `/api/stats/tokens/month`

Get token usage statistics for the current month.

**Response (200 OK):**
```json
{
  "success": true,
  "month_label": "Jan 2026",
  "daily": [
    {
      "day": "01",
      "input_words": 150,
      "output_words": 1200
    },
    {
      "day": "02",
      "input_words": 200,
      "output_words": 1500
    },
    {
      "day": "03",
      "input_words": 180,
      "output_words": 1350
    }
  ]
}
```

---

#### 4. View Database Table

**GET** `/api/db/table/<table_name>`

View contents of a database table (excludes `profilehistory` for privacy).

**Path Parameters:**
- `table_name` (required) - Name of the table to view

**Available Tables:**
- `blogdata` - Complete blog posts
- `blogparts` - Individual blog sections
- `promptdata` - Prompt templates
- `progress` - Daily progress tracking

**Example Request:**
```bash
GET /api/db/table/blogdata
```

**Response (200 OK):**
```json
{
  "success": true,
  "table": {
    "name": "blogdata",
    "columns": ["blogID", "blogText"],
    "row_count": 20,
    "rows": [
      {
        "blogID": 1,
        "blogText": "# Health Blog Example\n\n[Content...]"
      },
      {
        "blogID": 2,
        "blogText": "# Another Health Blog\n\n[Content...]"
      }
    ]
  }
}
```

**Error Response (403 Forbidden):**
```json
{
  "success": false,
  "code": "TABLE_EXCLUDED",
  "message": "This table is excluded from DB views.",
  "table": "profilehistory"
}
```

**Error Response (404 Not Found):**
```json
{
  "success": false,
  "code": "UNKNOWN_TABLE",
  "message": "Table not found.",
  "table": "nonexistent_table",
  "available": ["blogdata", "blogparts", "promptdata", "progress"]
}
```

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Important Notice:** This system is designed specifically for blog writing purposes only, for the specific client's needs as they requested.

---

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Coding Standards

- Follow PEP 8 style guide for Python code
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Write unit tests for new features
- Update documentation for API changes

---

## 📧 Contact

**Ibrahim Hussain**  
Email: [ibrahimbeaconarion@gmail.com](mailto:ibrahimbeaconarion@gmail.com)

**Project Link:** [https://github.com/ib-hussain/writers-block](https://github.com/ib-hussain/writers-block)

---

## 🙏 Acknowledgments

- [Flask](https://flask.palletsprojects.com/) - Web framework
- [LangChain](https://www.langchain.com/) - LLM framework
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Render](https://render.com/) - Hosting platform

---

<div align="center">

**Made with ❤️ for content creators**

⭐ Star this repo if you find it helpful!

</div>
