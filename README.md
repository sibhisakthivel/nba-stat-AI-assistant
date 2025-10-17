# NBA Stats AI Chatbot  

An end-to-end **Retrieval-Augmented Generation (RAG)** and **Natural Language Processing (NLP)** system designed to provide evidence-based answers to questions about NBA games and player performance.  
This project combines **semantic embeddings**, **context retrieval**, and **language generation** to demonstrate how large language models (LLMs) can reason over structured sports data with verifiable accuracy.

## Video Demo

<p align="center">
  <video src="assets/rag_chatbot_demo.mp4" width="80%" controls>
    Your browser does not support the video tag.
  </video>
</p>

### Overview  
The NBA Stats RAG Chatbot is a fully containerized AI application that integrates **NLP-driven question understanding** with **database-grounded retrieval and reasoning**.  
It connects a **PostgreSQL + pgvector** database, a **FastAPI backend**, and an **Angular frontend**, allowing users to ask natural-language basketball questions — such as  
*“Who led the Celtics in scoring on Christmas Day?”* — and receive structured, evidence-backed answers drawn from actual NBA datasets.

Unlike generic chatbots, this system emphasizes **factual grounding and explainability** through evidence-linked outputs.  
It demonstrates how NLP, embeddings, and retrieval architectures can support **sports analytics**, **data exploration**, and **interactive reporting**.

### Core Capabilities  
- End-to-end **RAG pipeline** (ingest → embed → retrieve → generate)  
- **NLP-powered query understanding** for natural-language basketball questions  
- Semantic search using **Ollama’s `nomic-embed-text`** model with **pgvector** storage  
- Evidence-linked LLM responses citing the exact database rows used  
- Modular architecture for extension to other sports or structured datasets  
- Frontend chat interface built with **Angular**, featuring an interactive evidence panel  

---

## Architecture Overview  

The NBA Stats RAG Chatbot follows a modular full-stack architecture designed for efficiency, transparency, and scalability.  
Each component of the system performs a specialized role in the **RAG (Retrieval-Augmented Generation)** pipeline.

### Backend Components  
- **Database (PostgreSQL + pgvector):**  
  Stores structured NBA data (game details, player box scores) along with vector embeddings for semantic retrieval.  
  Enables similarity search via the `pgvector` extension for fast cosine-distance queries.  

- **Embedding Engine (Ollama):**  
  Generates 768-dimensional embeddings using the `nomic-embed-text` model.  
  These embeddings are used to semantically represent both question text and database rows for context matching.  

- **API Layer (FastAPI):**  
  Acts as the bridge between the LLM and the database.  
  Handles user requests, executes SQL retrieval queries, aggregates context, and invokes LLM generation.  
  Endpoints are modularized for retrieval, embedding, and response generation.  

- **LLM Reasoning (Ollama + Llama 3.2 3B):**  
  Performs the generation step using RAG-based prompting.  
  The LLM interprets retrieved evidence rows, synthesizes reasoning, and produces structured, evidence-linked answers.

### Frontend Components  
- **Angular Web Interface:**  
  Provides a chat-based user experience for natural-language interaction.  
  Implements asynchronous API calls to the FastAPI backend and renders responses with linked evidence.  
  Includes UI elements for query history, evidence visualization, and chat session management.

### Data Flow Summary  
1. **User Query →** Sent from Angular frontend to FastAPI backend.  
2. **Embedding & Retrieval →** Query is embedded via Ollama and matched against pgvector rows in PostgreSQL.  
3. **Context Assembly →** Retrieved rows are formatted into structured context blocks.  
4. **LLM Generation →** The model generates an answer grounded in retrieved evidence.  
5. **Frontend Display →** Final response and evidence array are displayed interactively in the chat UI.

---

## Pipeline Design  

The RAG pipeline is structured around four primary stages — **Ingest**, **Embed**, **Retrieve**, and **Generate** — with each stage implemented as a distinct backend module for clarity and modularity.

