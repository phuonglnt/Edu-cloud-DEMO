# Edu-cloud DEMO

LLM-based teaching assistant integrated into Moodle.

- Students ask questions and get answers built from the course materials, with the source cited. 
- Teachers generate quizzes from the same materials. 
- Course files uploaded to Moodle are sent automatically to the assistant AI.


## Services

| Service | Port | Role | Source |
| --- | --- | --- | --- |
| `moodle` | 8080 | Course platform | Built from our Dockerfile |
| `postgres` | internal | Moodle database | Existing image |
| `open-webui` | 3001 | AI assistant, knowledge bases | Existing image |
| `quiz-api` | 8001 | Quiz generation | Built from our Dockerfile |
| `sync-moodle` | none | Sends Moodle files to the assistant | Built from our Dockerfile |

External dependency: the Google Gemini API provides the language model.

PostgreSQL has no published port: only the services in this compose file can reach it.

## How it works

**Asking a question.** The student opens the assistant from the Moodle menu, types `#` to select the course, then asks. 
Open WebUI retrieves the relevant passages from the course materials and sends them to Gemini with the question. 
The answer comes back with the document name and page.

**Generating a quiz.** The teacher opens the quiz interface, picks a course, a topic and a number of questions. 
The API finds the knowledge base named after the course and asks the assistant to write the quiz from it.

**Uploading materials.** When a teacher adds a PDF to a Moodle course, `sync-moodle` detects it, knowl
creates a knowledge base named after the course if needed, and uploads the file. Nothing else to do.

## Requirements

- Docker with Docker Compose
- A Gemini API key, created on `aistudio.google.com/apikey`
- An Open WebUI API key, created once the stack is running running
        + **Settings → Authentication → Create API key**
        + **Admin Panel → Account → API key**

## Getting started

```bash
cp .env.example .env     
docker compose up -d --build
docker compose ps
```

## fill in the keys
```bash
OPENAI_API_KEY=         # Gemini API Key
ASSISTANT_API_KEY=      # Open Webui API Key
MOODLE_ADMIN_USER=admin
MOODLE_ADMIN_PASSWORD=
MOODLE_ADMIN_EMAIL=
```

The first start takes a few minutes: Moodle initialises its database and Open WebUI sets up.

Then:

1. Open `http://localhost:8080` and log in to Moodle with the admin account from `.env`.
2. Open `http://localhost:3001` and create the assistant account. The first account created is the administrator.

3. Restart the services if need

```bash
docker compose up -d --force-recreate quiz-api sync-moodle
```

4. In Moodle, create a course and upload a PDF. Within a few minutes it appears as a knowledge base in the assistant.

### Link in the Moodle menu

Site administration → Appearance → Advanced theme settings → Custom menu items:

```
Accueil|/
Assistant IA|http://localhost:3001
```

This field **replaces** the main menu, so the home entry has to be declared as well. (Not a good design)

Services reach each other by **service name**, not by IP address: `postgres:5432`, `open-webui:8080`.

~~## Deploying on the university server (optional)

Two additions are needed, because the server only reaches the Internet through a proxy.

**Proxy during image builds.** A container does not inherit the host configuration, so `apt-get` and `pip` fail without it:

```yaml
    build:
      context: .
      args:
        http_proxy: http://cache.univ-pau.fr:3128
        https_proxy: http://cache.univ-pau.fr:3128
```

**Indexing through the API.** Open WebUI normally downloads an embedding model on first start, which the proxy blocks and which leaves the container hanging. Add to `open-webui`:

```yaml
      - HTTPS_PROXY=http://cache.univ-pau.fr:3128
      - https_proxy=http://cache.univ-pau.fr:3128
      - RAG_EMBEDDING_ENGINE=openai
      - RAG_EMBEDDING_MODEL=models/gemini-embedding-001
```

The proxy variables apply to every outgoing request, including calls between containers, so `quiz-api` and `sync-moodle` already declare `NO_PROXY` for the internal service names.~~

## Operations

```bash
docker compose ps
docker compose logs -f sync-moodle
docker compose down                     # stop, keep the data
docker compose up -d --build            # rebuild and apply changes
```

**Never run `docker compose down -v`**: the `-v` option deletes the volumes, and with them the Moodle database, the assistant accounts and the knowledge bases.

## Known limitations

- **Moodle and the assistant have separate accounts. Single sign-on would let the assistant know which courses a user is enrolled in.**
- The free Gemini tier allows 20 requests per day per model. The quota is counted per model, so several models can be configured to spread the load.
- The assistant answers even when the information is not in the course materials. In that case it uses its general knowledge, so the cited source should always be checked.
- Retrieval only returns the closest passages, so an answer can miss information located in another part of a document.
- The services run without HTTPS.
