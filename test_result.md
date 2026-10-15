#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

## user_problem_statement: "Les réponses aux questions sont visibles sous le profil du répondant"
## frontend:
##   - task: "Afficher les réponses guidées dans la fiche du répondant"
##     implemented: true
##     working: true
##     file: "/app/frontend/app/index.tsx"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "La fiche distingue toutes les réponses aux questions des souvenirs libres. Le rendu vide a été vérifié sur mobile."
##       - working: true
##         agent: "testing"
##         comment: "Itération 10 : parcours complet validé, compteur passé de 0 à 1 et réponse guidée visible sous Claire avec question, audio et transcription en attente. Capsule de test supprimée ensuite."
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 10
##   run_ui: true
## test_plan:
##   current_focus:
##     - "Enregistrer une réponse guidée pour un profil puis vérifier sa présence dans la section Réponses aux questions de cette fiche"
##   stuck_tasks: []
##   test_all: false
##   test_priority: "high_first"

## known_external_integration_issue:
##   - flow: "Transcription automatique Whisper"
##     working: "not_tested_on_railway"
##     mocked: false
##     priority: "medium"
##     comment: "L'ancien backend local refusait whisper-1, mais le frontend actif pointe désormais Railway. STT/TTS Railway restent à vérifier après création du premier établissement; aucun fallback n'est simulé."

## user_problem_statement_railway: "Reconfigurer l'URL backend vers Railway : https://racontellecareapi-production.up.railway.app"
## railway_backend:
##   - task: "Basculer le frontend Expo vers le backend Railway"
##     implemented: true
##     working: true
##     files: "/app/frontend/.env, /app/memory/PRD.md, /app/memory/test_credentials.md"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: false
##         agent: "main"
##         comment: "URL Railway valide mais preflight web initialement refusé et comptes historiques absents."
##       - working: "NA"
##         agent: "main"
##         comment: "Variables CORS configurées par l'utilisateur sur Railway. GET /api=200, preflight=200 avec ACAO exact, accès navigateur=200 et login inexistant retourne proprement Identifiants incorrects."
##       - working: true
##         agent: "testing"
##         comment: "Itération 15 : URL, variables protégées, API Railway, 401, CORS, login web, inscription, mode local, lint et TypeScript validés à 100 %. Aucun mock."
##       - working: true
##         agent: "main"
##         comment: "Fixture auth rendu optionnel via RAILWAY_TEST_EMAIL/RAILWAY_TEST_PASSWORD et avertissement shadow web corrigé. Suite Railway 6/6, lints Python/JS et tsc verts."
## test_plan_railway:
##   current_focus:
##     - "EXPO_PUBLIC_BACKEND_URL pointe uniquement vers Railway sans /api final"
##     - "Les variables Expo protégées de preview sont inchangées"
##     - "CORS preview vers Railway autorise GET/POST avec credentials"
##     - "Le formulaire de connexion appelle bien /api/auth/login sur Railway"
##     - "Le flux d'inscription peut créer le premier établissement Railway"
##   test_all: false
##   test_priority: "high_first"

## user_problem_statement_azure_speech: "Remplacer OpenAI Whisper et OpenAI TTS par Azure AI Speech, région France Central, en conservant le cache tts_cache et les autres fonctionnalités."
## azure_speech:
##   - task: "Migration STT/TTS vers Azure AI Speech France Central"
##     implemented: true
##     working: true
##     files: "/app/backend/azure_speech.py, /app/backend/server.py, /app/nixpacks.toml, /app/railway.json, /app/backend/requirements.txt"
##     stuck_count: 0
##     priority: "critical"
##     needs_retesting: false
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "STT Azure REST + conversion WAV, TTS SSML AlainNeural -5 %, cache Mongo existant, quotas/consentements inchangés, erreurs 429/502/503 sûres. OpenAI/LiteLLM retirés. Tests : 26/26 API locale, 15/15 suite publique disponible, 9/9 contrats Azure. Appels Azure réels à valider après redéploiement Railway car la nouvelle clé n'est volontairement pas disponible localement."
##       - working: true
##         agent: "testing"
##         comment: "Itération 16 : contrats Azure, routes STT/TTS, cache, ffmpeg Railway et non-régression validés. 26/26 tests locaux et 15/15 tests publics disponibles. Production non mockée; fournisseurs doublés uniquement dans les tests."
##       - working: "verified_predeploy"
##         agent: "main"
##         comment: "Alertes finales corrigées : MongoDB fail-fast, import inutilisé retiré, Nixpacks préserve les paquets par défaut. Deux suites rejouées vertes. Contrôle réel Azure en attente du redéploiement Railway de ce code."
##       - working: true
##         agent: "user"
##         comment: "Le backend a été redéployé et l'utilisateur confirme que tout fonctionne. Il demande explicitement de ne plus tenter de connexion Railway."
## test_plan_azure_speech:
##   current_focus:
##     - "Aucune dépendance ni invocation OpenAI/Whisper/TTS-1 ne subsiste"
##     - "M4A/WebM/WAV sont normalisés en WAV PCM mono 16 kHz avant Azure STT"
##     - "Endpoint, headers et corps Azure STT respectent exactement le contrat France Central"
##     - "SSML Azure utilise AlainNeural, fr-FR, rate -5 % et échappe le texte"
##     - "Le second appel TTS identique réutilise tts_cache sans appeler Azure"
##     - "Consentement, auth tenant, quotas et routes frontend restent inchangés"
##     - "Railway installe ffmpeg et exige les variables Azure en production"
##   test_all: true
##   test_priority: "critical_first"

