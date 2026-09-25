# Racontelle Care — Procédure administrateur (bêta)

## 1. Préparer l'espace pilote

1. Ouvrir l'application → **Pas encore de compte ? Créer l'espace de l'établissement**.
   Le premier compte créé est **Administrateur**.
2. Accueil → **Espace professionnel** → créer le **code professionnel** à 4 chiffres
   (il protège cet espace sur la tablette ; 5 erreurs = blocage 1 minute).
3. **Équipe** → *Ajouter un membre à l'équipe* pour chaque animateur
   (mot de passe temporaire de 12 caractères, transmis de vive voix).
4. Créer les **5 profils** (bouton *Ajouter* de l'accueil) et renseigner le
   **consentement** de chacun. Sans consentement « obtenu », aucun enregistrement n'est possible.

## 2. Rôles

| Action | Membre | Administrateur |
|--------|:------:|:--------------:|
| Créer un profil, enregistrer, classer, réaffecter | ✅ | ✅ |
| Modifier le consentement | ✅ (journalisé) | ✅ |
| Supprimer un souvenir, retirer ou supprimer un profil | — | ✅ |
| Fusionner des doublons, exporter | — | ✅ |
| Réglages, questions, quiz, indicateurs, journal | — | ✅ |

## 3. Fonctions de la bêta (interrupteurs)

*Espace professionnel → Fonctions de la bêta.* Effet immédiat, sans mise à jour de l'application.

| Fonction | Par défaut | Remarque |
|----------|:---------:|----------|
| Quiz « Qui a dit ça ? » | activé | |
| Thèmes sensibles | **désactivé** | À activer uniquement par un professionnel habilité |
| Lecture vocale des questions | activé | |
| Partage famille | désactivé | Hors bêta ; désactiver coupe aussi les liens existants |
| Transcription automatique | désactivé | Hors bêta ; nécessite l'accès Whisper sur la clé Emergent |
| Carnet PDF | désactivé | Hors bêta |

## 4. Banque de questions

*Espace professionnel → Banque de questions.* Les 400 questions (20 thèmes × 20) sont
chargées automatiquement au démarrage du serveur. Désactiver une question la retire
des propositions sans la supprimer.

## 5. Contenus du quiz

*Espace professionnel → Contenus du quiz.*

- 18 citations d'auteurs du **domaine public** sont fournies au départ.
- **Import** : coller un CSV (séparateur `;`) ou un JSON respectant le gabarit de l'annexe B :

```
id;type;prompt_text;audio_file;correct_answer;choice_a;choice_b;choice_c;choice_d;era;theme;difficulty;source_reference;rights_status;license_note;active
```

- `rights_status` : `public_domain`, `licensed`, `provided_by_client` ou `blocked`.
  Un contenu `blocked` n'est **jamais** actif.
- **Extraits musicaux** : un extrait n'est actif qu'avec son fichier audio et une autorisation d'usage.
  Deux possibilités :
  - mettre une **URL privée https** dans la colonne `audio_file` ;
  - ou déposer le fichier (15 Mo max) par l'API, avec un jeton administrateur :

```bash
curl -X POST "$API/api/quiz/items/M001/audio" -H "Authorization: Bearer $TOKEN" -F "file=@extrait.mp3;type=audio/mpeg"
```

## 6. Mot de passe oublié

- Chaque utilisateur peut cliquer sur **Mot de passe oublié ?** : un code à 8 caractères,
  valable 30 minutes, est envoyé par email.
- **Prérequis serveur** : renseigner `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
  `SMTP_FROM` dans `backend/.env` (voir `backend/.env.example`). Sans SMTP, aucun email ne part.
- Solution de secours : l'administrateur définit un mot de passe temporaire pour un membre :

```bash
curl -X POST "$API/api/auth/members/<id_membre>/password" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"new_password":"Nouveau-Mot-2026!"}'
```

## 7. Suivi pendant la bêta

- **Indicateurs** (espace professionnel) : sessions, capsules, durée moyenne, parcours guidé,
  mode spontané, incidents techniques, quiz. Bouton **Exporter (CSV)** pour les bilans.
- **Journal des actions sensibles** : 15 dernières actions visibles ; historique complet via `GET /api/audit?limit=500`.
- **Retours des testeurs** : `GET /api/feedback` (catégorie, commentaire, version, date).
