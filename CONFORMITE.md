# Conformité aux cahiers des charges Racontelle Family

Références : *Cahier des charges bêta test Racontelle Family* et *MVP technique chiffrable Racontelle Family*
(10/09/2026), plus la charte graphique Racontelle. Vérification par relecture du code (24/09/2026), puis
exécution des tests (25/09/2026, voir « Résultats des tests » en fin de document).

Légende : ✅ conforme · 🔧 corrigé lors de cette vérification · ⚖️ écart assumé (choix produit) · 📱 à vérifier sur téléphone réel

## Écarts assumés (décision du 24/09/2026)

| Règle du cahier | Application | Raison |
|---|---|---|
| RG-01 / MVP-03 : 4 membres maximum, le 5e bloqué | 4 profils directs, puis invitations sans limite | Choix produit « pas de limite stricte de membres » |
| RG-08 / MVP-16 : 1 question du jour par cercle | Jusqu'à 3 questions du jour communes au cercle | Choix produit « jusqu'à 3 questions par jour » |
| Hors périmètre (§1, RG-15, RG-18) : IA, livre, transcription, texte, photo, avatar | Livre romancé IA + PDF, transcription, texte, photos, arbre qui grandit | Fonctions conservées visibles pendant la bêta |
| §3 : PWA, base relationnelle PostgreSQL « ou équivalent » | App Expo (iOS, Android **et** web) ; MongoDB | L'option OPT-01 (app native) est couverte ; MongoDB est l'« équivalent » retenu, isolation par cercle vérifiée |

Conséquence à garder en tête : le cahier conçoit la mesure de la bêta autour du seul rituel vocal. Les fonctions en plus
(livre, photos) enrichissent l'expérience mais peuvent brouiller la lecture des indicateurs.

## Critères de recette MVP-01 à MVP-25

| ID | Critère | État | Détail |
|---|---|---|---|
| MVP-01 | Inscription, connexion, réinitialisation | ✅ 🔧 | Case d'acceptation des conditions ajoutée (E2) ; codes de réinitialisation stockés hachés |
| MVP-02 | Créer un cercle, devenir membre 1 | ✅ | |
| MVP-03 | 4 profils maximum | ⚖️ | Voir écarts assumés |
| MVP-04 | Invitation limitée au cercle, expiration, révocation | ✅ 🔧 | Code haché (plus stocké en clair), 7 jours, usage unique ; un renvoi génère un nouveau code et invalide l'ancien |
| MVP-05 | Un compte = un cercle | ✅ | |
| MVP-06 | 400 questions, filtre par thème | ✅ 🔧 | Textes identiques à l'annexe A ; noms de thèmes corrigés (virgules manquantes) ; niveau, usage et tags importés de l'annexe |
| MVP-07 | Questions sensibles invisibles | ✅ | 2 thèmes sensibles inactifs et masqués |
| MVP-08 | « Une autre question » garde narrateur et thème | 🔧 | Bouton ajouté sur l'écran d'enregistrement |
| MVP-09 | Question surprise active et non sensible | ✅ | Erreur réseau désormais affichée |
| MVP-10 | Démarrer/arrêter/réécouter/recommencer/sauvegarder, pause | 🔧 📱 | Pause et reprise ajoutées |
| MVP-11 | Capsule rattachée au bon cercle et narrateur | ✅ | |
| MVP-12 | Date/heure et durée visibles | 🔧 | L'heure et le thème ajoutés dans l'album et la fiche |
| MVP-13 | Échec d'upload : audio conservé, réessai | 🔧 📱 | État « En attente d'envoi » + bouton « Réessayer l'envoi » ; alerte si on quitte sans sauvegarder. Limite : l'audio reste sur l'écran d'enregistrement, pas dans une file persistante après fermeture de l'app |
| MVP-14 | Album du cercle, filtres narrateur et thème | 🔧 | Filtre par thème ajouté |
| MVP-15 | Suppression immédiatement effective | ✅ 🔧 | Purge définitive documentée et outillée (`ADMINISTRATION.md`) |
| MVP-16 | Une question du jour par cercle | ⚖️ 🔧 | 3 par jour (écart assumé) ; doublons concurrents rendus impossibles par un index unique |
| MVP-17 | Pas de question sensible, pas de doublon | ✅ 🔧 | Même thème évité deux jours de suite (RG-10) |
| MVP-18 | Répondre à la question du jour | ✅ | |
| MVP-19 | Passer sans affecter les autres | ✅ 🔧 | La carte passée est maintenant masquée pour ce membre seulement |
| MVP-20 | Préférence e-mail quotidien respectée | 🔧 | **L'e-mail quotidien n'était jamais envoyé** : envoi automatique ajouté (9 h, une fois par jour, seulement si activé) |
| MVP-21 | E-mails envoyés, erreurs journalisées | 🔧 | Événements `invite_email_failed`, `daily_email_failed` |
| MVP-22 | Feedback avec contexte | 🔧 | Version de l'app et plateforme ajoutées ; commentaire facultatif si une note est donnée |
| MVP-23 | Export CSV des événements | 🔧 | `GET /api/admin/events/export` |
| MVP-24 | Aucune capsule sans authentification ni d'un autre cercle | ✅ | |
| MVP-25 | 0 bug bloquant | — | À établir par la recette |

