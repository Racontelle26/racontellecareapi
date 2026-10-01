# Administration de la bêta Racontelle Family

Le MVP n'a pas de back-office graphique (cahier MVP, §4). Les opérations d'administration passent par
des routes protégées par le jeton `ADMIN_TOKEN`, envoyé dans l'en-tête `X-Admin-Token`.

Dans les exemples ci-dessous, remplacez `https://api.racontelle.fr` par l'adresse de votre API et
`VOTRE_JETON` par la valeur d'`ADMIN_TOKEN` (Render > racontelle-api > Environment).

## Exporter les événements de la bêta (MVP-23)

```powershell
curl.exe -H "X-Admin-Token: VOTRE_JETON" -o evenements.csv https://api.racontelle.fr/api/admin/events/export
```

Fichier CSV séparé par des `;`, lisible directement dans Excel. Filtrer à partir d'une date :
`.../api/admin/events/export?since=2026-10-01`.

Événements journalisés : `account_created`, `circle_created`, `invite_sent`, `invite_resent`,
`invite_accepted`, `invite_revoked`, `invite_email_failed`, `question_viewed`, `question_skipped`,
`theme_selected`, `recording_started`, `recording_saved` (durée, source daily/guided/spontaneous),
`recording_failed`, `capsule_played`, `capsule_deleted`, `capsule_purged`, `daily_email_sent`,
`daily_email_failed`, `feedback_submitted`, `deletion_requested`. Le contenu des voix n'est jamais exporté.

## Désactiver ou réactiver une question sans redéployer (§10.2)

```powershell
curl.exe -X PATCH -H "X-Admin-Token: VOTRE_JETON" -H "Content-Type: application/json" -d "{\"active\": false}" https://api.racontelle.fr/api/admin/questions/42
```

`42` est le numéro de la question dans la banque (1 à 400). Les questions sensibles ne peuvent pas être réactivées pendant la bêta.

## Importer ou corriger des questions (Annexe B)

Envoyer une liste JSON au format de l'annexe B. L'import est rejouable : une question existante (même
`source_number`) est mise à jour, jamais dupliquée.

```powershell
curl.exe -X POST -H "X-Admin-Token: VOTRE_JETON" -H "Content-Type: application/json" --data "@questions.json" https://api.racontelle.fr/api/admin/import/questions
```

```json
[{"source_number": 401, "theme": "Enfance & premiers souvenirs", "text": "Quel est votre premier souvenir ?",
  "level": "tout public", "usage": "Question de récit de vie", "tags": ["enfance", "mémoire"],
  "sensitive": false, "active": true}]
```

## E-mail « question du jour »

Envoyé automatiquement chaque jour à partir de `DAILY_EMAIL_HOUR` (9 h, heure de Paris), au plus une
fois par membre et par jour, uniquement aux membres qui ont laissé l'option active dans leur profil.
Envoi manuel (par exemple pour tester) :

```powershell
curl.exe -X POST -H "X-Admin-Token: VOTRE_JETON" https://api.racontelle.fr/api/admin/send-daily-emails
```

## Demandes de suppression (RGPD)

Les membres demandent la suppression depuis **Profil > Confidentialité**. Liste des demandes :

```powershell
curl.exe -H "X-Admin-Token: VOTRE_JETON" https://api.racontelle.fr/api/admin/deletion-requests
```

Procédure manuelle (le cahier autorise une exécution par Racontelle avec trace) :

1. Répondre à la personne par e-mail pour confirmer la demande.
2. Dans MongoDB Atlas (Browse Collections), passer ses souvenirs en `status: "deleted"` avec `deleted_at` (collection `capsules`, filtre `recorded_by_user_id`).
3. Passer le compte en `active: false` (collection `users`) et son profil en `status: "revoked"` (collection `members`).
4. Passer la demande en `status: "done"` avec la date (collection `deletion_requests`).
5. Lancer la purge ci-dessous avec `older_than_days=0`.

## Purge définitive des fichiers supprimés (RG-14)

Une suppression dans l'application rend le souvenir **immédiatement** inaccessible (liste, fiche, lien audio).
Les fichiers audio et photo restent 30 jours dans le stockage pour permettre une restauration en cas d'erreur,
puis sont effacés par la purge :

```powershell
curl.exe -X POST -H "X-Admin-Token: VOTRE_JETON" "https://api.racontelle.fr/api/admin/purge-deleted?older_than_days=30"
```

À lancer une fois par semaine pendant la bêta (ou via un cron gratuit comme cron-job.org).
La purge ne fonctionne qu'avec le stockage S3/R2 ou local, pas avec le stockage Emergent.

## Fin de bêta

1. Exporter les événements (CSV) et les retours (`feedback` dans Atlas > Export Collection).
2. Prévenir les familles et leur proposer d'exporter leurs souvenirs (sur demande, fichiers audio depuis R2).
3. À la date annoncée : passer tous les souvenirs en `deleted`, lancer la purge avec `older_than_days=0`,
   puis supprimer la base Atlas et le bucket R2 si la V1 ne reprend pas les données.
4. Conserver le journal des suppressions (collection `events`) le temps légal nécessaire.
