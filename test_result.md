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