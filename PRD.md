# PRD — CognitiveLoad Test with BITalino

## Problem Statement
Mesurer et visualiser comment la charge cognitive évolue quand on cumule 
des tâches mentales et physiques simultanées, et identifier le moment 
de bascule où le système cognitif est dépassé (modèle du "pichet qui déborde").

## Target Users
Binôme étudiant en contexte de labo. Un seul participant par session de test.

## End Users
- Les deux membres du binôme (développeurs et sujets de test)
- Potentiellement : démo devant le cours

---

## Functional Requirements

### FR1 — Connexion BITalino
- Le système doit se connecter à la carte BITalino Core BT via Bluetooth
- Adresse MAC configurable
- Fréquence d'acquisition : 1000 Hz
- Capteurs actifs : EDA (port A2), EMG (port A1), ACC (port A3), FSR (port A4)
- Le système doit afficher le niveau de batterie au démarrage

### FR2 — Calibration (Round 1)
- Durée : 60 secondes
- Acquisition de toutes les données capteurs au repos
- Calcul et sauvegarde des valeurs de référence (baseline) par capteur :
  - EDA : moyenne et écart-type au repos
  - EMG : niveau de bruit de base
  - ACC : valeurs de référence position neutre
  - FSR : valeur de repos (0 pression)
- Aucune interaction utilisateur requise sauf rester immobile

### FR3 — Round 2 : Test de base
- Affichage de questions de logique/raisonnement (QCM)
- Temps de réponse : 15 secondes par question
- Réponse via clavier (touches 1/2/3/4)
- Minimum 5 questions
- Enregistrement : réponse correcte/incorrecte, temps de réponse
- Acquisition capteurs continue en parallèle

### FR4 — Round 3 : Défi FSR
- Même questions QCM (temps réduit : 12 secondes)
- Défi intercalé : un compteur défile de 0 à 100 rapidement
- L'utilisateur doit appuyer sur le FSR pour stopper le compteur 
  le plus proche possible d'une valeur cible affichée
- Score FSR = écart entre valeur stoppée et valeur cible
- Acquisition capteurs continue

### FR5 — Round 4 : Double tâche EMG
- Même questions QCM (temps réduit : 10 secondes)
- Défi EMG intercalé : une barre de progression affiche le niveau 
  de contraction musculaire en temps réel
- L'utilisateur doit maintenir la contraction dans une zone cible 
  pendant 3 secondes
- Seuil cible EMG calculé à partir de la baseline + offset
- Interface visuellement plus chargée (couleurs, éléments supplémentaires)
- Acquisition capteurs continue

### FR6 — Round 5 : Surcharge maximale
- Questions complexes, temps très court (7 secondes)
- Défi EMG + défi FSR actifs simultanément avec les questions
- Sons distrayants joués aléatoirement
- Interface saturée visuellement
- Seuil EMG changeant toutes les 10 secondes
- Acquisition capteurs continue

### FR7 — Sauvegarde des données
- Toutes les données brutes capteurs sauvegardées en CSV 
  avec timestamp par round
- Données de performance (scores QCM, scores FSR, scores EMG) 
  sauvegardées en JSON
- Nommage : session_YYYYMMDD_HHMMSS/

### FR8 — Rapport final
- Affiché à la fin de la session (Round 5 terminé)
- Graphiques par capteur : évolution round par round
- Tableau de performance : scores QCM, FSR, EMG par round
- Identification automatique du "point de bascule" :
  round où EDA ou HR dépasse baseline + 2 écarts-types
- Export HTML

---

## Non-Functional Requirements

### NFR1 — Stack technique
- Python 3.10
- BITalino via librairie plux (déjà fonctionnelle dans main.py)
- UI : Tkinter (inclus dans Python, pas de dépendance supplémentaire)
- Visualisation : matplotlib
- Données : pandas, numpy

### NFR2 — Performance
- Latence affichage EMG temps réel : < 100ms
- Pas de perte de données capteurs pendant l'UI
- Acquisition capteurs dans un thread séparé de l'UI

### NFR3 — Structure
- main.py reste le fichier de test connexion existant, non modifié
- Le projet se lance via `python src/app.py`
- Chaque round est un module indépendant dans src/rounds/

---

## Success Criteria
1. On observe une augmentation significative de l'EDA au round 5 
   vs round 1 (baseline)
2. Les scores QCM diminuent du round 2 au round 5
3. Le rapport identifie un round de bascule cohérent avec 
   ce qu'a ressenti le participant
4. Aucune perte de données capteurs pendant une session complète
5. Le défi EMG fonctionne en temps réel sans lag visible

---

## Out of Scope
- Plusieurs participants simultanés
- Sauvegarde cloud
- Machine learning sur les données
- Support multi-plateforme (développé et testé sur la plateforme du binôme)