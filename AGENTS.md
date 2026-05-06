# AGENTS.md

## Project Overview
**IQ Overload** - Application Python mesurant la charge cognitive via BITalino multi-capteurs.

### Phase 1 (Current)
Construction du socle technique :
- Connexion stable BITalino (100 Hz, 5 capteurs : EDA, EMG, ACC, FSR, PPG)
- Affichage temps réel des signaux (matplotlib)
- Calibration baseline (20 secondes au repos)
- Calcul CCI (Cognitive Capacity Index) et détection point de bascule
- Génération rapport HTML avec graphiques et analyse

### Phase 2 (Future)
Interface utilisateur avec 5 rounds de difficulté croissante, QCM, défis EMG/FSR.

## Project Structure
```
src/
├── app.py                    # Point d'entrée, orchestration
├── config.py                 # Constantes de configuration
├── bitalino_reader.py        # Acquisition capteurs (threaded)
├── visualizer.py             # Affichage matplotlib temps réel
├── calibration.py            # Calcul baseline 20s
├── cognitive_load.py         # Calcul CCI + détection tipping point
├── sensors/                  # Processors par capteur
│   ├── eda_processor.py
│   ├── emg_processor.py
│   ├── acc_processor.py
│   ├── fsr_processor.py
│   ├── ppg_processor.py
│   └── hrv_analyzer.py
└── report/
    ├── reporter.py           # Génération rapport HTML
    └── templates/
        └── report.html       # Template Jinja2
```

## Coding Standards

### Python Style
- **Version**: Python 3.10+
- **Style Guide**: PEP8 strict
- **Type Hints**: Obligatoires sur toutes les signatures publiques
- **Docstrings**: Format Google style sur toutes les fonctions/classes publiques
- **Line Length**: Max 100 caractères
- **Function Length**: Max 40 lignes (refactoriser si dépassement)

### Architecture
- **Threading**: Architecture producteur-consommateur avec `queue.Queue`
- **No Blocking**: Jamais de blocking call dans thread UI
- **Thread-Safe**: Utiliser `threading.Event` pour synchronisation
- **Error Handling**: Toujours catch exceptions dans threads (sinon crash silencieux)

### Data Processing
- **Numpy**: Pour tous les calculs mathématiques (pas de boucles Python pures)
- **Deque**: Fenêtres glissantes avec `maxlen` pour éviter croissance infinie
- **Dataclasses**: Pour structures de données (pas de dict quand structure définie)

## Dependencies
```txt
numpy>=1.24.0
pandas>=2.0.0
matplotlib>=3.7.0
scipy>=1.10.0
jinja2>=3.1.0
pytest>=7.3.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
```
**Note**: `plux.pyd` est un binaire local (pas dans PyPI)

## Allowed Actions

### Implementation
- ✅ Implémenter les modules selon **SPECS.md**
- ✅ Créer nouveaux fichiers dans `src/` selon structure définie
- ✅ Modifier `src/bitalino_reader.py` (ajouter threading, queue, reconnexion)
- ✅ Créer répertoires `data/` et `reports/` si nécessaire

### Testing
- ✅ Ajouter tests pytest dans `/tests`
- ✅ Créer fixtures partagées dans `tests/conftest.py`
- ✅ Mocker `plux.SignalsDev` pour tests unitaires
- ✅ Utiliser données synthétiques (numpy) pour tests

### Documentation
- ✅ Ajouter docstrings sur nouvelles fonctions
- ✅ Commenter code complexe (formules, algorithmes)
- ✅ Mettre à jour README.md avec instructions

## Forbidden Actions

### Code Modifications
- ❌ **NE PAS** modifier `src/plux.pyd` (binaire intouchable)
- ❌ **NE PAS** modifier la signature de `plux.SignalsDev.onRawFrame(nSeq, data)`
- ❌ **NE PAS** bloquer le thread BITalino avec `time.sleep()` ou I/O

### Dependencies
- ❌ **NE PAS** ajouter ML/DL frameworks lourds (TensorFlow, PyTorch)
- ❌ **NE PAS** ajouter GUI frameworks autres que matplotlib (Phase 1)
- ❌ **NE PAS** utiliser dépendances système non-portable

