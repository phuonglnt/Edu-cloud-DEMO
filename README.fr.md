# Edu-cloud DEMO

*[English version](README.md)*

Edu-cloud ajoute à Moodle un assistant pédagogique basé sur un LLM, qui répond aux étudiants à partir des supports de leur cours.

- **L'enseignant dépose ses diapositives et ses documents, au format PDF, dans Moodle.** Ils servent à la fois de support de cours et de source pour l'assistant : ils lui sont envoyés automatiquement, sans autre manipulation.
- **L'étudiant pose ses questions à l'assistant** et reçoit une réponse construite à partir de ces supports, avec le document et la page cités.
- **L'enseignant génère des quiz** à partir des mêmes supports.
- **L'offre gratuite donne droit à 5 questions.** Au-delà, l'assistant bloque le chat et l'étudiant passe à un niveau supérieur (GOLD ou PLATINUM) depuis la page « Abonnement » de Moodle, par un paiement simulé.
- **Un tableau de bord** suit l'utilisation : nombre de questions, niveau et quota de chaque utilisateur.


## Services

| Service | Port | Rôle | Origine |
| --- | --- | --- | --- |
| `moodle` | 8080 | Plateforme de cours | Construit avec notre Dockerfile |
| `postgres` | interne | Base de données de Moodle | Image existante |
| `open-webui` | 3001 | Assistant IA, bases de connaissances | Image existante |
| `quiz-api` | 8001 | Génération de quiz | Construit avec notre Dockerfile |
| `sync-moodle` | aucun | Envoie les fichiers Moodle à l'assistant | Construit avec notre Dockerfile |
| `stats-api` | 8002 | Statistiques, quotas et abonnements | Image `ple002/educloud-stats-api:v3`, déployée comme service Swarm |

Dépendance externe : l'API Google Gemini fournit le modèle de langage.

L'API Groq fournit le modèle de `stats-api` (bilan du tableau de bord, tuteur), pour ne pas consommer le quota gratuit de Gemini.

## Fonctionnement

**Poser une question.** L'étudiant ouvre l'assistant depuis le menu de Moodle, tape `#` pour choisir le cours, puis pose sa question.
Open WebUI cherche les passages utiles dans les supports et les envoie à Gemini avec la question.
La réponse revient avec le nom du document et la page.

**Générer un quiz.** L'enseignant ouvre l'interface de quiz, choisit un cours, un thème et un nombre de questions.
L'API trouve la base de connaissances qui porte le nom du cours et demande le quiz à l'assistant.

**Déposer des supports.** Quand un enseignant ajoute un PDF dans un cours Moodle, `sync-moodle` le détecte,
crée la base de connaissances du cours si elle n'existe pas, puis y dépose le fichier. Il n'y a rien d'autre à faire.

**Suivre la consommation.** Le tableau de bord sur `http://localhost:8002` affiche
le nombre d'utilisateurs et de cours Moodle, ainsi que le nombre de questions
posées à l'assistant par utilisateur, avec son niveau et son quota. Il génère aussi
un court bilan écrit par l'IA.

**Changer de forfait.** Depuis le menu de Moodle, l'étudiant ouvre la page
« Abonnement ». Elle affiche son niveau, son quota, et un formulaire de paiement
simulé. Après un paiement accepté, `stats-api` enregistre le nouveau niveau dans
PostgreSQL. La carte `4242 4242 4242 4242` est acceptée, la carte
`4000 0000 0000 0002` est refusée.

**Bloquer le chat au quota.** Quand un utilisateur a atteint son quota, l'assistant
refuse sa question suivante et le renvoie vers la page « Abonnement ». Le chat
reprend dès que le paiement est accepté.

## Niveaux de service

| Niveau | Questions à l'assistant |
| --- | --- |
| FREE | 5 |
| GOLD | 50 |
| PLATINUM | illimité |

Le niveau est enregistré dans la table `abonnement` de PostgreSQL. Chaque
paiement, accepté ou refusé, est enregistré dans la table `paiement`. Les deux
tables sont créées au démarrage de `stats-api`.

Le compte Moodle et le compte de l'assistant sont rapprochés par leur **adresse
e-mail** : l'utilisateur paie avec son compte Moodle, et le quota s'applique au
compte Open WebUI qui a la même adresse.

## Prérequis

- Docker avec Docker Compose
- Une clé d'API Gemini, créée sur `aistudio.google.com/apikey`
- Une clé d'API Open WebUI, créée une fois les services démarrés
        + **Settings → Authentication → Create API key**
        + **Admin Panel → Account → API key**

## Démarrage

