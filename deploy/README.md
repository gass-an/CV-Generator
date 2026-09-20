# CV-Generator — Commandes serveur Docker

Cette documentation concerne uniquement le PC fixe Windows utilisé comme serveur LLM.

## Emplacement

Le dossier contient :

```text
CV-Generator/
├── docker-compose.prod.yml
└── .env
```

## Démarrer le serveur

Ouvrir PowerShell puis :

```powershell
docker compose -f docker-compose.prod.yml up -d
```

## Voir les logs du LLM

```powershell
docker compose -f docker-compose.prod.yml logs -f llm
```

## Vérifier le serveur LLM

Depuis le PC fixe :

```powershell
curl.exe http://localhost:8080/health
```

Résultat attendu :

```json
{"status":"ok"}
```

## Arrêter le serveur

```powershell
docker compose -f docker-compose.prod.yml down
```

## Redémarrer le serveur

```powershell
docker compose -f docker-compose.prod.yml restart
```

Ou, pour recréer proprement les conteneurs :

```powershell
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

## Mettre à jour l'image Docker

```powershell
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## Arrêter complètement Docker / WSL

Quand le serveur n'est plus utilisé :

1. Quitter Docker Desktop.
2. Dans PowerShell :

```powershell
wsl --shutdown
```

Cela libère la RAM utilisée.


## Volume du modèle

Le modèle LLM est stocké dans le volume Docker :

```text
cv-generator-models
```

Lister les volumes :

```powershell
docker volume ls
```

Ne pas supprimer ce volume sauf si le modèle doit réellement être retéléchargé.
