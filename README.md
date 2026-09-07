# FinPilot

### An AI Financial Operating System for Students

FinPilot is an AI-powered financial decision platform designed to help students make **smarter financial decisions before they spend**.

Instead of acting as a simple expense tracker or chatbot, FinPilot combines financial analytics, machine learning, OCR, and multi-agent AI to understand a student's financial situation and provide actionable, explainable guidance.

---

## 🚀 Why FinPilot?

Students often make financial decisions without knowing the long-term impact on their cash flow, savings, and financial stability.

FinPilot brings these signals together in one place:

- **Understand** current spending and cash flow
- **Predict** future financial pressure
- **Simulate** the impact of financial decisions
- **Scan** bills and receipts automatically
- **Debate** important decisions using multiple specialized AI agents
- **Chat** with an AI financial copilot
- **Track** overall financial health

The goal is simple:

> **Help students make better financial decisions before they spend.**

---

## ✨ Core Features

### 🧠 AI Financial Boardroom

The flagship feature of FinPilot.

A financial decision is evaluated by multiple specialized AI agents instead of relying on a single response.

**Agents include:**

- 📊 **Budget-Bot** — analyzes affordability, surplus, EMI-to-income and budget allocation
- 🛡️ **Risk-Radar** — identifies financial risks and downside scenarios
- 🔭 **Horizon-Planner** — evaluates longer-term financial impact
- 👑 **The Chairman** — synthesizes the agents' opinions into a final decision
- 😈 **Devil's Advocate** — challenges the decision and searches for overlooked risks

This produces an explainable decision rather than a simple yes/no answer.

---

### 🎯 Decision Simulator

Explore the financial impact of a decision before committing to it.

Users can model scenarios and understand how changes can affect:

- Monthly cash flow
- Savings
- Expenses
- Financial stability
- Future affordability

---

### 📈 Cash Flow Prediction

FinPilot analyzes financial patterns to estimate future cash-flow behavior and help users identify potential financial pressure before it happens.

---

### 🧾 AI Receipt & Bill Scanner

FinPilot combines OCR with LLM-based interpretation to extract useful information from receipts and bills.

The pipeline is designed to handle noisy OCR output and convert unstructured documents into usable financial data.

---

### 💳 Spending Analytics

Understand where money is going through spending analysis and category-level insights.

FinPilot can also use historical spending patterns to provide forward-looking spending insights.

---

### 🤖 FinCopilot

A conversational AI financial assistant that lets users interact with their financial information naturally.

Users can ask questions about spending, savings, cash flow, and financial decisions without navigating through multiple screens.

---

### ❤️ Financial Health Score

FinPilot summarizes important financial signals into an easy-to-understand financial health indicator, helping students quickly understand their overall position.

---

## 🖥️ Screenshots

### Dashboard

![FinPilot Dashboard](screenshots/finpilot-dashboard(1).png)

### AI Financial Boardroom

![AI Financial Boardroom](screenshots/finpilot-boardroom(1).png)

### Decision Simulator

![Decision Simulator](screenshots/finpilot-decision-simulator(1).png)

### AI Bill & Receipt Scanner

![AI Bill Scanner](screenshots/finpilot-bill-scanner(1).png)

### Spending Insights

![Spending Insights](screenshots/finpilot-spending-insights(1).png)

### Cash Flow Prediction

![Cash Flow Prediction](screenshots/finpilot-cash-flow(1).png)

## 🏗️ System Architecture

```text
                    ┌─────────────────────────┐
                    │       FinPilot UI       │
                    │     React + Vite        │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │       FastAPI API       │
                    │        Python           │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
       ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
       │ Financial   │    │ OCR + LLM   │    │ ML /        │
       │ Analytics   │    │ Fusion      │    │ Prediction   │
       └─────────────┘    └─────────────┘    └─────────────┘
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │   Multi-Agent AI        │
                    │   Financial Boardroom    │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Explainable Financial   │
                    │ Decision / Recommendation│
                    └─────────────────────────┘
````

---

## 🛠️ Technology Stack

| Layer              | Technology                      |
| ------------------ | ------------------------------- |
| Frontend           | React, Vite, Material UI        |
| Backend            | Python, FastAPI                 |
| AI / LLM           | Groq API, GPT-OSS 120B          |
| Multi-Agent System | Specialized financial AI agents |
| OCR                | PaddleOCR                       |
| ML / Data          | Pandas, NumPy, Scikit-learn     |
| Database           | SQLite                          |
| Version Control    | Git, GitHub                     |

---

## 🔄 How FinPilot Works

### 1. Capture financial information

Users provide financial data manually or through scanned bills and receipts.

### 2. Process and structure the data

OCR, parsing, validation, analytics, and ML components transform raw information into structured financial signals.

### 3. Analyze the financial situation

FinPilot evaluates income, expenses, savings, debt obligations, spending behavior, and projected cash flow.

### 4. Simulate decisions

Users can test the impact of a financial decision before taking it.

### 5. Run the Financial Boardroom

For important decisions, multiple specialized agents independently evaluate the scenario.

### 6. Produce an explainable verdict

The Chairman synthesizes the discussion, while the Devil's Advocate challenges the conclusion.

The result is a decision supported by **numbers, risks, reasoning, and context**.

---

## ⚙️ Running FinPilot Locally

### Prerequisites

* Python 3.x
* Node.js and npm
* A Groq API key

### 1. Clone the repository

```bash
git clone https://github.com/Pray1503/FinCopilot.git
cd FinCopilot
```

### 2. Open the main project

The working application is located under:

```text
FinCopilot-semi-final/FinCopilot-mega
```

```bash
cd FinCopilot-semi-final/FinCopilot-mega
```

### 3. Configure environment variables

Create a `.env` file and add:

```env
GROQ_API_KEY=your_groq_api_key
```

### 4. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 5. Start the backend

```bash
python -m uvicorn api.main:app --reload --port 8000
```

### 6. Start the frontend

Open another terminal:

```bash
cd finpilot-ui
npm install
npm run dev
```

Then open the local Vite URL shown in the terminal.

---

## 📁 Project Structure

```text
FinCopilot-mega/
├── agents/          # Multi-agent financial decision system
├── api/             # FastAPI backend
├── cashflow/        # Cash-flow analysis and prediction
├── copilot/         # Conversational financial assistant
├── data/            # Application data
├── fusion/          # OCR + LLM fusion
├── llm/             # LLM-related components
├── ml/              # Machine-learning components
├── ocr/             # OCR pipeline
├── pages/           # Application pages
├── services/        # Shared backend services
├── shared/          # Shared utilities
├── simulator/       # Decision simulation
├── uploads/         # Uploaded documents
└── finpilot-ui/     # React frontend
```

---

## 🔐 Responsible Financial Assistance

FinPilot is designed as an educational and decision-support system for students.

Its recommendations should be treated as **decision support, not professional financial advice**. Users should independently verify important financial decisions and consider their own circumstances.


## 🎯 Project Vision

FinPilot aims to move student finance from:

**"Where did my money go?"**

to:

**"What should I do before I spend it?"**

**FinPilot — an AI Financial Operating System for Students.**