```bash
cp .env.example .env     
docker compose up -d --build
docker compose ps
```

## Remplir les clés
```bash
OPENAI_API_KEY=         # Clé API Gemini
ASSISTANT_API_KEY=      # Clé API Open WebUI
MOODLE_ADMIN_USER=admin
MOODLE_ADMIN_PASSWORD=
MOODLE_ADMIN_EMAIL=
LLM_API_KEY=            # Clé API Groq, utilisée par stats-api
```

Le premier démarrage prend quelques minutes : Moodle initialise sa base et Open WebUI se configure.

Ensuite :

1. Ouvrir `http://localhost:8080` et se connecter à Moodle avec le compte administrateur du fichier `.env`.
2. Ouvrir `http://localhost:3001` et créer le compte de l'assistant. Le premier compte créé est administrateur.

3. Relancer les services si besoin

```bash
docker compose up -d --force-recreate quiz-api sync-moodle
```

4. Dans Moodle, créer un cours et y déposer un PDF. Au bout de quelques minutes, il apparaît comme base de connaissances dans l'assistant.

**Port de l'assistant.** En local, l'assistant est publié sur le port 3001. Sur le serveur de l'université, il utilise le port 3000 : remplacer `3001` par `3000` dans les adresses de ce document. Les lignes correspondantes sont en commentaire dans `docker-compose.yml` et `docker-stack-stats.yml`.

**Aucun modèle visible avec un compte utilisateur.** Par défaut, seuls les administrateurs de l'assistant voient les modèles. Dans Admin Panel → Models, ouvrir chaque modèle à proposer et le rendre public.

**Synchroniser les supports pour une démonstration.** `sync-moodle` envoie les PDF à l'assistant au démarrage, puis toutes les `SYNC_INTERVAL` secondes (24 heures dans `docker-compose.yml`). Pour qu'un PDF déposé pendant une démonstration apparaisse tout de suite, relancer le service :

```bash
docker compose restart sync-moodle
```

Sur le serveur, depuis un autre dossier : `docker compose -f ~/educloud/docker-compose.yml restart sync-moodle`.

**Installer Moodle.** Au tout premier démarrage, une fois `.env` rempli, lancer une seule fois `./install-moodle.sh` : le script crée la base de Moodle et le compte administrateur.

**Démarrer `stats-api`.** `docker compose up -d` ne démarre pas `stats-api` : voir « Déploiement avec Docker Swarm ».

### Lien dans le menu de Moodle

Site administration → Appearance → Advanced theme settings → Custom menu items :

```
Accueil|/
Assistant IA|http://localhost:3001
Abonnement|/local/abonnement/index.php
```