## user_problem_statement_resident_modal: "Corriger l'erreur Unexpected text node: A text node cannot be a child of a View dans ResidentFormSheet."
## resident_modal_runtime:
##   - task: "Supprimer le nœud texte parasite dans la modale Nouveau profil"
##     implemented: true
##     working: true
##     files: "/app/frontend/src/components/modals.tsx"
##     stuck_count: 0
##     priority: "critical"
##     needs_retesting: false
##     status_history:
##       - working: false
##         agent: "user"
##         comment: "Capture mobile : Unexpected text node dans ResidentFormSheet, ligne 90."
##       - working: "NA"
##         agent: "main"
##         comment: "Espaces JSX entre </Text> et </View> déplacés sur une nouvelle ligne. Recherche globale sans autre motif, ESLint/TypeScript verts, modale ouverte en 390x844 sans erreur console."
##       - working: true
##         agent: "testing"
##         comment: "Itération 17 : création et modification du profil validées en 390x844, tous les contrôles interactifs fonctionnent, aucune erreur Unexpected text node, lint et TypeScript verts."
## test_plan_resident_modal:
##   current_focus:
##     - "Ouvrir Nouveau profil sans écran d'erreur"
##     - "Vérifier photo, champs, consentement et bouton Créer le profil"
##     - "Créer un profil local puis rouvrir la modale de modification"
##     - "Aucune erreur Unexpected text node dans la console"
##   test_all: false
##   test_priority: "critical_first"

## user_problem_statement_logo: "Appliquer le logo fourni partout : icône Android, écran de démarrage, écran de connexion et accueil."
## application_logo:
##   - task: "Nouvelle identité visuelle Racontelle Care"
##     implemented: true
##     working: "NA"
##     files: "/app/frontend/assets/images/icon.png, /app/frontend/assets/images/adaptive-icon.png, /app/frontend/assets/images/splash-image.png, /app/frontend/assets/images/favicon.png, /app/frontend/assets/images/racontelle-logo.webp, /app/frontend/app.json"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: true
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Logo utilisateur détouré et décliné sans altération en variantes interface, icône opaque, adaptive foreground transparent, splash et favicon. Login 152x152 et accueil 92x92 vérifiés. Version 1.0.2 / Android versionCode 3. Expo Doctor 20/20, export web, lint et TypeScript verts."
## test_plan_logo:
##   current_focus:
##     - "Logo visible et non déformé sur connexion et accueil"
##     - "Icône classique 1024 opaque et adaptive foreground 1024 transparent dans la zone sûre"
##     - "Splash et favicon utilisent le nouveau monogramme"
##     - "Expo config expose version 1.0.2 et Android versionCode 3"
##     - "Export web et compatibilité SDK Expo passent"
##   test_all: false
##   test_priority: "high_first"

