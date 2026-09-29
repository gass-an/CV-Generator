# Exemples curl — CV Generator

## Développement

### Créer un CV

```bash
cat > /tmp/camille-document-request.json <<'JSON'
{
  "avp_number": "3134-26-1382/SR",
  "resume": {
    "basics": {
      "name": "Camille Exemple",
      "label": "Assistante qualité",
      "email": "camille@example.nc",
      "phone": "+687 75 00 00",
      "summary": "Professionnelle organisée et rigoureuse, avec une expérience en rédaction de procédures, analyse de processus et suivi d actions d amélioration.",
      "location": {
        "city": "Nouméa",
        "region": "Province Sud",
        "countryCode": "NC"
      }
    },
    "work": [
      {
        "name": "Entreprise Exemple",
        "position": "Assistante qualité",
        "startDate": "2023-01",
        "endDate": "2025-08",
        "summary": "Participation au suivi qualité et à l amélioration continue des processus internes.",
        "highlights": [
          "Rédaction et mise à jour de procédures internes",
          "Analyse de processus existants",
          "Participation à des réunions avec plusieurs services",
          "Suivi d actions d amélioration",
          "Préparation de documents de synthèse",
          "Mise à jour de tableaux de suivi"
        ]
      },
      {
        "name": "Organisation Exemple",
        "position": "Assistante administrative",
        "startDate": "2021-03",
        "endDate": "2022-12",
        "summary": "Support administratif et organisationnel.",
        "highlights": [
          "Gestion et classement de documents",
          "Préparation de comptes rendus",
          "Suivi de dossiers administratifs",
          "Accueil et échanges avec différents interlocuteurs"
        ]
      }
    ],
    "education": [
      {
        "institution": "Université Exemple",
        "area": "Gestion",
        "studyType": "Licence",
        "startDate": "2018",
        "endDate": "2021"
      }
    ],
    "skills": [
      {
        "name": "Rédaction de procédures",
        "keywords": ["Documentation", "Formalisation"]
      },
      {
        "name": "Analyse de processus",
        "keywords": ["Amélioration continue", "Organisation"]
      },
      {
        "name": "Outils bureautiques",
        "keywords": ["Word", "Excel", "PowerPoint"]
      }
    ],
    "languages": [
      {"language": "Français", "fluency": "Courant"},
      {"language": "Anglais", "fluency": "Intermédiaire"}
    ],
    "certificates": [
      {"name": "Formation qualité interne", "date": "2024"}
    ],
    "interests": [
      {"name": "Organisation et amélioration des méthodes de travail"}
    ]
  }
}
JSON

curl -s \
  -X POST \
  http://127.0.0.1:8000/api/v1/documents/cv \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/camille-document-request.json \
  | jq
```

### Vérifier le statut

```bash
curl -s \
  http://127.0.0.1:8000/api/v1/documents/<JOB_ID>/status \
  | jq
```

### Récupérer le CV généré en AsciiDoc

```bash
curl -s \
  http://127.0.0.1:8000/api/v1/documents/<JOB_ID> \
  | jq -r '.content'
```

### Télécharger le CV au format DOCX

```bash
curl -OJ \
  http://127.0.0.1:8000/api/v1/documents/<JOB_ID>/download
```

### Créer une lettre de motivation

Cette commande réutilise le même AVP et le même JSON Resume fictif créés plus haut.

```bash
curl -s \
  -X POST \
  http://127.0.0.1:8000/api/v1/documents/cover-letter \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/camille-document-request.json \
  | jq
```

### Vérifier le statut de la lettre

```bash
curl -s \
  http://127.0.0.1:8000/api/v1/documents/<JOB_ID>/status \
  | jq
```

### Récupérer la lettre générée en AsciiDoc

```bash
curl -s \
  http://127.0.0.1:8000/api/v1/documents/<JOB_ID> \
  | jq -r '.content'
```

### Télécharger la lettre au format DOCX

```bash
curl -OJ \
  http://127.0.0.1:8000/api/v1/documents/<JOB_ID>/download
```
