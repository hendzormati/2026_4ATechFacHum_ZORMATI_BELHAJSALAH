# PRD — IQ Overload

## Application Name
**IQ Overload**

## Problem Statement
Mesurer et visualiser comment la charge cognitive évolue quand on cumule
des tâches mentales et physiques simultanées, et identifier le moment
de bascule où le système cognitif est dépassé (modèle du "pichet qui déborde").
L'application croise des données physiologiques multi-capteurs avec des
performances cognitives pour produire un rapport analytique objectif.

## Target Users
Binôme étudiant en contexte de labo. Un seul participant par session de test.

## End Users
- Les deux membres du binôme (développeurs et sujets de test)
- Potentiellement : démo devant le cours

---

## Development Phases

Le projet est découpé en deux phases principales et séquentielles.
La Phase 2 ne commence qu'une fois la Phase 1 entièrement validée.

---

# PHASE 1 — Acquisition, Signal Processing & Reporting

## Objectif de la Phase 1
Construire le socle technique invisible à l'utilisateur final :
connexion stable, lecture fiable de tous les capteurs, affichage
dynamique des signaux, calcul des références physiologiques,
et génération du rapport analytique.

---

## P1 — Étape 1 : Connexion continue

### Contexte
Actuellement main.py et plux.pyd testent une connexion de 20 secondes
puis ferment. Ce comportement doit être remplacé par une connexion
persistante qui dure toute la session de l'application.

### État initial du repo
- `main.py` — test de connexion 20 secondes, ne pas modifier
- `plux.pyd` — librairie binaire BITalino, ne pas modifier
- `src/bitalino_reader.py` — à créer, remplace la logique de main.py

### Requirements P1-E1
- La connexion BITalino s'établit au lancement de l'application
- Elle reste active jusqu'à la fermeture explicite du programme
- La connexion tourne dans un thread dédié séparé du thread principal
- Adresse MAC configurable dans un fichier `config.py`
- Fréquence d'acquisition : 1000 Hz
- Le niveau de batterie est affiché au démarrage
- En cas de déconnexion : tentative de reconnexion automatique x3
  avant d'afficher une erreur

### Fichiers concernés
- `src/bitalino_reader.py` (nouveau)
- `src/config.py` (nouveau)

### Success Criteria E1
- Le programme tourne sans interruption pendant 10 minutes minimum
- La déconnexion volontaire (Ctrl+C ou fermeture fenêtre) ferme
  proprement la connexion BITalino sans erreur

---

## P1 — Étape 2 : Affichage dynamique des 6 capteurs simultanément

### Contexte
Une fois la connexion stable, afficher en temps réel les signaux
de tous les capteurs actifs dans des graphiques dynamiques simultanés.

### Capteurs et ports BITalino
| Capteur | Port | Câble      | Ce qu'on mesure                          |
|---------|------|------------|------------------------------------------|
| EDA     | A2   | 2-leads    | Conductance cutanée, activation émotionnelle |
| EMG     | A1   | 3-leads    | Contraction musculaire                   |
| ACC     | A3   | intégré    | Micro-mouvements, agitation              |
| FSR     | A4   | direct     | Pression appliquée sur le capteur        |
| ECG     | A5   | 3-leads    | Rythme cardiaque                         |
| PPG     | A6   | 3-leads    | Variabilité cardiaque optique            |

### Requirements P1-E2
- Affichage de 6 graphiques simultanés dans une même fenêtre
- Chaque graphique affiche :
  - Le nom du capteur (ex: "EDA — Activité électrodermale")
  - Le signal brut en temps réel sous forme de courbe
  - L'axe Y avec unité si applicable
  - L'axe X en secondes (fenêtre glissante de 10 secondes)
- Fréquence de rafraîchissement : 1 fois par seconde minimum,
  plus rapide si possible sans impact sur l'acquisition
- L'acquisition capteurs ne doit jamais être bloquée par l'affichage
  (threads séparés)
- La fenêtre d'affichage reste ouverte tant que la connexion est active

### Fichiers concernés
- `src/visualizer.py` (nouveau)
- `src/bitalino_reader.py` (modifié)

### Success Criteria E2
- Les 6 courbes s'affichent simultanément sans lag visible
- Contracter le muscle fait réagir la courbe EMG en moins de 200ms
- Appuyer sur le FSR fait réagir la courbe FSR immédiatement
- Aucune perte de données capteurs pendant l'affichage

---

## P1 — Étape 3 : Calibration et valeurs de référence

### Contexte
Une fois l'affichage validé, lancer une session de calibration de
20 secondes pendant laquelle l'utilisateur reste au repos.
Ces données établissent la baseline individuelle utilisée dans
toute l'analyse ultérieure.

### Requirements P1-E3

