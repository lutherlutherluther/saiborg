# Saiborg 🤖

A powerful Slack bot that combines AI-powered RAG (Retrieval-Augmented Generation) with Monday.com CRM integration. Saiborg helps your team answer questions from company documents and manage customer relationships directly from Slack.

## Features

- **📚 RAG-powered Q&A**: Ask questions about your company documents (PDFs) and get intelligent answers
- **📊 Monday.com Integration**: Search and manage customers/leads directly from Slack
- **✉️ Email Drafting**: Automatically generate follow-up emails based on CRM data
- **📅 Meeting Prep**: Get prepared for customer meetings with context and suggested questions
- **🎯 Next Steps**: Receive actionable recommendations for your sales pipeline
- **🇩🇰 Danish Language Support**: Fully optimized for Danish business communication

## Project Structure

### Core Files

- **`app.py`** - Main Slack bot application. Handles Slack events, routes to RAG or Monday.com modes, and manages all bot interactions.

- **`monday_client.py`** - Monday.com API client. Provides functions to search customers, fetch all items, and interact with your CRM board.

- **`build_index.py`** - Script to build the Chroma vector database from PDF documents. Run this to index your company documents for RAG functionality.

- **`monday_test.py`** - Simple test script to verify Monday.com API connection.

### Configuration Files

- **`requirements.txt`** - Python dependencies needed to run the bot.

- **`Procfile`** - Process file for deployment platforms (Render, Heroku).

- **`render.yaml`** - Render.com deployment configuration.

- **`runtime.txt`** - Python version specification.

- **`saiborg.service`** - Systemd service file for Linux VPS deployment.

- **`.gitignore`** - Git ignore rules (excludes `.env`, `venv/`, `chroma_db/`, etc.).

- **`DEPLOYMENT.md`** - Detailed deployment guide for running 24/7.

### Directories

- **`data/`** - Place your PDF documents here. They will be indexed by `build_index.py`.

- **`chroma_db/`** - Vector database storage (auto-generated, excluded from git).

- **`venv/`** - Python virtual environment (excluded from git).

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file with:

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
GOOGLE_API_KEY=your-google-api-key
MONDAY_API_KEY=your-monday-api-key  # Optional
MONDAY_CUSTOMER_BOARD_ID=5085798849  # Optional
CHROMA_DB_PATH=chroma_db  # Optional
```

### 3. Build the Vector Index (Optional)

If you want RAG functionality, add PDFs to `data/` and run:

```bash
python3 build_index.py
```

### 4. Run the Bot

```bash
python3 app.py
```

## Usage in Slack

### General Questions (RAG Mode)
```
@saiborg Hvad er vores returpolitik?
@saiborg Hvad koster produkt X?
```

### Monday.com CRM Queries
```
@saiborg Find kunden Vocast i Monday
@saiborg Hvilke leads har vi i Monday?
```

### Email Drafting
```
@saiborg Find kunden X i Monday og skriv en mail hvor jeg følger op
@saiborg Lav en opfølgningsmail for leadet Y
```

### Meeting Preparation
```
@saiborg Forbered møde med kunden X i morgen
@saiborg Mødeforberedelse til salgsmødet med firma Y
```

### Next Steps
```
@saiborg Hvad er næste skridt for kunden X i Monday?
@saiborg Hvad bør jeg gøre nu med leadet Y?
```

## Deployment

See `DEPLOYMENT.md` for detailed instructions on deploying to:
- Render.com (recommended)
- Railway.app
- DigitalOcean
- Fly.io

## Technologies

- **Slack Bolt** - Slack bot framework
- **LangChain** - LLM orchestration
- **Google Gemini** - AI model (gemini-2.0-flash)
- **Chroma** - Vector database
- **Monday.com API** - CRM integration

## License

Private project - All rights reserved