### Architecture
- ❌ **NE PAS** mélanger logique acquisition et UI dans même thread
- ❌ **NE PAS** utiliser variables globales pour partage données inter-threads
- ❌ **NE PAS** ignorer les exceptions dans callbacks/threads

## Test Requirements

### Coverage
- **Minimum**: 80% sur modules critiques (sensors, calibration, cognitive_load)
- **Commande**: `pytest tests/ --cov=src --cov-report=html`

### Test Types
- **Unit Tests**: Tous les processors, calibration, cognitive_load
- **Integration Tests**: bitalino_reader (mocké), app.py (partiel)
- **Mock Strategy**: Utiliser `pytest-mock` pour `plux.SignalsDev`

### Fixtures (tests/conftest.py)
- `temp_dir`: Répertoire temporaire pour outputs
- `synthetic_baseline_data`: BaselineData complet pour tests
- `mock_raw_frame`: RawFrame avec valeurs réalistes
- `synthetic_eda_data`, `synthetic_emg_data`, etc.

### Running Tests
```bash
# Tous les tests
pytest tests/ -v

# Tests spécifiques
pytest tests/test_calibration.py -v

# Avec couverture
pytest tests/ --cov=src --cov-report=html

# Skip integration tests
pytest tests/ -v -m "not integration"
```

## Critical Implementation Notes

### Threading Pitfalls
1. **Queue Timeout**: Toujours `queue.get(timeout=0.1)` pour éviter deadlock
2. **Stop Event**: Vérifier `stop_event.is_set()` dans toutes les boucles
3. **Exception Handling**: Wrapper thread functions dans try/except

### Data Validation
1. **Frame Validation**: Vérifier `len(frame.channels) == 5` avant accès
2. **Baseline Required**: Vérifier `baseline is not None` avant init processors
3. **HRV Minimum**: Besoin de 5+ IBIs pour calcul RMSSD valide

### Performance
1. **CCI Frequency**: Calculer seulement 1Hz (pas 100Hz)
2. **Plot Update**: Max 10Hz pour matplotlib (sinon lag)
3. **Numpy Vectorization**: Toujours préférer numpy vs boucles Python

### Memory Management
1. **Deque MaxLen**: Toujours définir pour fenêtres glissantes
2. **CSV Progressive**: En Phase 2, écrire CSV au fil de l'eau
3. **Close Resources**: Toujours fermer BITalino, fichiers, plots

## Entry Points

### Phase 1 - Main Application
```bash
python src/app.py
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Test coverage
pytest tests/ --cov=src --cov-report=html

# Specific test file
pytest tests/test_calibration.py -v
```

### Manual Testing
```bash
# Test connection only (existing script)
python src/bitalino_reader.py
```

## Success Criteria Phase 1

### Automated
- [ ] All pytest tests pass
- [ ] Code coverage > 80% on critical modules
- [ ] No flake8 warnings (PEP8 compliance)

### Manual
- [ ] Connection stable 10+ minutes without crash
- [ ] 5 sensor plots display simultaneously without lag
- [ ] Calibration produces consistent baseline (3 trials)
- [ ] CCI increases visibly during mental calculation
- [ ] Tipping point detected when stress sustained
- [ ] HTML report generated without errors
- [ ] Report contains all sections and plots
- [ ] CSV data readable and complete

## Development Workflow

1. **Read SPECS.md** section for module to implement
2. **Create test file first** (TDD approach when possible)
3. **Implement module** following specs exactly
4. **Run tests** until all pass
5. **Manual validation** if applicable
6. **Update tasks.md** to mark task complete
7. **Move to next task** in sequence

## Questions/Ambiguities

If anything is unclear in SPECS.md:
1. Check PRD.md for context/requirements
2. Check AGENTS.md for guidelines
3. Ask for clarification before implementing
4. Document decision in code comments

---

**Last Updated**: Following complete SPECS.md Phase 1
**Current Phase**: Phase 1 - Implementation Ready
**Next Milestone**: First working connection + visualizer