## user_problem_statement_launcher_icon: "Le logo Emergent apparaît encore comme icône pour ouvrir l'application ; utiliser le logo Racontelle Care à la place."
## native_launcher_icon:
##   - task: "Forcer le nouveau logo dans le prochain APK Android"
##     implemented: true
##     working: "source_verified_pending_apk"
##     files: "/app/frontend/app.json, /app/frontend/assets/images/racontelle-care-icon-v4.png, /app/frontend/assets/images/racontelle-care-adaptive-v4.png, /app/frontend/assets/images/racontelle-care-splash-v4.png, /app/frontend/assets/images/racontelle-care-favicon-v4.png"
##     stuck_count: 0
##     priority: "critical"
##     needs_retesting: true
##     status_history:
##       - working: false
##         agent: "user"
##         comment: "Capture Android : l'application Racontelle Care installée affiche encore l'icône Emergent."
##       - working: "NA"
##         agent: "main"
##         comment: "Icône forcée explicitement dans expo.icon, ios.icon, android.icon et android.adaptiveIcon avec noms versionnés uniques v4. Version 1.0.3 / Android versionCode 4 pour invalider ancien APK et cache build. Expo config confirme tous les chemins; Doctor 20/20, lint et TypeScript verts. Un nouvel APK natif reste nécessaire."
##       - working: "source_verified_pending_apk"
##         agent: "testing"
##         comment: "Itération 19 : configuration Expo, assets natifs, absence de logo Emergent actif, Doctor 20/20, lint, TypeScript, export web et logos UI validés. L'icône launcher finale doit être confirmée après génération et installation d'un nouvel APK versionCode 4."
## test_plan_native_launcher_icon:
##   current_focus:
##     - "Tous les champs Expo natifs pointent vers des fichiers Racontelle Care v4"
##     - "Icône 1024 opaque et adaptive foreground transparent respectent Android"
##     - "VersionCode 4 force une mise à jour distincte de l'ancien APK"
##     - "Aucune référence icon/splash active ne pointe vers les anciens fichiers"
##     - "Le prochain APK doit être généré puis installé; Expo Go conserve toujours sa propre icône hôte"
##   test_all: false
##   test_priority: "critical_first"

## user_problem_statement_brand: "Remplace le nom de Ehpad recall par Racontelle Care partout."
## branding:
##   - task: "Renommage complet visible en Racontelle Care"
##     implemented: true
##     working: true
##     files: "/app/frontend/app.json, /app/backend/server.py, /app/frontend/app/_layout.tsx, /app/frontend/app/index.tsx, /app/frontend/src/theme.ts, /app/memory/PRD.md"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Nom, slug, scheme, titre web, partage familial, carnets PDF et documentation renommés Racontelle Care. Les URL de preview et bundle IDs historiques sont conservés pour ne pas casser l'environnement ni l'identité des builds. Titre public vérifié et 13 tests carnets/partages réussis."
##       - working: false
##         agent: "testing"
##         comment: "Itération 14 : marque entièrement validée, mais yarn lint signalait 11 règles React dans le chronomètre existant."
##       - working: true
##         agent: "main"
##         comment: "Les 11 règles React ont été corrigées sans désactiver ESLint. yarn lint et tsc passent; titre Racontelle Care et chronomètre résident 2 s revérifiés sur mobile. Profil TEST supprimé."
## test_plan_brand:
##   current_focus:
##     - "Le titre web et la configuration Expo affichent Racontelle Care"
##     - "Le partage familial affiche Racontelle Care"
##     - "Le carnet PDF affiche Racontelle Care"
##     - "Aucun ancien nom visible ne subsiste dans le frontend ou les documents générés"
##   test_all: false
##   test_priority: "high_first"

## user_problem_statement_session: "Ouverture automatique : la session reste mémorisée et l’application s’ouvre directement, sans aucune vérification. Permettre d'afficher le mot de passe lorsqu'il doit être utilisé lorsque la session expire."
## frontend_session:
##   - task: "Ouverture locale immédiate et mot de passe affichable"
##     implemented: true
##     working: true
##     files: "/app/frontend/src/api.ts, /app/frontend/src/components/auth-screen.tsx, /app/frontend/app/index.tsx"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Le lancement lit uniquement l'identité et les données locales; aucun refresh ou appel API automatique. La première action serveur valide ensuite la session. L'œil du mot de passe fonctionne et une reconnexion admin complète a été validée."
##       - working: true
##         agent: "testing"
##         comment: "Itération 13 : reload directement sur l'accueil du bon établissement sans aucun appel /api au lancement; œil validé en connexion et inscription; logout efface bien l'identité."
##       - working: true
##         agent: "main"
##         comment: "Expiration reproduite par 401 contrôlés sur action serveur + refresh : message explicite, email prérempli, mot de passe vide, œil fonctionnel et reconnexion réussie."
## test_plan_session:
##   current_focus:
##     - "Après connexion puis relance, l'accueil s'ouvre directement sans écran de connexion"
##     - "Aucune requête /api n'est émise automatiquement lors de cette relance"
##     - "Après expiration, l'écran de reconnexion préremplit l'email mais jamais le mot de passe"
##     - "Le bouton œil affiche et masque réellement le mot de passe"
##     - "Une action serveur ultérieure déclenche alors seulement la validation/rotation"
##   test_all: false
##   test_priority: "high_first"
## agent_communication:
##   - agent: "main"
##     message: "Tester le parcours profil → atelier → question guidée → enregistrement → sauvegarde → retour fiche, puis vérifier question, audio et transcription dans la section dédiée."
##   - agent: "testing"
##     message: "Validation frontend réussie à 100 %, aucun problème bloquant. Rapport : /app/test_reports/iteration_10.json."

