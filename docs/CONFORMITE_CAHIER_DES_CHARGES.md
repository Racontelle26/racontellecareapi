# Racontelle Care — Conformité au cahier des charges bêta (15/09/2026)

État au 25/09/2026, après la mise à niveau de l'application.
✅ conforme dans le code · ⚠️ partiel ou à vérifier · ❌ non couvert (hors code ou à faire)

> Vérifications faites le 25/09/2026 sur poste local :
> - serveur : 21 tests automatiques réussis (`backend/tests_local`, base MongoDB simulée) ;
> - application : TypeScript et ESLint sans erreur, version web construite ;
> - parcours testés dans un navigateur : inscription, profil, thèmes, « Une autre question »,
>   micro refusé, quiz, espace professionnel, retour testeur.
>
> Restent à confirmer sur un vrai téléphone ou une vraie tablette (le micro n'est pas accessible
> dans le navigateur de test) : l'enregistrement audio, l'envoi différé et le mode hors connexion.
> Les tests d'origine (`backend/tests`) visent l'environnement Emergent et n'ont pas été rejoués.

## 1. Critères de recette (§14)

| ID | Critère | État | Où / comment |
|----|---------|------|--------------|
| BT-01 | 5 profils maximum, limite infranchissable | ✅ | Serveur (`MAX_RESIDENTS = 5`) + application ; la réactivation par modification est bloquée |
| BT-02 | Statut de consentement visible | ✅ | Pastille sur l'accueil et la fiche ; 3 statuts (obtenu, en attente, retiré) ; historique daté (`consent_logs`) |
| BT-03 | Capsule guidée rattachée au résident | ✅ | Automatique ; le serveur refuse une capsule guidée sans résident |
| BT-04 | Date et heure visibles dans la bibliothèque | ✅ | Date + heure d'enregistrement d'origine ; le serveur horodate aussi la réception (`created_at`) |
| BT-05 | « Une autre question » garde résident et thème | ✅ | Bouton sur la carte question, même thème, même résident |
| BT-06 | 400 questions importées, activables/désactivables | ✅ | `backend/data/questions.json` (annexe A), écran « Banque de questions » |
| BT-07 | Thèmes sensibles inactifs par défaut | ✅ | Intimité/corps/sexualité et Deuils désactivés ; activation par l'administrateur |
| BT-08 | Pause, reprise, arrêt, réécoute, recommencer, sauvegarder | ✅ | Écran d'enregistrement |
| BT-09 | Pas d'arrêt automatique à 5 min | ✅ | Aucune limite de durée ; envoi jusqu'à ~2 h 30 (150 Mo) |
| BT-10 | Mode spontané sans résident | ✅ | Bouton « Mode spontané » de l'accueil |
| BT-11 | Capsule spontanée dans « À classer » avec date d'origine | ✅ | Rubrique « À classer » (accueil + bibliothèque) |
| BT-12 | Affectation ultérieure à un résident | ✅ | Bouton « Classer » ; la date d'origine est conservée |
| BT-13 | Réaffectation tracée | ✅ | Journal : `capsule.classify` / `capsule.reassign` |
| BT-14 | Réseau faible : rien n'est perdu, état d'envoi affiché | ✅ | Sauvegarde locale immédiate, file d'attente rejouée automatiquement, pastilles « En attente d'envoi » / « Sauvegardé » |
| BT-15 | Citation, choix, bonne réponse | ✅ | Quiz « Qui a dit ça ? » (18 citations du domaine public fournies) |
| BT-16 | Mode musical : extrait autorisé, choix, réponse | ⚠️ | Moteur prêt ; **aucun extrait fourni** : à importer avec leurs droits (procédure admin) |
| BT-17 | Pas de score cognitif individuel | ✅ | Score facultatif de session, jamais rattaché à un résident |
| BT-18 | Item désactivable sans suppression | ✅ | Écran « Contenus du quiz » |
| BT-19 | Contenu bloqué jamais actif | ✅ | Contrôlé au serveur (import, modification, lecture) |
| BT-20 | Suppression rend l'audio inaccessible, journalisée | ✅ | Suppression admin : audio effacé du stockage, liens révoqués, journal `capsule.delete` |
| BT-21 | Messages d'erreur compréhensibles | ⚠️ | Micro, réseau, sauvegarde : ✅ ; « niveau sonore insuffisant » : ❌ (pas de mesure du volume) |
| BT-22 | Bouton de retour avec version de l'application | ✅ | Bouton « Retour » de l'accueil et de l'espace pro ; version jointe automatiquement |

## 2. Périmètre fonctionnel (§2) et écrans (§9)

| Exigence | État |
|----------|------|
| Connexion simple, une session professionnelle | ✅ + « Mot de passe oublié » |
| Accueil : 5 cartes + Souvenir guidé, Mode spontané, Qui a dit ça ?, À classer | ✅ |
| Parcours guidé : résident → thème / Question surprise → question → enregistrer → réécouter → sauvegarder → « Capsule sauvegardée » | ✅ (3 à 4 actions après le résident) |
| Cartes des 20 thèmes avec indication des thèmes sensibles | ✅ |
| Titre automatique (question / « Souvenir spontané — date ») modifiable | ✅ |
| Tri chronologique inversable | ✅ |
| Une capsule « À classer » ne se partage pas et ne compte pas dans les statistiques d'un résident | ✅ |
| Champs résident : prénom, initiale/nom, unité, photo, consentement, date de création | ✅ |
| Administration : résidents, questions actives, contenus quiz, suppressions RGPD | ✅ (dans l'application, espace professionnel) |
| Interrupteurs de fonctions sans redéploiement | ✅ quiz, thèmes sensibles, lecture vocale, partage famille, transcription, carnet PDF |
| Journal des actions sensibles | ✅ suppression, réaffectation, consentement, accès administrateur, exports, réglages |
| Indicateurs §13 + export | ✅ écran + export CSV (`/api/indicators?format=csv`) |

## 3. Hors périmètre bêta (§16) présent dans l'application

Ces fonctions existaient déjà. Elles sont **désactivées par défaut** et activables par l'administrateur :
transcription automatique, partage famille, carnet PDF. La lecture vocale des questions (non prévue au cahier) reste active et peut être coupée.

## 4. Exigences techniques (§11–12) — hors code ou à décider

| Exigence | État | Commentaire |
|----------|------|-------------|
| Base PostgreSQL ou relationnelle | ❌ | L'application utilise MongoDB (héritage Emergent). Écart à arbitrer. |
| Hébergement UE de la base et des audios | ⚠️ | Dépend de l'hébergeur Emergent : à vérifier contractuellement |
| Sauvegardes automatiques base + audio | ❌ | À mettre en place chez l'hébergeur |
| Environnements dev / recette / bêta | ❌ | À créer |
| Journalisation des crashs | ⚠️ | Échecs d'envoi et d'enregistrement comptés ; pas d'outil de crash (ex. Sentry) |
| Durée de conservation des comptes et capsules | ❌ | À définir avant le pilote (voir procédure de fin de pilote) |
| Builds iOS/Android en distribution privée | ❌ | À produire (EAS / TestFlight / test interne Play Store) |
| Maquettes Figma | ❌ | Non livrées |
