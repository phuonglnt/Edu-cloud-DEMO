# Edu-cloud DEMO

*[Version française](README.fr.md)*

Edu-cloud adds an LLM-based teaching assistant to Moodle, which answers students from their own course materials.

- **The teacher uploads slides and documents, as PDF files, to Moodle.** They serve both as course material and as the source for the assistant: they are sent to it automatically, with nothing else to do.
- **The student asks the assistant questions** and gets an answer built from these materials, with the document and page cited.
- **The teacher generates quizzes** from the same materials.
- **The free plan allows 5 questions.** Beyond that, the assistant blocks the chat and the student moves to a higher tier (GOLD or PLATINUM) from the "Abonnement" page in Moodle, through a simulated payment.
- **A dashboard** tracks usage: number of questions, tier and quota of each user.


## Services

| Service | Port | Role | Source |
| --- | --- | --- | --- |
| `moodle` | 8080 | Course platform | Built from our Dockerfile |
| `postgres` | internal | Moodle database | Existing image |
| `open-webui` | 3001 | AI assistant, knowledge bases | Existing image |
| `quiz-api` | 8001 | Quiz generation | Built from our Dockerfile |
| `sync-moodle` | none | Sends Moodle files to the assistant | Built from our Dockerfile |
| `stats-api` | 8002 | Statistics, quotas and subscriptions | Image `ple002/educloud-stats-api:v3`, deployed as a Swarm service |

External dependency: the Google Gemini API provides the language model.

The Groq API provides the model of `stats-api` (dashboard report, tutor), so that it does not use up the free Gemini quota.

## How it works

**Asking a question.** The student opens the assistant from the Moodle menu, types `#` to select the course, then asks. 
Open WebUI retrieves the relevant passages from the course materials and sends them to Gemini with the question. 
The answer comes back with the document name and page.

**Generating a quiz.** The teacher opens the quiz interface, picks a course, a topic and a number of questions. 
The API finds the knowledge base named after the course and asks the assistant to write the quiz from it.

**Uploading materials.** When a teacher adds a PDF to a Moodle course, `sync-moodle` detects it,
creates a knowledge base named after the course if needed, and uploads the file. Nothing else to do.

**Tracking usage.** The dashboard on `http://localhost:8002` shows the number of
Moodle users and courses, and the number of questions asked to the assistant per
user, with their tier and quota. It also generates a short report written by the AI.

**Changing plan.** From the Moodle menu, the student opens the "Abonnement" page.
It shows their tier, their quota, and a simulated payment form. After an accepted
payment, `stats-api` stores the new tier in PostgreSQL. Card `4242 4242 4242 4242`
is accepted, card `4000 0000 0000 0002` is declined.

**Blocking the chat at the quota.** Once a user has reached their quota, the
assistant refuses their next question and points them to the "Abonnement" page.
The chat works again as soon as a payment is accepted.

## Service tiers

| Tier | Questions to the assistant |
| --- | --- |
| FREE | 5 |
| GOLD | 50 |
| PLATINUM | unlimited |

The tier is stored in the `abonnement` table in PostgreSQL. Every payment, accepted
or declined, is stored in the `paiement` table. Both tables are created when
`stats-api` starts.

The Moodle account and the assistant account are matched by **email address**: the
user pays with their Moodle account, and the quota applies to the Open WebUI
account that has the same address.

## Requirements

- Docker with Docker Compose
- A Gemini API key, created on `aistudio.google.com/apikey`
- An Open WebUI API key, created once the stack is running
        + **Settings → Authentication → Create API key**
        + **Admin Panel → Account → API key**

## Getting started

```bash
cp .env.example .env     
docker compose up -d --build
docker compose ps
```

## Fill in the keys
```bash
OPENAI_API_KEY=         # Gemini API Key
ASSISTANT_API_KEY=      # Open Webui API Key
MOODLE_ADMIN_USER=admin
MOODLE_ADMIN_PASSWORD=
MOODLE_ADMIN_EMAIL=
LLM_API_KEY=            # Groq API key, used by stats-api
```

The first start takes a few minutes: Moodle initialises its database and Open WebUI sets up.

Then:

1. Open `http://localhost:8080` and log in to Moodle with the admin account from `.env`.
2. Open `http://localhost:3001` and create the assistant account. The first account created is the administrator.

3. Restart the services if needed

```bash
docker compose up -d --force-recreate quiz-api sync-moodle
```

4. In Moodle, create a course and upload a PDF. Within a few minutes it appears as a knowledge base in the assistant.

