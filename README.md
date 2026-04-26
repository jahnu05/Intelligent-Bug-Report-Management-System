# Intelligent Bug Report Management System

## Contributor Intelligence Subsystem

This subsystem automates the collection of GitHub repository data, profiles contributors using AI, and provides an intelligent assignment engine for bug reports.

### Key Features

- **Automated Data Ingestion**: Pulls commit history and issue data from GitHub.
- **AI Profiling**: Generates detailed contributor summaries and focus areas using Gemini.
- **Issue Assignment**: Matches new bug reports to the most qualified contributors based on their historical work.
- **Real-time Synchronization**: Uses **GitHub Webhooks** to update issues automatically as they are opened or closed.
- **Live Dashboard**: A modern, real-time UI with SSE (Server-Sent Events) for instant updates and monitoring.
- **State Persistence**: Remembers your current repository view using local storage.

---

### Prerequisites

- **Python 3.10+**
- **MongoDB Atlas** (or local MongoDB)
- **ngrok** (for local testing of GitHub Webhooks)
- **GitHub Classic Token** (with `repo` scopes)
- **Google Gemini API Key**

---

### Setup & Run Instructions

```bash
# 1) Clone and enter directory
cd Intelligent-Bug-Report-Management-System

# 2) Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3) Configure environment
# Copy .env.example to .env and fill in:
# - MONGODB_URI, GITHUB_TOKEN, GEMINI_API_KEY
cp .env.example .env

# 4) Start the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 5) Expose for Webhooks (Required for real-time sync)
# In a NEW terminal:
ngrok http 8000
```

---

### GitHub Webhook Configuration

To enable real-time synchronization between your GitHub repo and the dashboard:

1.  **Get Public URL**: Start ngrok and copy the `Forwarding` URL (e.g., `https://abcd-123.ngrok-free.app`).
2.  **Add Webhook on GitHub**:
    - Go to your repository **Settings** -> **Webhooks** -> **Add webhook**.
    - **Payload URL**: `https://<your-ngrok-url>/webhooks/github`
    - **Content type**: `application/json` (**REQUIRED**)
    - **Secret**: Optional (matches `GITHUB_WEBHOOK_SECRET` in `.env`).
    - **Trust**: Check "Just the `push` event" OR "Let me select individual events" and check **Issues**.
3.  **Verify**: You should see a green checkmark in GitHub's "Recent Deliveries" after the first event.

> [!TIP]
> **Multi-Repository Support**: You can use the same ngrok URL for multiple repositories. The system automatically routes events to the correct records based on the repository name in the payload.

---

### Dashboard Usage

1.  **Access**: Open `http://localhost:8000` in your browser.
2.  **Load Repo**: Enter `owner/repo` (e.g., `pandas-dev/pandas`) and click **Load Repository**.
3.  **Initial Sync**:
    - Click **Sync** to pull commit history and build contributor profiles.
    - Click **Fetch** to pull existing issues from GitHub.
4.  **Real-time**: Once loaded, any new issue activity on GitHub will appear on the dashboard instantly without refreshing!

---

### API Documentation

The system exposes a comprehensive REST API. For detailed design notes, schema details, and architectural decisions, see:
- [Contributor Data Docs](./controbutor%20data%20docs.md)
- [Issue Assignment Docs](./issue%20assignment%20docs.md)

### Development & Testing

```bash
# Run unit/smoke tests
pytest -q

# Manual Health Check
curl -s http://localhost:8000/health
```