## user_problem_statement_deployment_outage: "Après un force push sur main, Railway boucle sur uvicorn: command not found et le backend est hors service."
## railway_startup_recovery:
##   - task: "Rendre le build et le démarrage Railway déterministes"
##     implemented: true
##     working: "pending_deployment"
##     files: "/app/Dockerfile, /app/.dockerignore, /app/railway.json"
##     stuck_count: 1
##     priority: "critical"
##     needs_retesting: true
##     status_history:
##       - working: false
##         agent: "user"
##         comment: "Production indisponible après force push; logs Railway: /bin/bash: line 1: uvicorn: command not found."
##       - working: "NA"
##         agent: "main"
##         comment: "Cause racine: Nixpacks lancé à la racine du monorepo ne détecte pas backend/requirements.txt. Dockerfile racine ajouté avec installation explicite des dépendances et ffmpeg; startCommand Nixpacks supprimée au profit du CMD Docker sur PORT."
##       - working: "source_verified_pending_deployment"
##         agent: "testing"
##         comment: "Itération 21 : 9/9 contrats déploiement/Azure/auth passent, pip check et ffmpeg passent, uvicorn démarre réellement et GET /api/ répond 200. Docker CLI indisponible localement; validation Railway finale requise après Save to GitHub."
##       - working: false
##         agent: "user"
##         comment: "Après redéploiement, Railway renvoie encore 502; demande explicite de supprimer tout port hardcodé/repli et d'utiliser strictement la variable PORT."
##       - working: "NA"
##         agent: "main"
##         comment: "EXPOSE et le repli 8000 supprimés. Le CMD Docker exige PORT, échoue explicitement si absent et transmet exactement la valeur Railway à uvicorn."
##       - working: "source_verified_pending_deployment"
##         agent: "testing"
##         comment: "Itération 22 : aucun EXPOSE/fallback/port hardcodé; PORT=8765 donne GET /api/ 200, PORT absent échoue explicitement, 9/9 tests passent. Validation Railway live requise après Save to GitHub."
##       - working: true
##         agent: "main"
##         comment: "Vérification totale : Railway répond 200 cinq fois, OpenAPI publie forgot/reset, accès anonyme refusé, CORS autorisé/inconnu conforme et en-têtes sécurité présents. Frontend réaligné sur l'URL Railway après détection d'une régression vers l'URL de preview."
##       - working: true
##         agent: "main"
##         comment: "Nouvelle régression de fusion détectée : frontend/.env avait rebasculé vers l'URL de preview. EXPO_PUBLIC_BACKEND_URL restaurée exactement vers https://racontellecareapi-production.up.railway.app, sans toucher aux variables packager protégées."
## test_plan_railway_startup_recovery:
##   current_focus:
##     - "Le Dockerfile installe backend/requirements.txt et vérifie l'import uvicorn pendant le build"
##     - "ffmpeg et les certificats HTTPS sont présents pour Azure Speech"
##     - "Railway utilise le builder DOCKERFILE et le CMD écoute 0.0.0.0:$PORT"
##     - "Les fichiers .env et secrets locaux ne sont jamais copiés dans l'image"
##     - "GET /api/ répond 200 après redéploiement"
##   test_all: false
##   test_priority: "critical_first"