## Règles de gestion RG-01 à RG-18

| ID | État | Détail |
|---|---|---|
| RG-01 | ⚖️ | 4 membres : écart assumé |
| RG-02 | ✅ | |
| RG-03 | ✅ 🔧 | Token haché, 7 jours, révocable, usage unique |
| RG-04 | ⚖️ | Les invités en attente ne sont pas comptés dans une limite, puisqu'il n'y en a pas |
| RG-05, RG-06, RG-07 | ✅ | |
| RG-08 | ⚖️ | 3 questions par jour, uniques par cercle, date et emplacement |
| RG-09 | ✅ | |
| RG-10 | 🔧 | Thèmes de la veille évités quand le stock le permet |
| RG-11 | ✅ | |
| RG-12 | ✅ | |
| RG-13 | 🔧 📱 | Réessai sans perte tant que l'écran est ouvert |
| RG-14 | ✅ 🔧 | Purge documentée |
| RG-15, RG-18 | ⚖️ | IA, texte et photo conservés |
| RG-16 | ✅ | Aucun paiement |
| RG-17 | 🔧 | E-mail uniquement, désactivable par membre, changement journalisé |

## Les 12 écrans

| Écran | État | Détail |
|---|---|---|
| E1 Accueil / onboarding | 🔧 | Accès « J'ai reçu un code d'invitation » ajouté ; accroche de la charte |
| E2 Connexion / inscription | 🔧 | Case d'acceptation obligatoire des conditions et du consentement |
| E3 Créer / rejoindre un cercle | ✅ | |
| E4 Accueil Family | ✅ | |
| E5 Membres / invitations | ✅ 🔧 | Nouveau code affiché lors d'un renvoi |
| E6 Thèmes / questions | ✅ 🔧 | |
| E7 Question du jour | 🔧 | Liens « Changer de thème » et « Mettre les rappels en pause » |
| E8 Enregistrer / réécouter | 🔧 | Pause, autre question, rappel du consentement, état d'envoi |
| E9 Album | 🔧 | Filtre thème, date et heure |
| E10 Fiche capsule | ✅ 🔧 | Heure et thème affichés |
| E11 Profil / paramètres | 🔧 | Section Confidentialité : consentement accepté (date, version) et demande de suppression |
| E12 Feedback | 🔧 | Contexte technique automatique |

## Sécurité, RGPD, mesure

- Journal d'usage : tous les événements du §12 sont désormais enregistrés (`question_viewed`, `theme_selected`, `recording_started`, `recording_failed`, `daily_email_sent` manquaient).
- Demande de suppression de compte depuis l'app, exécutée manuellement avec trace (§11).
- Hébergement UE, sauvegardes, environnements staging et bêta : voir `DEPLOIEMENT.md`.
- Procédure de fin de bêta : `ADMINISTRATION.md`.