**Assistant port.** Locally, the assistant is published on port 3001. On the university server it uses port 3000: replace `3001` with `3000` in the addresses of this document. The matching lines are commented in `docker-compose.yml` and `docker-stack-stats.yml`.

**No model visible with a user account.** By default, only the assistant's administrators see the models. In Admin Panel → Models, open each model to offer and make it public.

**Syncing materials for a demo.** `sync-moodle` sends the PDFs to the assistant at startup, then every `SYNC_INTERVAL` seconds (24 hours in `docker-compose.yml`). For a PDF uploaded during a demo to show up right away, restart the service:

```bash
docker compose restart sync-moodle
```

On the server, from another folder: `docker compose -f ~/educloud/docker-compose.yml restart sync-moodle`.

**Installing Moodle.** On the very first start, once `.env` is filled in, run `./install-moodle.sh` once: the script creates the Moodle database and the administrator account.

**Starting `stats-api`.** `docker compose up -d` does not start `stats-api`: see "Deploying with Docker Swarm".

### Link in the Moodle menu

Site administration → Appearance → Advanced theme settings → Custom menu items:

```
Accueil|/
Assistant IA|http://localhost:3001
Abonnement|/local/abonnement/index.php
```

This field **replaces** the main menu, so the home entry has to be declared as well. (Not a good design)

Services reach each other by **service name**, not by IP address: `postgres:5432`, `open-webui:8080`.

### "Abonnement" page in Moodle

The "Abonnement" page is a Moodle plugin (`moodle-abonnement/`, copied into the image by the Dockerfile). After the first image build, install it once:

```bash
docker compose exec -u www-data moodle php /var/www/html/admin/cli/upgrade.php --non-interactive
```

The page calls `stats-api` from the Moodle container. Since `stats-api` is a Swarm service, outside the Compose network, its address must be given to the `moodle` service in `docker-compose.yml`:

```yaml
      STATS_API_URL: http://host.docker.internal:8002
```

Then run `docker compose up -d moodle`. Without this variable, the page shows "Impossible de charger votre abonnement".

### Blocking the chat when the quota is reached

The filter `openwebui-filter/quota_educloud.py` blocks the chat of a user whose quota is reached. Open WebUI administrators are not limited: `quiz-api` and `stats-api` call the assistant with an administrator's key.

Installation, once, in Open WebUI (`http://localhost:3001`):

1. Admin Panel → Functions → "+" → New Function, paste the content of the file, save.
2. Enable the function, then "..." → Global (it then applies to every model).
3. Open the Valves (gear icon) and set `stats_api_url` to `http://host.docker.internal:8002`. On the server, also set `moodle_url`.

If the filter cannot reach `stats-api`, it lets the questions through: the chat is then no longer blocked.

## Deploying on the university server (optional)

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

The proxy variables apply to every outgoing request, including calls between containers, so `quiz-api` and `sync-moodle` already declare `NO_PROXY` for the internal service names.

## Deploying with Docker Swarm

`stats-api` is not in the Compose file: it is deployed with `docker-stack-stats.yml`, with 3 replicas, behind an **nginx** reverse proxy that is the single entry point on port 8002. The other services must be started first, with `docker compose up -d`.

| Service of the `swarmdemo` stack | Role | Published | Replicas |
| --- | --- | --- | --- |
| `nginx` | Entry point, spreads requests, retries on another replica on failure | Port 8002 in `host` mode | 1 |
| `stats-api` | API, dashboard, quotas and payments | Not published; `endpoint_mode: dnsrr` | 3 |

**Why nginx.** The university server is an LXC container: Docker cannot configure IPVS there, and Swarm's ingress routing depends on it (`Failed to create a new service for vip … operation not permitted`). In `dnsrr` mode, Swarm's DNS returns the address of each healthy replica; nginx queries them in turn (`nginx-stats.conf`) and sets aside for 15 s a replica that does not answer.

**One file for local and server.** The defaults in `docker-stack-stats.yml` are the server's (`10.3.16.187`, PostgreSQL on 5432, assistant on 3000, university proxy). Locally, the `SWARM_DB_HOST`, `SWARM_DB_PORT`, `SWARM_ASSISTANT_URL` and `SWARM_HTTPS_PROXY` variables of `.env` override them (see `.env.example`). Do not set them on the server.

### Enabling Swarm on the machine

Once per machine:

```bash
docker swarm init                                   # turns this machine into a Swarm node (manager)
docker info --format '{{.Swarm.LocalNodeState}}'    # checks the state: must print "active"
docker node ls                                      # lists the nodes of the cluster (a single one here)
```

### Building and pushing the image

Swarm pulls the image from Docker Hub, so it must be pushed after every change to `stats-api`.