## user_problem_statement_total_verification: "Est-ce que l'appli est fonctionnelle maintenant ? Lance une vérification totale."
## total_verification:
##   - task: "Recette complète frontend, backend local et production publique Railway"
##     implemented: true
##     working: "public_and_local_verified"
##     files: "/app/frontend, /app/backend, /app/Dockerfile, /app/railway.json"
##     stuck_count: 0
##     priority: "critical"
##     needs_retesting: false
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Railway /api/ 200 cinq fois, OpenAPI forgot/reset présent, accès anonyme 401, CORS autorisé/inconnu conforme, partage invalide 404, en-têtes sécurité présents. Backend local 26/26 + unités 12/12; frontend lint, TypeScript, Doctor 20/20 et export web passent. UI mobile et appel forgot réel vers Railway 200 validés. Expo/router alignés sur les patchs SDK 57 et EXPO_PUBLIC_BACKEND_URL restauré vers Railway."
##       - working: "limited"
##         agent: "main"
##         comment: "Aucun compte de test Railway valide n'est documenté : aucun login distant ni appel Azure authentifié ne peut être exécuté. Resend/SMTP n'est pas configuré; la route forgot répond mais la livraison réelle d'email reste non fonctionnelle/différée."
##       - working: "NA"
##         agent: "main"
##         comment: "Correctif post-recette : le mode local est désormais considéré gestionnaire sur la fiche, afin d'afficher profile-remove et permettre la suppression locale protégée par PIN. Le lancement direct server.py exige aussi PORT sans fallback."
##       - working: "limited"
##         agent: "testing"
##         comment: "Itération 23 : backend public Railway 8/8, backend local 26/26, opérateur/déploiement 12/12, frontend auth/local et appel forgot Railway validés. profile-remove était instable/absent en local avant correctif."
##       - working: true
##         agent: "main"
##         comment: "Après correctif, parcours réel 390x844 validé : mode local, création profil, profile-remove visible, création PIN, suppression définitive et nettoyage du profil. Lint, TypeScript et test déploiement 10/10 verts."
## test_plan_total_verification:
##   current_focus:
##     - "Production Railway publique sans 502, cinq réponses /api/ 200"
##     - "Frontend mobile charge, navigation auth/forgot et appel CORS Railway fonctionnent"
##     - "Backend local auth, isolation, profils, capsules, audio, hors-ligne, mot de passe et sécurité"
##     - "Azure France Central et tts_cache préservés par contrats; pas d'appel réel sans compte de test"
##     - "Lint, TypeScript, Expo Doctor, bundle web et dépendances"
##   test_all: true
##   test_priority: "critical_first"

## user_problem_statement_resend: "Configurer Resend officiel avec lien web + code vers l'écran Nouveau mot de passe."
## resend_password_recovery:
##   - task: "Envoyer les récupérations de mot de passe via l'API officielle Resend"
##     implemented: true
##     working: "source_verified_pending_railway_env"
##     files: "/app/backend/email_service.py, /app/backend/security.py, /app/frontend/app/index.tsx, /app/frontend/src/components/auth-screen.tsx"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: true
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Email transactionnel fixe Racontelle Care, destinataire lu uniquement en base, lien HTTPS + code one-shot, clé backend seulement, garde anti-phishing et réponse anti-énumération. Lien profond 390x844 validé : écran reset ouvert, email et code préremplis."
##       - working: "MOCKED"
##         agent: "main"
##         comment: "42 tests backend passent; le client HTTP email est simulé et aucune livraison réelle n'a été demandée. RESEND_API_KEY doit être configuré dans Railway avant activation réelle."
##       - working: "NA"
##         agent: "main"
##         comment: "Le proxy Emergent non documenté a été entièrement retiré. Implémentation basculée vers POST https://api.resend.com/emails avec Authorization Bearer, expéditeur strict no-reply@racontellecare.com, URL de reset first-party et tâche FastAPI en arrière-plan pour préserver l'anti-énumération."
##       - working: "source_verified_pending_deployment"
##         agent: "testing"
##         comment: "Itération 25 : Resend officiel uniquement, backend 42/42, frontend deep-link validé. Production sert encore l'ancien message forgot : redéploiement requis. API Resend et Mongo restent MOCKED; aucun email réel envoyé."
##       - working: false
##         agent: "main"
##         comment: "Après annonce d'un déploiement actif, l'API publique sert toujours l'ancien message. RCA : les changements Resend ne figurent pas dans le HEAD déployé et email_service.py n'est pas suivi; un nouveau Save to GitHub est requis. Validation PASSWORD_RESET_URL rendue dynamique et sûre (HTTPS, hôte non-IP/non-raccourci), sans domaine hardcodé."
##       - working: "deployed_source_verified"
##         agent: "main"
##         comment: "Après push de conflict_151026_1601, Railway /api/ répond 200 et forgot renvoie le nouveau contrat « un lien et un code ». Playwright sur l'URL publique réelle confirme POST vers Railway HTTP 200. Aucun compte personnel ni email réel testé."
## test_plan_resend:
##   current_focus:
##     - "Template fixe, marque Racontelle Care, aucun formulaire ni demande de secret"
##     - "Lien HTTPS first-party, code court one-shot, expiration et cinq essais conservés"
##     - "Recipient issu de users.email_lower, jamais du corps libre d'une route d'envoi"
##     - "Clé uniquement en Authorization Bearer vers api.resend.com et absente du payload/logs/frontend"
##     - "Deep link ouvre l'écran reset et préremplit email/code"
##     - "Livraison réelle différée jusqu'aux variables Railway"
##   test_all: true
##   test_priority: "high_first"