#### Acquisition de référence
- Durée : 20 secondes minimum au repos
- Tous les capteurs actifs pendant la calibration
- Les courbes restent affichées pendant la calibration

#### Valeurs calculées par capteur

**EDA**
- Moyenne baseline (SCL — Skin Conductance Level)
- Écart-type baseline
- Seuil d'activation = moyenne + 2 × écart-type
- Seuil de stress élevé = moyenne + 3 × écart-type

**EMG**
- Niveau de bruit de base (RMS au repos)
- Seuil de contraction légère = bruit × 3
- Seuil de contraction forte = bruit × 8
- Seuil cible pour les défis = bruit × 5 (modifiable)

**ACC**
- Vecteur magnitude moyen au repos
- Seuil d'agitation = moyenne + 2 × écart-type
- Seuil de mouvement significatif = moyenne + 4 × écart-type

**FSR**
- Valeur au repos (devrait être proche de 0)
- Seuil de détection d'appui = repos + offset fixe (20 unités)

**ECG**
- Fréquence cardiaque de base (BPM)
- Intervalle R-R moyen
- Seuil tachycardie = BPM baseline × 1.2

**PPG**
- HRV (Heart Rate Variability) baseline
- BPM optique de référence

#### Sauvegarde
- Toutes les valeurs de référence sauvegardées dans
  `data/baseline_YYYYMMDD_HHMMSS.json`
- Format JSON structuré par capteur

### Fichiers concernés
- `src/calibration.py` (nouveau)
- `src/sensors/eda_processor.py` (nouveau)
- `src/sensors/emg_processor.py` (nouveau)
- `src/sensors/acc_processor.py` (nouveau)
- `src/sensors/fsr_processor.py` (nouveau)
- `src/sensors/ecg_processor.py` (nouveau)
- `src/sensors/ppg_processor.py` (nouveau)

### Success Criteria E3
- Les valeurs de référence sont cohérentes avec ce qu'on observe
  sur les courbes pendant le repos
- Le fichier JSON est généré et lisible
- Les seuils EMG permettent de distinguer repos / contraction légère
  / contraction forte lors d'un test manuel

---

## P1 — Étape 4 : Analyse charge cognitive et mémoire de travail

### Contexte
Définir les indicateurs et algorithmes qui permettent de détecter
la surcharge cognitive à partir des signaux physiologiques.
C'est le cœur analytique du projet, directement lié au modèle
théorique du cours.

### Indicateurs de charge cognitive retenus

#### Indice EDA (stress émotionnel)
eda_index = (valeur_actuelle - baseline_EDA) / ecart_type_EDA
- < 1 : charge normale
- 1 à 2 : charge modérée
- > 2 : charge élevée (activation sympathique)
- > 3 : surcharge

#### Indice EMG (tension musculaire involontaire)
emg_tension = RMS_actuel / bruit_baseline
- Détecte la tension musculaire résiduelle entre les défis
- Indicateur indirect d'anxiété cognitive

#### Indice ACC (agitation motrice)
acc_index = magnitude_actuelle / magnitude_baseline
- Micro-mouvements involontaires = agitation cognitive
- Augmente quand le cerveau est surchargé

#### HRV (variabilité cardiaque — indicateur clé)
hrv_drop = (hrv_baseline - hrv_actuel) / hrv_baseline × 100
- Diminution de HRV = augmentation charge mentale
- > 20% de drop = charge significative
- > 40% de drop = surcharge

#### Indice de charge cognitive global (CCI)
CCI = (eda_index × 0.35) + (hrv_drop × 0.35) +
(acc_index × 0.15) + (emg_tension × 0.15)
- Score composite normalisé entre 0 et 10
- Calculé toutes les secondes
- Historique conservé pour le rapport

#### Détection du point de bascule
- Point de bascule = premier moment où CCI > 7 pendant > 3 secondes
- Ou : premier round où la moyenne CCI dépasse le double
  de la moyenne CCI du round 1

### Lien avec le modèle théorique du cours
| Concept cours              | Indicateur IQ Overload        |
|----------------------------|-------------------------------|
| Pichet qui déborde         | CCI > 7 (point de bascule)    |
| Charge mémoire de travail  | HRV drop + EDA index          |
| État émotionnel perturbateur| EDA index > 2                |
| Agitation cognitive        | ACC index > 2                 |
| Fatigue musculaire/tension | EMG tension résiduelle        |

### Fichiers concernés
- `src/cognitive_load.py` (nouveau)
- `src/sensors/hrv_analyzer.py` (nouveau)

### Success Criteria E4
- Le CCI augmente measurablement quand on fait un calcul mental
  difficile pendant le test
- Le point de bascule est détecté dans les 2 secondes après
  un pic de stress observable sur les courbes

---

## P1 — Étape 5 : Reporting