Ce champ **remplace** le menu principal : il faut donc déclarer aussi l'entrée d'accueil. (Ce n'est pas une bonne conception)

Les services s'appellent par leur **nom de service**, et non par une adresse IP : `postgres:5432`, `open-webui:8080`.

### Page « Abonnement » dans Moodle

La page « Abonnement » est un plugin Moodle (`moodle-abonnement/`, copié dans l'image par le Dockerfile). Après la première construction de l'image, l'installer une fois :

```bash
docker compose exec -u www-data moodle php /var/www/html/admin/cli/upgrade.php --non-interactive
```

La page appelle `stats-api` depuis le conteneur Moodle. Comme `stats-api` est un service Swarm, en dehors du réseau Compose, son adresse doit être donnée au service `moodle` dans `docker-compose.yml` :

```yaml
      STATS_API_URL: http://host.docker.internal:8002
```

Puis `docker compose up -d moodle`. Sans cette variable, la page affiche « Impossible de charger votre abonnement ».

### Blocage du chat quand le quota est atteint

Le filtre `openwebui-filter/quota_educloud.py` bloque le chat d'un utilisateur dont le quota est atteint. Les administrateurs d'Open WebUI ne sont pas limités : `quiz-api` et `stats-api` appellent l'assistant avec la clé d'un administrateur.

Installation, une seule fois, dans Open WebUI (`http://localhost:3001`) :

1. Admin Panel → Functions → « + » → New Function, coller le contenu du fichier, enregistrer.
2. Activer la fonction, puis « ... » → Global (elle s'applique alors à tous les modèles).
3. Ouvrir les Valves (roue dentée) et renseigner `stats_api_url` : `http://host.docker.internal:8002`. Sur le serveur, renseigner aussi `moodle_url`.

Si le filtre ne peut pas joindre `stats-api`, il laisse passer les questions : le chat n'est alors plus bloqué.

## Déploiement sur le serveur de l'université (optionnel)

Deux ajouts sont nécessaires, car le serveur ne sort sur Internet qu'à travers un proxy.

**Le proxy pendant la construction des images.** Un conteneur n'hérite pas de la configuration de l'hôte, donc `apt-get` et `pip` échouent sans cela :

```yaml
    build:
      context: .
      args:
        http_proxy: http://cache.univ-pau.fr:3128
        https_proxy: http://cache.univ-pau.fr:3128
```

**L'indexation par l'API.** Open WebUI télécharge normalement un modèle d'indexation au premier démarrage, ce que le proxy bloque, et le conteneur reste bloqué. Ajouter dans `open-webui` :

```yaml
      - HTTPS_PROXY=http://cache.univ-pau.fr:3128
      - https_proxy=http://cache.univ-pau.fr:3128
      - RAG_EMBEDDING_ENGINE=openai
      - RAG_EMBEDDING_MODEL=models/gemini-embedding-001
```

Les variables de proxy s'appliquent à toutes les requêtes sortantes, y compris les appels entre conteneurs. C'est pourquoi `quiz-api` et `sync-moodle` déclarent déjà `NO_PROXY` pour les noms de services internes.

## Déploiement avec Docker Swarm

`stats-api` n'est pas dans le fichier Compose : il est déployé avec `docker-stack-stats.yml`, en 3 réplicas, derrière un reverse proxy **nginx** qui constitue l'unique point d'entrée sur le port 8002. Les autres services doivent être démarrés avant, avec `docker compose up -d`.

| Service de la pile `swarmdemo` | Rôle | Publication | Réplicas |
| --- | --- | --- | --- |
| `nginx` | Point d'entrée, répartition des requêtes, reprise sur un autre réplica en cas d'échec | Port 8002 en mode `host` | 1 |
| `stats-api` | API, tableau de bord, quotas et paiements | Non publié ; `endpoint_mode: dnsrr` | 3 |

**Pourquoi nginx.** Le serveur de l'université est un conteneur LXC : Docker ne peut pas y configurer IPVS, dont dépend le routage ingress de Swarm (`Failed to create a new service for vip … operation not permitted`). En mode `dnsrr`, le DNS de Swarm renvoie l'adresse de chaque réplica sain ; nginx les interroge à tour de rôle (`nginx-stats.conf`) et écarte pendant 15 s un réplica qui ne répond pas.

**Un seul fichier pour le local et le serveur.** Les valeurs par défaut de `docker-stack-stats.yml` sont celles du serveur (`10.3.16.187`, PostgreSQL sur 5432, assistant sur 3000, proxy de l'université). En local, les variables `SWARM_DB_HOST`, `SWARM_DB_PORT`, `SWARM_ASSISTANT_URL` et `SWARM_HTTPS_PROXY` du fichier `.env` les remplacent (voir `.env.example`). Sur le serveur, ne pas les définir.

### Activer Swarm sur la machine

À faire une seule fois par machine :

```bash
docker swarm init                                   # transforme cette machine en nœud Swarm (manager)
docker info --format '{{.Swarm.LocalNodeState}}'    # vérifie l'état : doit afficher « active »
docker node ls                                      # liste les nœuds du cluster (ici un seul)
```

### Construire et publier l'image

Swarm télécharge l'image depuis Docker Hub : il faut donc la publier après chaque modification de `stats-api`.

```bash
docker login                                        # connexion au compte Docker Hub
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ple002/educloud-stats-api:v3 \
  --push ./stats-api
```

- `--platform` : construit l'image pour deux architectures, `amd64` pour le serveur et `arm64` pour un Mac Apple Silicon.
- `-t` : nom et version de l'image. Pour une nouvelle version, changer le tag (`v4`, ...) ici et dans `docker-stack-stats.yml`.
- `--push` : envoie l'image sur Docker Hub à la fin de la construction.
- `./stats-api` : dossier qui contient le Dockerfile.

### Déployer

Les variables du fichier `.env` ne sont pas lues automatiquement par Swarm. Il
faut les charger avant le déploiement, dans le même terminal. Sinon la clé de l'assistant est vide et le service redémarre en boucle :

```bash
set -a && source .env && set +a                             # charge les variables de .env dans le terminal
echo "${#ASSISTANT_API_KEY} ${#LLM_API_KEY}"                # deux nombres non nuls attendus
```

Les réplicas de `stats-api` ne sont placés que sur les nœuds étiquetés `educloud=api` (règle de placement). À faire une fois par nœud :

```bash
docker node update --label-add educloud=api $(docker info -f '{{.Swarm.NodeID}}')
```

```bash
docker stack deploy -c docker-stack-stats.yml swarmdemo     # crée ou met à jour la pile « swarmdemo »
docker service ls --filter name=swarmdemo                   # nginx 1/1, stats-api 3/3 (max 3 per node)
docker service ps swarmdemo_stats-api                       # état de chaque réplica
docker service logs swarmdemo_nginx --tail=20               # requêtes vues par nginx, avec le réplica choisi
curl --noproxy '*' http://localhost:8002/health             # vérifie que l'API répond
```

Si `swarmdemo_nginx` reste à `0/1` avec `port is already allocated`, un processus `docker-proxy` garde le port 8002 : `systemctl restart docker`, puis redéployer.

Une configuration Swarm est immuable : après une modification de `nginx-stats.conf`, changer le nom de la config (`nginx_conf_v2` → `nginx_conf_v3`) aux deux endroits du fichier stack.

Mise à jour vers une nouvelle image, un réplica après l'autre :

```bash
docker service update --image ple002/educloud-stats-api:v3 swarmdemo_stats-api
```

### Choisir le modèle de `stats-api`

`stats-api` (bilan du tableau de bord, tuteur) n'utilise pas Gemini : il appelle directement l'API Groq. Ainsi, ses appels ne consomment pas le quota de l'offre gratuite de Gemini, réservé à l'assistant et aux quiz.

Trois variables de `docker-stack-stats.yml` le configurent :

| Variable | Valeur | Rôle |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Adresse de l'API Groq |
| `LLM_API_KEY` | `${LLM_API_KEY}`, lue dans `.env` | Clé API Groq, créée sur `console.groq.com/keys` |
| `LLM_MODEL` | par exemple `qwen/qwen3.8-27b` | Nom exact d'un modèle Groq qui fonctionne |

La clé est chargée depuis `.env` par `set -a && source .env && set +a` : ne jamais l'écrire dans `docker-stack-stats.yml`, qui est publié sur GitHub. Si `LLM_MODEL` ne fonctionne pas, le bilan et le tuteur renvoient une erreur 502. Après un changement, redéployer avec `docker stack deploy`.

**Vérifier les modèles Groq.** Cette commande liste tous les modèles du compte et en teste chacun :

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

`OK` : le modèle répond et peut être utilisé dans `LLM_MODEL`. Un message d'erreur : le modèle ne fait pas de chat (par exemple `whisper`, qui transcrit l'audio) ou demande d'accepter des conditions sur le site de Groq. Une ligne vide : pas de réponse dans le délai de 15 secondes, relancer la commande.

**Vérifier les modèles Gemini de l'assistant.** L'assistant et `quiz-api` utilisent toujours Gemini, par Open WebUI. Lister les noms des modèles :

```bash
KEY=$(grep ASSISTANT_API_KEY .env | cut -d= -f2)
curl -s -H "Authorization: Bearer $KEY" http://localhost:3001/api/models | grep -o '"id":"models/[^"]*"' | sort -u
```

Un modèle listé ne fonctionne pas toujours (quota Gemini épuisé, forte demande, modèle retiré). Pour le vérifier, écrire les noms à tester après `for m in` :

```bash
for m in models/gemini-3.5-flash models/gemini-3.6-flash; do
  printf "%-45s " "$m"
  curl -s -m 30 -X POST http://localhost:3001/api/chat/completions \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":5}" | head -c 120
  echo
done
```

Lecture du résultat : une ligne qui commence par `{"choices":` ou `{"id":` indique un modèle qui répond. `{"detail":"Model not found"}` ou un message d'erreur (quota, 429, 503) indique un modèle à ne pas utiliser pour le moment. Une ligne vide : pas de réponse dans le délai de 30 secondes.

### Tester Swarm

Chaque mesure de disponibilité envoie 120 requêtes `/health` toutes les 0,5 s (environ 60 s) au point d'entrée :

```bash
ok=0; ko=0; for i in $(seq 1 120); do
  c=$(curl -s --noproxy '*' -o /dev/null -m 2 -w '%{http_code}' http://localhost:8002/health)
  [ "$c" = "200" ] && ok=$((ok+1)) || ko=$((ko+1)); sleep 0.5; done
echo "OK=$ok KO=$ko dispo=$(( 100*ok/(ok+ko) ))%"
```

| Test | Commande, à lancer pendant la mesure dans un second terminal | Résultat attendu |
| --- | --- | --- |
| Répartition de charge | Voir ci-dessous | Environ un tiers des requêtes par réplica |
| Mise à jour progressive | `docker service update --force swarmdemo_stats-api` | 100 % |
| Panne d'un réplica | `docker kill $(docker ps -q -f name=swarmdemo_stats-api \| head -1)` | Réplica recréé ; 99 à 100 % |
| Réplica gelé (ne répond plus) | `docker pause $(docker ps -q -f name=swarmdemo_stats-api \| head -1)`, puis `docker unpause …` | 100 % ; nginx réessaie sur un autre réplica puis l'écarte 15 s |
| Rollback automatique | `docker service update --image ple002/educloud-stats-api:inexistant swarmdemo_stats-api` | Mise à jour annulée, image v3 conservée |

Répartition de charge, vue par nginx (adresse du réplica choisi pour chaque requête) :

```bash
for i in $(seq 1 30); do curl -s --noproxy '*' -o /dev/null http://localhost:8002/health; done
docker service logs swarmdemo_nginx --since 30s | grep -o 'upstream=[0-9.:]*' | sort | uniq -c
```

Les requêtes reprises sur un autre réplica apparaissent avec deux adresses, par exemple `upstream=10.0.1.6:8000, 10.0.1.5:8000 ustatus=504, 200`.

Règles de placement et ressources. Chaque test laisse les réplicas existants en marche :

| Test | Commande | Résultat attendu |
| --- | --- | --- |
| Limite de 3 réplicas par nœud | `docker service scale swarmdemo_stats-api=4` | 4ᵉ réplica `Pending` : `no suitable node (max replicas per node limit exceed)` |
| Réservation impossible | Passer `memory: 128M` à `64G` sous `reservations`, puis `docker stack deploy` | Nouveau réplica `Pending`, anciens réplicas toujours actifs |

Revenir ensuite à `docker service scale swarmdemo_stats-api=3` ou à `128M`.

Retirer l'étiquette `educloud=api` du nœud montre aussi l'effet de la contrainte, mais Swarm retire alors **tous** les réplicas du nœud : le service est interrompu jusqu'à la remise de l'étiquette. Après l'avoir remise, `docker service update --force swarmdemo_stats-api` relance les réplicas restés `Pending`.

Arrêter la pile :

```bash
docker stack rm swarmdemo                       # supprime nginx et stats-api (les données restent dans PostgreSQL)
```

## Exploitation

```bash
docker compose ps
docker compose logs -f sync-moodle
docker compose down                     # arrêter en conservant les données
docker compose up -d --build            # reconstruire et appliquer les changements
```

**Ne jamais utiliser `docker compose down -v`** : l'option `-v` supprime les volumes, donc la base de Moodle, les comptes de l'assistant et les bases de connaissances.

Autres commandes utiles :

```bash
docker compose logs -f moodle                   # journal d'un autre service : moodle, open-webui, quiz-api, postgres
docker compose restart quiz-api                 # redémarrer un seul service
docker compose up -d moodle                     # appliquer un changement de docker-compose.yml à un seul service

docker service ls                               # état de stats-api (service Swarm, absent de « docker compose ps »)
docker service logs -f swarmdemo_stats-api      # journal de stats-api
```

Vérifier qu'un paiement est bien enregistré, après un essai sur la page « Abonnement » :

```bash
docker compose exec postgres psql -U moodle -d moodle -c "SELECT * FROM abonnement;"    # niveau actuel de chaque utilisateur
docker compose exec postgres psql -U moodle -d moodle -c "SELECT * FROM paiement;"      # historique des paiements
```

Un paiement accepté ajoute une ligne `ACCEPTE` dans `paiement` et met à jour le niveau dans `abonnement`. Un paiement refusé ajoute une ligne `REFUSE` dans `paiement` et ne change pas `abonnement`. L'utilisateur est identifié par son adresse e-mail.

## Limites connues

- **Moodle et l'assistant ont des comptes séparés. Une authentification unique permettrait à l'assistant de savoir à quels cours un utilisateur est inscrit.**
- L'assistant répond même quand l'information n'est pas dans les supports de cours. Dans ce cas il utilise ses connaissances générales : il faut donc toujours vérifier la source citée.
- La recherche ne remonte que les passages les plus proches, donc une réponse peut passer à côté d'une information située dans une autre partie d'un document.
- Les services fonctionnent sans HTTPS.
- Les questions posées depuis l'iframe de Moodle ne sont pas comptées : le navigateur bloque le cookie d'Open WebUI dans un iframe.
- Le tableau des questions ne liste que les utilisateurs qui ont déjà posé une question.
- **Le quota ne s'applique que si le compte Moodle et le compte de l'assistant ont la même adresse e-mail.**