```bash
docker login                                        # log in to the Docker Hub account
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ple002/educloud-stats-api:v3 \
  --push ./stats-api
```

- `--platform`: builds the image for two architectures, `amd64` for the server and `arm64` for an Apple Silicon Mac.
- `-t`: image name and version. For a new version, change the tag (`v4`, ...) here and in `docker-stack-stats.yml`.
- `--push`: sends the image to Docker Hub once it is built.
- `./stats-api`: folder that contains the Dockerfile.

### Deploying

Swarm does not read the `.env` file automatically. Load the variables before deploying, in the same terminal. Otherwise the assistant key is empty and the service restarts in a loop:

```bash
set -a && source .env && set +a                             # loads the .env variables into the terminal
echo "${#ASSISTANT_API_KEY} ${#LLM_API_KEY}"                # two non-zero numbers expected
```

`stats-api` replicas are only placed on nodes labelled `educloud=api` (placement rule). Once per node:

```bash
docker node update --label-add educloud=api $(docker info -f '{{.Swarm.NodeID}}')
```

```bash
docker stack deploy -c docker-stack-stats.yml swarmdemo     # creates or updates the "swarmdemo" stack
docker service ls --filter name=swarmdemo                   # nginx 1/1, stats-api 3/3 (max 3 per node)
docker service ps swarmdemo_stats-api                       # state of each replica
docker service logs swarmdemo_nginx --tail=20               # requests seen by nginx, with the chosen replica
curl --noproxy '*' http://localhost:8002/health             # checks that the API answers
```

If `swarmdemo_nginx` stays at `0/1` with `port is already allocated`, a `docker-proxy` process holds port 8002: `systemctl restart docker`, then redeploy.

A Swarm config is immutable: after changing `nginx-stats.conf`, rename the config (`nginx_conf_v2` → `nginx_conf_v3`) in both places of the stack file.

Updating to a new image, one replica after the other:

```bash
docker service update --image ple002/educloud-stats-api:v3 swarmdemo_stats-api
```

### Choosing the `stats-api` model

`stats-api` (dashboard report, tutor) does not use Gemini: it calls the Groq API directly. Its calls therefore do not use up the quota of the free Gemini tier, which is kept for the assistant and the quizzes.

Three variables in `docker-stack-stats.yml` configure it:

| Variable | Value | Role |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Groq API address |
| `LLM_API_KEY` | `${LLM_API_KEY}`, read from `.env` | Groq API key, created on `console.groq.com/keys` |
| `LLM_MODEL` | for example `qwen/qwen3.8-27b` | Exact name of a Groq model that works |

The key is loaded from `.env` by `set -a && source .env && set +a`: never write it in `docker-stack-stats.yml`, which is published on GitHub. If `LLM_MODEL` does not work, the report and the tutor return a 502 error. After a change, redeploy with `docker stack deploy`.

**Checking the Groq models.** This command lists every model of the account and tests each one:

```bash
KEY=$(grep '^LLM_API_KEY=' .env | cut -d= -f2)
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $KEY" \
  | python3 -c "import sys,json; print('\\n'.join(m['id'] for m in json.load(sys.stdin).get('data',[])))" \
  | while read -r m; do
      printf "%-45s " "$m"
      r=$(curl -s -m 15 -X POST https://api.groq.com/openai/v1/chat/completions \
        -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
        -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":5}")
      if echo "$r" | grep -q '"choices"'; then echo "OK"; else echo "$r" | head -c 80; echo; fi
    done
```

`OK`: the model answers and can be used in `LLM_MODEL`. An error message: the model does not do chat (for example `whisper`, which transcribes audio) or requires accepting terms on the Groq website. An empty line: no answer within 15 seconds, run the command again.

**Checking the assistant's Gemini models.** The assistant and `quiz-api` still use Gemini, through Open WebUI. List the model names:

```bash
KEY=$(grep ASSISTANT_API_KEY .env | cut -d= -f2)
curl -s -H "Authorization: Bearer $KEY" http://localhost:3001/api/models | grep -o '"id":"models/[^"]*"' | sort -u
```

A listed model does not always work (Gemini quota used up, high demand, model retired). To check, write the names to test after `for m in`:

```bash
for m in models/gemini-3.5-flash models/gemini-3.6-flash; do
  printf "%-45s " "$m"
  curl -s -m 30 -X POST http://localhost:3001/api/chat/completions \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":5}" | head -c 120
  echo
done
```

Reading the result: a line starting with `{"choices":` or `{"id":` means the model answers. `{"detail":"Model not found"}` or an error message (quota, 429, 503) means the model must not be used for now. An empty line: no answer within 30 seconds.

