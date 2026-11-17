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

`stats-api` n'est pas dans le fichier Compose : il est déployé comme service Swarm avec `docker-stack-stats.yml`, en 3 réplicas. Les autres services doivent être démarrés avant, avec `docker compose up -d`.

Le service Swarm n'est pas sur le réseau Compose. Il atteint donc PostgreSQL et l'assistant par les ports publiés sur l'hôte : `host.docker.internal:5434` et `host.docker.internal:3001`. Sur un serveur Linux, remplacer `host.docker.internal` par l'adresse IP du serveur.

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
docker stack deploy -c docker-stack-stats.yml swarmdemo     # crée ou met à jour la pile « swarmdemo » à partir du fichier
docker service ls                                           # liste les services et leurs réplicas (3/3 attendu)
docker service ps swarmdemo_stats-api                       # état de chaque réplica du service
docker service logs swarmdemo_stats-api --tail=30           # 30 dernières lignes de journal du service
curl http://localhost:8002/health                           # vérifie que l'API répond
```

Le service s'appelle `swarmdemo_stats-api` : nom de la pile, puis nom du service dans le fichier.

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

Mise à l'échelle :

```bash
docker service scale swarmdemo_stats-api=3      # passe à 3 réplicas
docker service ps swarmdemo_stats-api           # les 3 réplicas doivent être « Running »
docker service scale swarmdemo_stats-api=1      # revient à 1 réplica
```

Tolérance aux pannes : arrêter un conteneur de force, Swarm en recrée un.

```bash
docker ps | grep stats-api                      # trouve l'identifiant d'un conteneur du service
docker kill <CONTAINER_ID>                      # arrête ce conteneur brutalement
docker service ps swarmdemo_stats-api           # l'ancien est « Failed », un nouveau est « Running »
```

État partagé : avec 3 réplicas, la même requête doit donner le même niveau, quel que soit le réplica qui répond.

```bash
for i in 1 2 3 4 5 6; do curl -s http://localhost:8002/api/subscription/<e-mail>; echo; done
```

Le port 8002 est publié par le routage de Swarm (`"8002:8000"`), qui répartit les requêtes entre les réplicas. Avec `mode: host`, chaque réplica réserverait le port 8002 de la machine : un seul réplica pourrait démarrer par nœud. Les réplicas partagent les niveaux et les paiements, car ils sont enregistrés dans PostgreSQL et non en mémoire.

Arrêter le service Swarm :

```bash
docker stack rm swarmdemo                       # supprime la pile et ses conteneurs (les données restent dans PostgreSQL)
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
