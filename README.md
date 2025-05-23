# API d'Emploi du Temps EPSI/WIS

Une API REST pour accéder aux emplois du temps EPSI/WIS. Ceci est une version Python sous format d'api WEB du projet Rust original [irori-edt](https://gitlab.com/louisducruet/irori-edt).

Un serveur officiel de cet api est disponnible à : [https://epsi.enzomtp.party](https://epsi.enzomtp.party)

## Installation

1. Cloner le dépôt
2. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

## Lancement de l'API

Démarrer le serveur de développement Flask :
```bash
python app.py
```

L'API sera disponible à l'adresse `http://localhost:5000`

## Interface Web

L'API inclut une interface web utilisateur accessible à la racine du serveur (`/`). Cette interface permet de :

- Visualiser l'emploi du temps semaine par semaine
- Changer facilement entre les différentes semaines
- Enregistrer votre identifiant utilisateur localement dans le navigateur
- Basculer entre un thème clair et sombre

## Points d'Accès API

### Obtenir l'Emploi du Temps pour une Période

```
GET /
```

Paramètres de Requête :
- `user` (obligatoire) : Email de l'école sans le domaine
- `begin` (optionnel) : Date de début au format JJ-MM-AAAA (par défaut : aujourd'hui)
- `end` (optionnel) : Date de fin au format JJ-MM-AAAA (par défaut : date de début)

Exemple :
```
GET /?user=john.doe&begin=01-04-2024&end=07-04-2024
```

### Obtenir l'Emploi du Temps pour une Date Spécifique

```
GET /<date>
```

Paramètres de Chemin :
- `date` : La date au format JJ-MM-AAAA

Paramètres de Requête :
- `user` (obligatoire) : Email de l'école sans le domaine

Exemple :
```
GET /03-04-2024?user=john.doe
```

### Obtenir l'Emploi du Temps pour une Semaine Complète

```
GET /week/<date>
```

Paramètres de Chemin :
- `date` : N'importe quelle date de la semaine souhaitée au format JJ-MM-AAAA

Paramètres de Requête :
- `user` (obligatoire) : Email de l'école sans le domaine

Exemple :
```
GET /week/03-04-2024?user=john.doe
```

Cette requête retournera l'emploi du temps pour la semaine complète contenant le 3 avril 2024.

## Format de Réponse

L'API retourne des données JSON au format suivant :

Pour une période :
```json
[
  [
    {
      "name": "Nom du Cours",
      "room": "Numéro de Salle",
      "teacher": "Nom du Professeur",
      "date": "AAAA-MM-JJ",
      "start_time": "HH:MM",
      "end_time": "HH:MM"
    }
  ]
]
```

Pour une date spécifique :
```json
[
  {
    "name": "Nom du Cours",
    "room": "Numéro de Salle",
    "teacher": "Nom du Professeur",
    "date": "AAAA-MM-JJ",
    "start_time": "HH:MM",
    "end_time": "HH:MM"
  }
]
```

Pour une semaine complète :
```json
[
  [ // Lundi
    {
      "name": "Nom du Cours",
      "room": "Numéro de Salle",
      "teacher": "Nom du Professeur",
      "date": "AAAA-MM-JJ",
      "start_time": "HH:MM",
      "end_time": "HH:MM"
    }
  ],
  [ // Mardi
    // Cours du mardi
  ],
  // ... autres jours de la semaine jusqu'à vendredi
]
```

## Gestion des Erreurs

L'API retourne des codes de statut HTTP appropriés et des messages d'erreur :

- 400 : Requête Incorrecte (paramètres manquants, dates invalides, date de début postérieure à la date de fin)
- 500 : Erreur Serveur (problèmes côté serveur, erreurs lors de la récupération de l'emploi du temps)

Les réponses d'erreur incluent un message expliquant le problème :
```json
{
  "error": "Description du message d'erreur"
}
```

## Licence

Ce projet est sous la même licence que le projet Rust original.