### 1. Ingest  
- Raw NBA CSV data (games, teams, players, box scores) is parsed and inserted into the PostgreSQL database.  
- Each dataset is normalized to relational tables with primary keys (`game_id`, `player_id`) and indexed for efficient querying.  
- Includes lightweight preprocessing such as date normalization, column renaming, and data-type enforcement.

### 2. Embed  
- Each database row (game-level or player-level) is embedded into a 768-dimensional vector using **Ollama’s `nomic-embed-text`** model.  
- Embeddings are stored alongside source rows in **pgvector** for similarity search.  
- Implemented batching and checkpointing to optimize performance across tens of thousands of rows.

### 3. Retrieve  
- For each incoming question, the text is embedded using the same model and compared to stored vectors via cosine similarity.  
- Top-k (configurable, typically 5–8) most relevant rows are retrieved from both `game_details` and `player_box_scores` tables.  
- Retrieved context is formatted into structured text blocks for model input.

### 4. Generate  
- The retrieved evidence is injected into a structured **RAG prompt template**, providing context for the **Llama 3.2 3B** model via **Ollama**.  
- The model produces an evidence-linked natural-language answer.  
- Each response includes an `answer` field and an `evidence` array referencing the source table and row IDs.

### 5. Output Integration  
- The FastAPI backend serializes the LLM output as JSON and returns it to the Angular frontend.  
- The UI parses the evidence array to display contextual statistics alongside the generated answer.  

This modular design allows each stage (data ingestion, embedding, retrieval, or generation) to be developed, tested, or replaced independently — ensuring extensibility and reproducibility.

---

## Quick Start / Local Setup  

The project is fully containerized using **Docker Compose** for seamless local deployment of all services — database, embedding engine, backend API, and frontend UI.

### Prerequisites  
Make sure the following are installed on your system:  

- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)  
- [Python 3.11+](https://www.python.org/downloads/)  
- [Node.js 18+](https://nodejs.org/en/download/) and [Angular CLI](https://angular.io/cli)  
- [Ollama](https://ollama.com/) — for hosting the local embedding and LLM models

### 1. Clone and Configure  

Clone the repository and navigate into the project directory:  
```bash
git clone https://github.com/sibhisakthivel/nba-stat-ai-assistant.git
cd nba-stat-ai-assistant
```

Create a `.env` file in the project root with the following configuration variables:  

```bash
DB_DSN=postgresql+psycopg2://postgres:postgres@db:5432/nba
EMBED_MODEL=nomic-embed-text
LLM_MODEL=llama3.2:3b
```

These environment variables define database connectivity and model selections for both embedding and generation stages.

### 2. Start the Core Services  

Start the required containers and initialize your local database and embeddings.

Launch PostgreSQL and Ollama containers:  
```bash
docker compose up -d db ollama
docker exec ollama ollama pull nomic-embed-text
docker exec ollama ollama pull llama3.2:3b
docker compose build app
```

Initialize the database with game and player data:
```bash
docker compose run --rm app python -m backend.ingest
```

Generate embeddings for all database rows:
```bash
docker compose run --rm app python -m backend.embed
```

These steps populate the PostgreSQL instance and attach vector embeddings for semantic retrieval.

### 3. Launch the Backend  

Start the **FastAPI** server to handle embedding, retrieval, and generation requests:  

```bash
docker compose run --rm --service-ports app uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
```

Once running, the backend API will be available at:
http://localhost:8000/api/chat

You can test the API directly using curl or any HTTP client such as Postman or Insomnia.

### 4. Launch the Frontend  

Run the **Angular** development server to start the chat interface:  

```bash
cd frontend
npm install -g @angular/cli@15.1.0 typescript@4.9.4 --force
npm install --force
npm start
```

### 🧠 5. Ask Questions  

Once both the backend and frontend are running, you can query the chatbot directly from the UI or through the API.

Example API query:  
```bash
curl -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"question": "Who scored the most points for the Lakers on December 25, 2023?"}'
```

The response includes:

- A generated natural-language answer from the LLM
- An evidence array listing the database rows used for retrieval

Example response structure:
```bash
{
  "answer": "LeBron James scored 34 points for the Lakers on December 25, 2023.",
  "evidence": [
    {"table": "player_box_scores", "id": 22300126},
    {"table": "game_details", "id": 22300087}
  ]
}
```

This ensures every response is traceable and grounded in real statistical data.

### 6. Service Summary  

| Component | Description | Port |
|------------|--------------|------|
| **PostgreSQL + pgvector** | Structured database for NBA data and semantic embeddings | `5432` |
| **Ollama** | Local embedding and LLM inference engine | `11434` |
| **FastAPI** | Backend API for retrieval and response generation | `8000` |
| **Angular** | Frontend chat interface for interactive querying | `4200` |

Once all services are running, open your browser to **[http://localhost:4200](http://localhost:4200)** to begin interacting with the chatbot.  
You can ask natural-language questions about NBA games, and each response will display the underlying **evidence rows** used to generate the answer.

---

## Features & Capabilities  

The NBA Stats RAG Chatbot demonstrates how modern **NLP** and **retrieval-augmented generation (RAG)** techniques can be applied to structured sports data.  
Each feature was designed to improve accuracy, interpretability, and user interactivity.

### Core Features  
- **RAG Pipeline Architecture** – integrates retrieval, embedding, and LLM reasoning into a unified workflow.  
- **Semantic Search** – retrieves relevant game and player records using cosine similarity on pgvector embeddings.  
- **Evidence-Based Answers** – every response cites the database rows used for reasoning, ensuring transparency and verifiability.  
- **FastAPI Backend** – modularized endpoints for embedding, retrieval, and generation, supporting extensibility and experimentation.  
- **Angular Frontend** – interactive chat interface with a live evidence visualization panel.  
- **Local LLM Hosting** – fully offline execution using **Ollama** with `llama3.2:3b` and `nomic-embed-text` models.  

### Technical Highlights  
- **PostgreSQL + pgvector** used for scalable semantic retrieval across tens of thousands of NBA data rows.  
- **Efficient batching and progress tracking** for large-scale embedding generation.  
- **Prompt optimization and structured output formatting** for consistent LLM responses.  
- **Docker-based orchestration** for reproducible, multi-service local deployment.  

These capabilities collectively enable a transparent, self-contained AI system that answers factual basketball questions with interpretable reasoning — a prototype for scalable, domain-specific RAG systems.

## Deployment & Engineering Notes  

This section documents the end-to-end deployment process, engineering design choices, and practical challenges encountered while developing and running the NBA Stats RAG Chatbot.

### Deployment Stack & Workflow  
The system was deployed locally using **Docker Compose**, enabling isolated orchestration of all services.  
- **PostgreSQL (with pgvector):** persistent data and embedding storage  
- **Ollama service:** local LLM and embedding model host  
- **FastAPI backend:** handles ingestion, embedding, retrieval, and generation logic  
- **Angular frontend:** runs independently in a local development server, consuming the backend API  

Each service runs in a dedicated container and communicates through Docker’s internal network, providing full portability and environment reproducibility.

### Engineering Process  
The development process emphasized modularity, transparency, and testability:
- Designed clear separation between *data ingestion*, *embedding*, and *generation* modules.  
- Added progress logging and batching during embedding to handle tens of thousands of rows efficiently.  
- Integrated environment variables for model configuration (`EMBED_MODEL`, `LLM_MODEL`) to enable quick model swaps.  
- Implemented structured JSON responses for better frontend parsing and evidence visualization.

### Challenges Faced & Solutions  

| Challenge | Description | Solution |
|------------|--------------|-----------|
| **Embedding Runtime** | Large dataset embedding was slow due to unbatched requests. | Introduced batch processing (500 rows/batch) with progress tracking. |
| **LLM Response Latency** | Initial model inference was slow due to heavy context size. | Reduced context size and optimized prompt templates. |
| **Evidence Alignment** | Some responses referenced incorrect rows. | Improved retrieval ranking logic and post-filtering based on date/team match. |
| **Frontend-Backend Sync** | API endpoints needed cross-origin access for Angular. | Configured CORS middleware in FastAPI. |

### Optimization Highlights  
- Streamlined SQL queries for retrieval to minimize redundant vector comparisons.  
- Added automatic retry logic for embedding failures.  
- Introduced clear separation of evidence and context blocks to simplify model reasoning.  
- Tuned Angular rendering for faster chat updates.  

### Future Improvements  
Planned extensions to further enhance accuracy, scalability, and usability:
- **Cloud Deployment:** containerize the full stack for AWS ECS or Azure Web Apps.  
- **Evaluation Dashboard:** visualize retrieval accuracy and evidence coverage using Streamlit or Dash.  
- **Hybrid Vector Search:** integrate FAISS or Weaviate for faster large-scale retrieval.  
- **Multi-Model Support:** experiment with other embedding and generation models via environment toggles.  
- **User Analytics Layer:** log queries, latency, and model performance for iterative fine-tuning.  

---

## Deployment Expansion and Runtime Challenges

After completing the initial local implementation, the project was extended to explore **cloud deployment and hosted inference** workflows.  
This phase aimed to evaluate how the RAG chatbot performs under production constraints and to identify the trade-offs between local and hosted LLM architectures.

### 1. Migration from Ollama → Grok API (Groq)
The first major update involved replacing local inference through **Ollama** with hosted LLM calls to **Grok** (via the `GROQ_API_KEY`).  
This change enabled easier remote deployment, lighter containers, and compatibility with Render’s limited resource tiers while maintaining semantic retrieval through pgvector.

### 2. Backend Deployment on Render
The FastAPI backend was containerized and deployed to **Render**, using a managed PostgreSQL instance for persistent storage.  
Render simplified the build process but imposed key constraints on the free tier:
- **512 MB memory cap** often caused inference and embedding jobs to fail mid-execution.  
- **Automatic sleep after inactivity** resulted in 30–60 s cold-start delays on the first user request.  
- **Request timeouts** occasionally interrupted long-running LLM responses.  

Despite these limitations, Render proved useful for rapid iteration and API endpoint validation.

### 3. Frontend Deployment on Vercel
The Angular frontend was successfully deployed to **Vercel**, integrated with the live Render backend API.  
This allowed browser-based querying of the deployed RAG pipeline and testing of full client–server interactions in a hosted environment.

### 4. Runtime and Model Performance
Across both local and hosted versions, **response latency** remained the most significant challenge.  
Typical end-to-end query times ranged from **30–60 seconds**, primarily due to:
- Long similarity-search computations in pgvector over large datasets.  
- LLM generation overhead for multi-row evidence synthesis.  
- Cold-start delays and memory constraints on free-tier infrastructure.  

These experiments highlighted the practical limitations of running RAG pipelines on low-resource environments and motivated future optimizations, including:
- Asynchronous inference and streaming responses.  
- Persistent service tiers to eliminate cold starts.  
- Model distillation or smaller-context fine-tuning for faster reasoning.

> **Next Steps**  
> - Evaluate higher-memory tiers or GPU-accelerated hosting for consistent uptime.  
> - Introduce caching layers for repeated queries and embeddings.  
> - Continue profiling long-running Grok/Ollama responses to balance speed and accuracy.

---

### Author  
**Sibhi Sakthivel**  
M.S. Molecular Science & Software Engineering, UC Berkeley  
sibhisak@gmail.com
sibhisakthivel@berkeley.edu 
[LinkedIn](https://www.linkedin.com/in/sibhi-sakthivel-3ab23113b)
[GitHub](https://github.com/sibhisakthivel)
