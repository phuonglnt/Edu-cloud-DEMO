# Edu-cloud DEMO

Assistant pédagogique basé sur un LLM, intégré à Moodle.

- Les étudiants posent leurs questions et reçoivent une réponse construite à partir des supports de cours, avec la source citée.
- Les enseignants génèrent des quiz à partir des mêmes supports.
- Les fichiers déposés dans Moodle sont envoyés automatiquement à l'assistant IA.


## Services

| Service | Port | Rôle | Origine |
| --- | --- | --- | --- |
| `moodle` | 8080 | Plateforme de cours | Construit avec notre Dockerfile |
| `postgres` | interne | Base de données de Moodle | Image existante |
| `open-webui` | 3001 | Assistant IA, bases de connaissances | Image existante |
| `quiz-api` | 8001 | Génération de quiz | Construit avec notre Dockerfile |
| `sync-moodle` | aucun | Envoie les fichiers Moodle à l'assistant | Construit avec notre Dockerfile |

Dépendance externe : l'API Google Gemini fournit le modèle de langage.

PostgreSQL n'a pas de port publié : seuls les services de ce fichier Compose peuvent l'atteindre.

## Fonctionnement

**Poser une question.** L'étudiant ouvre l'assistant depuis le menu de Moodle, tape `#` pour choisir le cours, puis pose sa question.
Open WebUI cherche les passages utiles dans les supports et les envoie à Gemini avec la question.
La réponse revient avec le nom du document et la page.

**Générer un quiz.** L'enseignant ouvre l'interface de quiz, choisit un cours, un thème et un nombre de questions.
L'API trouve la base de connaissances qui porte le nom du cours et demande le quiz à l'assistant.

**Déposer des supports.** Quand un enseignant ajoute un PDF dans un cours Moodle, `sync-moodle` le détecte,
crée la base de connaissances du cours si elle n'existe pas, puis y dépose le fichier. Il n'y a rien d'autre à faire.

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

### Lien dans le menu de Moodle

Site administration → Appearance → Advanced theme settings → Custom menu items :

```
Accueil|/
Assistant IA|http://localhost:3001
```

Ce champ **remplace** le menu principal : il faut donc déclarer aussi l'entrée d'accueil. (Ce n'est pas une bonne conception)

Les services s'appellent par leur **nom de service**, et non par une adresse IP : `postgres:5432`, `open-webui:8080`.

~~## Déploiement sur le serveur de l'université (optionnel)

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

Les variables de proxy s'appliquent à toutes les requêtes sortantes, y compris les appels entre conteneurs. C'est pourquoi `quiz-api` et `sync-moodle` déclarent déjà `NO_PROXY` pour les noms de services internes.~~

## Exploitation

```bash
docker compose ps
docker compose logs -f sync-moodle
docker compose down                     # arrêter en conservant les données
docker compose up -d --build            # reconstruire et appliquer les changements
```

**Ne jamais utiliser `docker compose down -v`** : l'option `-v` supprime les volumes, donc la base de Moodle, les comptes de l'assistant et les bases de connaissances.

## Limites connues

- **Moodle et l'assistant ont des comptes séparés. Une authentification unique permettrait à l'assistant de savoir à quels cours un utilisateur est inscrit.**
- L'offre gratuite de Gemini permet 20 requêtes par jour et par modèle. Le quota étant calculé par modèle, plusieurs modèles peuvent être configurés pour répartir la charge.
- L'assistant répond même quand l'information n'est pas dans les supports de cours. Dans ce cas il utilise ses connaissances générales : il faut donc toujours vérifier la source citée.
- La recherche ne remonte que les passages les plus proches, donc une réponse peut passer à côté d'une information située dans une autre partie d'un document.
- Les services fonctionnent sans HTTPS.
