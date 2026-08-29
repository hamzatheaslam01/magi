# MAGI Setup Guide

This guide explains how to install and run MAGI locally.

## Requirements

Before running MAGI, make sure you have:

- Python 3.10 or newer
- Node.js
- npm
- Git
- An OpenRouter account
- An OpenRouter API key

---

## 1. Clone the Repository

Clone the repository:

```bash
git clone https://github.com/hamzatheaslam01/magi.git
```

Enter the project directory:

```bash
cd magi
```

The project structure should look similar to:

```text
magi/
├── README.md
├── SETUP.md
├── .gitignore
├── backend/
└── frontend/
```

---

# 2. Backend Setup

Open a terminal in the project root and enter the backend directory:

```powershell
cd backend
```

## Create the Virtual Environment

Create a Python virtual environment:

```powershell
python -m venv .venv
```

## Activate the Virtual Environment

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

You should see something similar to:

```text
(.venv) PS C:\...\magi\backend>
```

If PowerShell prevents the activation script from running, use:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate the environment again:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

# 3. Install Backend Dependencies

With the virtual environment activated, install the backend dependencies.

If the project contains a `requirements.txt` file:

```powershell
pip install -r requirements.txt
```

If there is no `requirements.txt`, install the required packages manually:

```powershell
pip install fastapi uvicorn python-dotenv openai pydantic
```

---

# 4. Configure OpenRouter

MAGI uses OpenRouter to communicate with the language model.

Create this file:

```text
backend/.env
```

Add:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
```

Replace `your_openrouter_api_key` with your actual OpenRouter API key.

For example:

```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx
```

## Important

Never commit your API key to GitHub.

The repository's `.gitignore` excludes:

```text
.env
backend/.env
```

Your actual API key should remain only in your local `backend/.env` file.

---

# 5. Start the Backend

Make sure you are inside:

```text
magi/backend
```

and that the virtual environment is activated.

Start FastAPI:

```powershell
uvicorn app.main:app --reload --port 8000
```

The backend should start at:

```text
http://localhost:8000
```

Keep this terminal running.

## Backend Health Check

Open:

```text
http://localhost:8000/health
```

You should receive:

```json
{
  "status": "online"
}
```

If you receive this response, the backend is running correctly.

---

# 6. Frontend Setup

Open a second terminal.

Return to the project root:

```powershell
cd C:\Users\HP\OneDrive\Desktop\magi
```

Then enter the frontend directory:

```powershell
cd frontend
```

Install the frontend dependencies:

```powershell
npm install
```

---

# 7. Start the Frontend

Start the Next.js development server:

```powershell
npm run dev
```

The frontend should start at:

```text
http://localhost:3000
```

Open that address in your browser.

---

# 8. Running MAGI

MAGI requires both the backend and frontend to be running.

You should have two terminals open.

## Terminal 1 — Backend

```powershell
cd magi\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

## Terminal 2 — Frontend

```powershell
cd magi\frontend
npm run dev
```

Then open:

```text
http://localhost:3000
```

---

# 9. How the Frontend Connects to the Backend

The frontend communicates with the FastAPI backend through HTTP and Server-Sent Events (SSE).

The main streaming endpoint is:

```text
POST /debate/stream
```

The frontend sends the user's question to the backend.

The backend then runs the real MAGI debate engine and streams events back to the frontend as they happen.

The general architecture is:

```text
User
 │
 ▼
Next.js Frontend
 │
 │ HTTP / SSE
 ▼
FastAPI Backend
 │
 ▼
Streaming Debate Engine
 │
 ├── MELCHIOR
 ├── BALTHASAR
 └── CASPER
 │
 ▼
OpenRouter
 │
 ▼
AI Responses
 │
 ▼
SSE Stream
 │
 ▼
Next.js Frontend
```

The interface therefore displays the actual backend process rather than simulating a debate on the frontend.

---

# 10. MAGI Debate Process

Each question passes through four main rounds.

```text
ROUND 1
INITIAL POSITIONS
       │
       ▼
ROUND 2
DIRECTED CHALLENGES
       │
       ▼
ROUND 3
RESPONSES
       │
       ▼
ROUND 4
RECONSIDERATION
       │
       ▼
MAGI SYNTHESIS
       │
       ▼
CONSENSUS
```

During the process, the frontend receives events from the backend and updates the interface in real time.

---

# 11. MAGI Units

MAGI currently uses three reasoning agents:

```text
MELCHIOR
BALTHASAR
CASPER
```

Each agent independently analyzes the question before interacting with the other agents.

The debate allows the agents to:

1. Form an initial position.
2. Challenge another agent.
3. Respond to criticism.
4. Reconsider their position.
5. Produce a final position.

The system then produces a final synthesis and consensus.

---

# 12. Confidence Scores

MAGI displays confidence based on the confidence values returned by the reasoning agents.

The frontend does not randomly generate the confidence percentage.

The final confidence is calculated from the agents' final confidence values.

Confidence should be interpreted as:

> Model-assessed confidence in the position.

It should not be interpreted as a statistically calibrated probability that the conclusion is objectively correct.

---

# 13. Common Problems

## `ERR_CONNECTION_REFUSED :8000`

If the browser displays:

```text
Failed to fetch
net::ERR_CONNECTION_REFUSED
```

the backend is probably not running.

Start the backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Then check:

```text
http://localhost:8000/health
```

You should receive:

```json
{
  "status": "online"
}
```

---

## `OPENROUTER_API_KEY is not set`

If the backend reports:

```text
OPENROUTER_API_KEY is not set
```

check that:

1. The file exists at:

```text
backend/.env
```

2. It contains:

```env
OPENROUTER_API_KEY=your_actual_api_key
```

3. The backend was restarted after creating or modifying `.env`.

---

## Port 8000 Already in Use

If Uvicorn reports that port `8000` is already in use, another backend process may already be running.

Check which process is using the port:

```powershell
netstat -ano | findstr :8000
```

You can then stop the relevant process if necessary.

---

## Port 3000 Already in Use

If Next.js reports that port `3000` is already in use, another frontend process may already be running.

You can either use the existing process or stop it before starting Next.js again.

---

## PowerShell Cannot Activate `.venv`

If PowerShell blocks:

```powershell
.\.venv\Scripts\Activate.ps1
```

run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try again:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

# 14. Development Workflow

During development, keep two terminals open.

### Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm run dev
```

Both development servers automatically reload when relevant files change.

---

# 15. Updating the Project

If you pull a newer version of MAGI:

```powershell
git pull
```

If backend dependencies have changed:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If frontend dependencies have changed:

```powershell
cd frontend
npm install
```

Restart the backend and frontend after updating.

---

# 16. Stopping MAGI

To stop either development server, press:

```text
Ctrl + C
```

in its terminal.

---

# 17. Security

Never commit the following files or directories:

```text
backend/.env
.env
backend/.venv/
```

In particular, never publish:

```text
OPENROUTER_API_KEY
```

to GitHub.

If an API key is accidentally committed or exposed, revoke it immediately and generate a new key.

---

# 18. Quick Start

Once MAGI has already been installed, running it requires two terminals.

### Terminal 1

```powershell
cd magi\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

### Terminal 2

```powershell
cd magi\frontend
npm run dev
```

Then open:

```text
http://localhost:3000
```

Check that the backend is online:

```text
http://localhost:8000/health
```

Expected response:

```json
{
  "status": "online"
}
```

If the health check works and the frontend is running, MAGI is ready to use.