### Contexte
Générer un rapport complet à la fin d'une session qui croise
les données physiologiques avec les performances.

### Requirements P1-E5

#### Données sauvegardées pendant la session
- Données brutes capteurs : CSV par capteur, une ligne par seconde
- CCI calculé : CSV avec timestamp
- Événements annotés : JSON (début/fin round, questions posées,
  réponses données, défis EMG/FSR)

#### Structure du rapport HTML
1. **En-tête** : date, durée session, adresse MAC carte
2. **Résumé baseline** : tableau des valeurs de référence par capteur
3. **Graphiques par capteur** : évolution sur toute la session
   avec annotations des rounds
4. **Graphique CCI** : courbe du score de charge cognitive global
   avec marqueur du point de bascule
5. **Tableau performance** : scores QCM, FSR, EMG par round
   (préparé pour Phase 2, vide en Phase 1)
6. **Analyse automatique** :
   - Round où le point de bascule a été détecté
   - Capteur le plus réactif (celui qui a le plus dévié de baseline)
   - Corrélation entre montée EDA et chute HRV
7. **Conclusion** : texte généré automatiquement décrivant
   le profil de charge cognitive du participant

#### Format de sortie
- `reports/report_YYYYMMDD_HHMMSS.html` — rapport complet
- `data/session_YYYYMMDD_HHMMSS/` — données brutes CSV + JSON

### Fichiers concernés
- `src/report/reporter.py` (nouveau)
- `src/report/templates/report.html` (nouveau)

### Success Criteria E5
- Le rapport HTML s'ouvre dans un navigateur sans erreur
- Les graphiques sont lisibles et correctement annotés
- Le point de bascule est visible et cohérent avec les courbes brutes

---

## P1 — Validation Globale Phase 1

### Critères de passage à la Phase 2
- [ ] Connexion stable 10 minutes sans interruption
- [ ] 6 courbes affichées simultanément sans perte de données
- [ ] Valeurs de calibration cohérentes et reproductibles
- [ ] CCI réactif et cohérent avec les observations visuelles
- [ ] Rapport HTML généré et complet après une session test
- [ ] Tous les tests pytest passent

---

# PHASE 2 — Interface Utilisateur (IQ Overload Experience)

## Statut
**À définir après validation complète de la Phase 1.**

## Aperçu préliminaire
La Phase 2 ajoute l'expérience utilisateur complète par-dessus
le socle technique de la Phase 1 :
- Interface graphique dédiée avec les 5 rounds
- Questions QCM de logique et raisonnement
- Défis EMG et FSR interactifs
- Dégradation progressive de l'interface (charge visuelle, sons)
- Intégration du rapport Phase 1 avec les scores de performance

Les spécifications détaillées de la Phase 2 seront rédigées
une fois la Phase 1 validée.

---

# Non-Functional Requirements (toutes phases)

## Stack technique
- Python 3.10
- BITalino via librairie plux (main.py + plux.pyd existants)
- UI Phase 1 : matplotlib (affichage signaux)
- UI Phase 2 : Tkinter
- Données : pandas, numpy
- Tests : pytest
- Rapport : HTML/CSS pur (pas de dépendance externe)

## Architecture
- `main.py` et `plux.pyd` : intouchables
- Point d'entrée Phase 1 : `python src/app.py`
- Acquisition capteurs : toujours dans un thread séparé
- Jamais de blocking call dans le thread UI

## Qualité
- PEP8, type hints, docstrings sur toutes les fonctions publiques
- Fonctions < 40 lignes
- Tout nouveau module a au minimum un test pytest

---

# Structure du repo cible (fin Phase 1)
/
├── main.py                          ← intouchable
├── plux.pyd                         ← intouchable
├── PRD.md
├── SPECS.md                         ← généré après PRD
├── AGENTS.md
├── requirements.txt
├── src/
│   ├── app.py                       ← point d'entrée
│   ├── config.py                    ← adresse MAC, constantes
│   ├── bitalino_reader.py           ← connexion continue + thread
│   ├── visualizer.py                ← affichage 6 courbes
│   ├── calibration.py               ← baseline 20 secondes
│   ├── cognitive_load.py            ← calcul CCI + bascule
│   ├── sensors/
│   │   ├── eda_processor.py
│   │   ├── emg_processor.py
│   │   ├── acc_processor.py
│   │   ├── fsr_processor.py
│   │   ├── ecg_processor.py
│   │   ├── ppg_processor.py
│   │   └── hrv_analyzer.py
│   └── report/
│       ├── reporter.py
│       └── templates/
│           └── report.html
├── tests/
│   ├── test_bitalino_reader.py
│   ├── test_calibration.py
│   ├── test_cognitive_load.py
│   └── test_sensors/
├── data/                            ← gitignored, données sessions
└── reports/                         ← gitignored, rapports HTML