### Testing Swarm

Each availability measurement sends 120 `/health` requests every 0.5 s (about 60 s) to the entry point:

```bash
ok=0; ko=0; for i in $(seq 1 120); do
  c=$(curl -s --noproxy '*' -o /dev/null -m 2 -w '%{http_code}' http://localhost:8002/health)
  [ "$c" = "200" ] && ok=$((ok+1)) || ko=$((ko+1)); sleep 0.5; done
echo "OK=$ok KO=$ko dispo=$(( 100*ok/(ok+ko) ))%"
```

| Test | Command, run during the measurement in a second terminal | Expected result |
| --- | --- | --- |
| Load distribution | See below | About a third of the requests per replica |
| Rolling update | `docker service update --force swarmdemo_stats-api` | 100 % |
| Replica failure | `docker kill $(docker ps -q -f name=swarmdemo_stats-api \| head -1)` | Replica recreated; 99 to 100 % |
| Frozen replica (no longer answers) | `docker pause $(docker ps -q -f name=swarmdemo_stats-api \| head -1)`, then `docker unpause …` | 100 %; nginx retries on another replica, then sets it aside for 15 s |
| Automatic rollback | `docker service update --image ple002/educloud-stats-api:inexistant swarmdemo_stats-api` | Update cancelled, v3 image kept |

Load distribution, as seen by nginx (address of the replica chosen for each request):

```bash
for i in $(seq 1 30); do curl -s --noproxy '*' -o /dev/null http://localhost:8002/health; done
docker service logs swarmdemo_nginx --since 30s | grep -o 'upstream=[0-9.:]*' | sort | uniq -c
```

Requests retried on another replica show two addresses, for example `upstream=10.0.1.6:8000, 10.0.1.5:8000 ustatus=504, 200`.

Placement rules and resources. Each test leaves the existing replicas running:

| Test | Command | Expected result |
| --- | --- | --- |
| Limit of 3 replicas per node | `docker service scale swarmdemo_stats-api=4` | 4th replica `Pending`: `no suitable node (max replicas per node limit exceed)` |
| Impossible reservation | Change `memory: 128M` to `64G` under `reservations`, then `docker stack deploy` | New replica `Pending`, old replicas still running |

Then go back to `docker service scale swarmdemo_stats-api=3` or to `128M`.

Removing the `educloud=api` label from the node also shows the effect of the constraint, but Swarm then removes **all** replicas from the node: the service is down until the label is put back. Once it is back, `docker service update --force swarmdemo_stats-api` restarts the replicas left `Pending`.

Stopping the stack:

```bash
docker stack rm swarmdemo                       # removes nginx and stats-api (data stays in PostgreSQL)
```

## Operations

```bash
docker compose ps
docker compose logs -f sync-moodle
docker compose down                     # stop, keep the data
docker compose up -d --build            # rebuild and apply changes
```

**Never run `docker compose down -v`**: the `-v` option deletes the volumes, and with them the Moodle database, the assistant accounts and the knowledge bases.

Other useful commands:

```bash
docker compose logs -f moodle                   # logs of another service: moodle, open-webui, quiz-api, postgres
docker compose restart quiz-api                 # restart a single service
docker compose up -d moodle                     # apply a docker-compose.yml change to a single service

docker service ls                               # state of stats-api (Swarm service, not shown by "docker compose ps")
docker service logs -f swarmdemo_stats-api      # logs of stats-api
```

Checking that a payment was stored, after a try on the "Abonnement" page:

```bash
docker compose exec postgres psql -U moodle -d moodle -c "SELECT * FROM abonnement;"    # current tier of each user
docker compose exec postgres psql -U moodle -d moodle -c "SELECT * FROM paiement;"      # payment history
```

An accepted payment adds an `ACCEPTE` row to `paiement` and updates the tier in `abonnement`. A declined payment adds a `REFUSE` row to `paiement` and leaves `abonnement` unchanged. The user is identified by their email address.

## Known limitations

- **Moodle and the assistant have separate accounts. Single sign-on would let the assistant know which courses a user is enrolled in.**
- The free Gemini tier allows 20 requests per day per model. The quota is counted per model, so several models can be configured to spread the load.
- The assistant answers even when the information is not in the course materials. In that case it uses its general knowledge, so the cited source should always be checked.
- Retrieval only returns the closest passages, so an answer can miss information located in another part of a document.
- The services run without HTTPS.
- Questions asked from the Moodle iframe are not counted: the browser blocks the Open WebUI cookie inside an iframe.
- The questions table only lists users who have already asked a question.
- The quota only applies if the Moodle account and the assistant account have the same email address.