## Charte graphique

Appliquée : palette (Blanc doux, Rose thé, Sauge douce, Brun mémoire, Bleu encre doux), polices Allura
(accroches), Cormorant Garamond (textes), Montserrat (boutons, menus, étiquettes), nouveau logo
(l'ancien est gardé sous `assets/images/racontelle-logo-ancien.png`). Le rose thé et la sauge sont trop
clairs pour porter du texte blanc ou fin : boutons et étiquettes utilisent une nuance plus foncée de la même
teinte (contraste 4,5:1). E-mails et livre PDF suivent la même palette.

## Résultats des tests (25/09/2026)

Environnement : API locale sur base MongoDB simulée en mémoire (`mongomock`), sans clé IA ni service e-mail.

| Contrôle | Résultat |
|---|---|
| Nouveaux tests de conformité (`test_conformite_family.py`) | ✅ 8/8 |
| Sécurité des médias (`test_iteration8_media_security.py`) | ✅ 20/20 |
| Suite backend complète | 78 réussis, 24 échecs, 11 erreurs (détail ci-dessous) |
| TypeScript (`tsc --noEmit`) | ✅ aucune erreur |
| Lint (ESLint) | ✅ aucune erreur |
| Construction de la version web (`expo export`) | ✅ réussie, 4 polices embarquées (Montserrat 400/500/600, Allura) |
| Parcours dans le navigateur (mobile 375 px) | ✅ accueil conforme à la charte, refus sans case cochée, inscription, création du cercle, 3 questions du jour aux noms de thèmes officiels, « Passer » masque la carte, section Confidentialité avec consentement daté |
| Export CSV des événements (admin) | ✅ 17 types d'événements journalisés |

Aucun des échecs restants ne vient des modifications de conformité :

| Tests | Cause |
|---|---|
| Livre romancé (7) | Pas de clé Anthropic en local : la génération répond 502, comme prévu |
| Transcription (3) | Pas de clé STT : statut `unavailable` au lieu de `pending`, comportement voulu depuis l'itération 19 |
| Photo unique `/capsules/{id}/photo` (7) | Ancienne API remplacée par les photos multiples à l'itération 8 : tests obsolètes |
| Invitation sans 4 profils (3 échecs + 3 erreurs de fixture) | Règle « 4 profils avant invitation » introduite à l'itération 6 : tests antérieurs |
| Itérations 7 et 17 (5 + 4) | Comptes qui n'existent que dans la base Emergent, chemin `/app/backend` |
| Itérations 18 et 19 (erreurs de collecte) | Ces tests ouvrent directement la base : impossible avec la base simulée |

Un test existant a été adapté : `test_daily_state_patch` supposait qu'une question déjà répondue pouvait
redevenir « vue ». L'app ne rétrograde plus un état répondu ou passé, ce qui corrige un vrai défaut.

## À faire avant la recette

1. ~~`yarn install` dans `frontend`~~ fait le 25/09/2026 (polices `@expo-google-fonts/montserrat` et `@expo-google-fonts/allura` 0.4.2).
2. Définir `ADMIN_TOKEN` dans l'environnement du backend de production (Render le génère via `render.yaml`).
3. Relancer les tests backend, dont le nouveau fichier `backend/tests/test_conformite_family.py` qui couvre les corrections ci-dessus. Le test d'invitation qui lisait le code en clair dans la liste a été adapté. À noter : la fixture `member_ctx` de `conftest.py` invite un membre avant que le cercle ait ses 4 profils, ce que l'API refuse depuis l'itération 6 ; les tests qui en dépendent risquent d'échouer indépendamment de cette vérification.
4. Recette sur un iPhone Safari et un Android Chrome réels (annexe C) : pause, réseau coupé pendant l'envoi, lecture audio.