## user_problem_statement_security: "Ajouter authentification serveur, isolation par établissement, autorisations, quotas, liens expirables/révocables, PIN sécurisé et CORS strict."
## security:
##   - task: "Sécurisation complète multi-établissements"
##     implemented: true
##     working: true
##     files: "/app/backend/security.py, /app/backend/server.py, /app/frontend/src/api.ts, /app/frontend/app/index.tsx"
##     stuck_count: 0
##     priority: "critical"
##     needs_retesting: false
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "JWT/refresh rotation, Argon2id, tenant_id systématique, rôles admin/member, quotas 30/100/100, partages 30 jours révocables, SecureStore PIN/tokens et CORS strict implémentés. 45 tests backend passent et l'UI login a été vérifiée."
##       - working: false
##         agent: "testing"
##         comment: "Itération 11 : origine CORS publique rejetée car le proxy la réécrivait vers ehpad-recall.cluster-2.preview.emergentcf.cloud."
##       - working: true
##         agent: "main"
##         comment: "Allowlist exacte complétée avec l'origine proxy et réécriture ACAO vers l'origine navigateur. Origine autorisée=200 avec ACAO public, origine inconnue=400 sans ACAO. Les connexions réussies ne consomment plus la limite anti-bruteforce. Matrice 7/7 et suite complète 52/52." 
## test_plan_security:
##   current_focus:
##     - "Inscription créant un établissement et un administrateur"
##     - "Connexion, restauration et déconnexion"
##     - "Isolation stricte entre deux établissements"
##     - "Membre bloqué sur suppressions, fusion, exports et carnets"
##     - "Partage familial expirant et révocable"
##     - "Quotas 30 STT, 100 TTS, 100 uploads et CORS strict"
##   test_all: true
##   test_priority: "critical_first"
## agent_communication_security:
##   - agent: "main"
##     message: "Utiliser les comptes documentés dans /app/memory/test_credentials.md. Vérifier backend et frontend mobile, puis signaler toute fuite inter-tenant ou action admin accessible à un membre."
##   - agent: "main"
##     message: "Correctif CORS appliqué après itération 11. Contre-vérifier OPTIONS autorisé/inconnu, puis accès mobile et stabilité publique."
##   - agent: "testing"
##     message: "Itération 12 validée : sécurité 100 %, matrice 7/7, suite complète 52/52, CORS et stabilité publics conformes."

## user_problem_statement_timing: "Le temps d'utilisation par résidents et globale est toujours erroné. Mettre un vrai chronométrage du temps d'utilisation par résident et temps total d'utilisation sous le profil espace professionnel."
## frontend_timing:
##   - task: "Chronométrage réel global et par résident"
##     implemented: true
##     working: "NA"
##     files: "/app/frontend/app/index.tsx, /app/frontend/src/local.ts, /app/frontend/src/types.ts"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: true
##     status_history:
##       - working: false
##         agent: "main"
##         comment: "Cause confirmée : les segments inférieurs à 3 secondes étaient supprimés, les secondes arrondies et l'écran professionnel n'était pas actualisé en direct."
##       - working: "NA"
##         agent: "main"
##         comment: "Comptage en millisecondes avec horloge monotone, premier plan uniquement, attribution fiche+atelier, rafraîchissement 1 s, persistance 10 s et migration des anciens compteurs. Test manuel : profil 5 s, total 6→7 s en direct, résident stable hors fiche, second passage 5→7 s."
## test_plan_timing:
##   current_focus:
##     - "Le total avance chaque seconde dans Espace professionnel"
##     - "Le compteur résident avance uniquement sur sa fiche ou son atelier"
##     - "Aucune période courte n'est ignorée"
##     - "Le temps en arrière-plan n'est pas compté"
##     - "Les valeurs survivent au rechargement et migrent depuis l'ancien format"
##   test_all: false
##   test_priority: "high_first"