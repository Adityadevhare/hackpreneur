\# HACKPRENEUR



\*\*From Hackathon Prototype to Real-World Product\*\*



HACKPRENEUR is a platform designed to help hackathon teams continue developing their prototypes after the event. It aims to support project readiness, milestone planning, feedback, and connections with relevant mentors and communities.



\## Tech Stack



\### Frontend

\- React

\- TypeScript

\- Vite

\- CSS



\### Backend

\- Python

\- FastAPI

\- SQLAlchemy

\- SQLite

\- Pydantic



\## Project Structure



```text

hackpreneur/

├── backend/

│   ├── database.py

│   ├── init\_db.py

│   ├── main.py

│   ├── models.py

│   └── requirements.txt

├── frontend/

│   ├── public/

│   ├── src/

│   ├── package.json

│   └── vite.config.ts

├── .gitignore

└── README.md

```



\## Getting Started



\### Prerequisites

\- Python 3.10 or later

\- Node.js and npm



\### 1. Clone the repository



```bash

git clone <YOUR\_REPOSITORY\_URL>

cd hackpreneur

```



\### 2. Start the backend



Open a terminal:



```powershell

cd backend

python -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

python -m pip install -r requirements.txt

python init\_db.py

uvicorn main:app --reload

```



Backend: `http://127.0.0.1:8000`



API documentation: `http://127.0.0.1:8000/docs`



\### 3. Start the frontend



Open a second terminal from the project root:



```powershell

cd frontend

npm install

npm run dev

```



Frontend: `http://localhost:5173`



\## Current API Endpoints



| Method | Endpoint | Description |

|---|---|---|

| GET | `/` | Welcome message |

| GET | `/api/health` | API health check |

| POST | `/api/projects` | Create a project |

| GET | `/api/projects` | Retrieve projects |



\## Database



HACKPRENEUR currently uses SQLite with SQLAlchemy. The database is initialized using `backend/init\_db.py`.



The local database file is excluded from Git and is recreated when the initialization script runs.



\## Project Status



This project is under active development. Features and architecture may change as development progresses.

