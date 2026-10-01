# Lancer Racontelle sur votre PC (Windows)

Procédure vérifiée le 25/09/2026 sur ce PC (Python 3.14, Node 24).

## Deux pièges propres à ce poste

1. **Chemins trop longs.** Le dossier du projet est très profond. Certains paquets (`anthropic`) dépassent la
   limite Windows de 260 caractères. L'environnement Python est donc installé dans un chemin court :
   `C:\Users\lekan\.racontelle-venv` (déjà créé, avec toutes les dépendances).
2. **Installation de Python coupée en deux.** Les exécutables sont dans `C:\Python314` et la bibliothèque
   standard dans `C:\Users\lekan\AppData\Local\Programs\Python\Python314`. Il faut donc définir `PYTHONHOME`
   avant chaque commande Python (voir ci-dessous). Une réinstallation propre de Python (python.org,
   « Repair » ou désinstaller puis réinstaller) supprimerait ce contournement.

Au début de chaque session PowerShell :

```powershell
$env:PYTHONHOME="C:\Users\lekan\AppData\Local\Programs\Python\Python314"
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
```

## Démarrer l'API

Sans base MongoDB installée, l'API peut tourner sur une base **simulée en mémoire** (`mongomock://`) :
parfaite pour tester, tout est effacé à l'arrêt. Dans le dossier `backend` :

```powershell
$env:MONGO_URL="mongomock://local"; $env:DB_NAME="racontelle_dev"
$env:JWT_SECRET="une-longue-phrase-secrete-de-plus-de-32-caracteres"
$env:APP_PUBLIC_URL="http://localhost:8001"; $env:LOCAL_STORAGE_DIR="C:\Users\lekan\.racontelle-data"
$env:ADMIN_TOKEN="jeton-admin-local-0123456789"
C:\Users\lekan\.racontelle-venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8001
```

Vérification : http://localhost:8001/api/ répond `{"message":"Racontelle API","status":"ok"}`.

Pour garder les données entre deux lancements, installez MongoDB Community Server (installateur .msi,
« Install as a Service ») et remplacez `MONGO_URL` par `mongodb://localhost:27017`.

## Lancer les tests du backend

Dans un second PowerShell (API démarrée comme ci-dessus, avec en plus `$env:RATE_LIMIT_DISABLED="1"`
**avant** `uvicorn`, sinon la protection anti-abus bloque les nombreuses inscriptions des tests) :

```powershell
$env:EXPO_PUBLIC_BACKEND_URL="http://127.0.0.1:8001"
C:\Users\lekan\.racontelle-venv\Scripts\python.exe -m pytest tests -p no:cacheprovider
```

Résultat du 25/09/2026 : 78 réussis, 24 échecs et 11 erreurs, tous expliqués dans `CONFORMITE.md`
(anciens tests d'Emergent, clés IA absentes, base simulée). Les tests de conformité et de sécurité des
médias passent tous (28/28) :

```powershell
C:\Users\lekan\.racontelle-venv\Scripts\python.exe -m pytest tests/test_conformite_family.py tests/test_iteration8_media_security.py -n 0 -p no:cacheprovider
```

## Démarrer l'application

Dépendances déjà installées. Si besoin de les réinstaller (yarn n'est pas installé globalement, on
passe par `npx`) :

```powershell
cd frontend
npx.cmd --yes yarn@1.22.22 install --network-concurrency 1
```

`--network-concurrency 1` évite une erreur de cache yarn fréquente sous Windows.

Créez `frontend\.env` :

```
EXPO_PUBLIC_BACKEND_URL=http://ADRESSE_IP_DU_PC:8001
```

(`ipconfig` → « Adresse IPv4 ». Pour le navigateur seul, `http://localhost:8001` suffit.)

```powershell
npx.cmd expo start
```

- **Téléphone** : même Wi-Fi que le PC, scannez le QR code avec Expo Go.
- **Navigateur** : appuyez sur `w`.

Contrôles du code : `node .\node_modules\typescript\bin\tsc --noEmit` et `node .\node_modules\eslint\bin\eslint.js app src`.
