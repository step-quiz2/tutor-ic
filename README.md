# Tutor IC — minimalist

Tutor socràtic mínim per a la interpretació d'un interval de confiança del 95%.
Dissenyat per a una demo en directe de ~20 minuts.

## Característiques

- **Un sol problema** (IC-001): interpretació de l'interval [3,2 ; 4,8].
- **Tres passos** Socràtics que escalen fins a la formulació correcta.
- **Un prerequisit** (PRE-PARAM): distinció paràmetre/estadístic.
- **Tres crides a Gemini**: jutjar, diagnosticar, generar pista.
- Senyals `?` (pista), `!text` (discrepància), `!!` (sortir).
- Rastre JSON visible al final per al professor.

## Instal·lació

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...   # clau gratuïta a https://aistudio.google.com/apikey
streamlit run app.py
```

(Opcional) Canviar el model:
```bash
export GEMINI_MODEL=gemini-2.5-flash   # default, recomanat per a la demo
# export GEMINI_MODEL=gemini-2.5-pro   # més qualitat, més car
```

## Demo planificada (20 minuts)

### Sessió A — "estudiant que raona bé"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | El 95% es refereix al procediment de construcció d'intervals: si repetíssim el procés moltes vegades amb mostres diferents, el 95% dels intervals construïts contindrien μ. És una propietat de l'eina, no del paràmetre. |
| 2 | Perquè μ és un paràmetre fix, no una variable aleatòria. Un cop l'interval [3,2; 4,8] està calculat, μ hi és o no hi és — és un fet ja determinat, no té sentit parlar de probabilitat. |
| 3 | Tenim una confiança del 95% que μ estigui dins de [3,2; 4,8], on "confiança" vol dir fiabilitat a llarg termini del procediment. Per a aquest interval concret no podem fer una afirmació probabilística. |

Resultat esperat: 3 × `correct`, sessió completada.

### Sessió B — "estudiant que comet l'error clàssic"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | Hi ha un 95% de probabilitat que μ estigui entre 3,2 i 4,8. |
| (1 bis) | (després del retrocés a PRE-PARAM, respondre la pregunta del prereq amb alguna cosa raonable, p.ex.: «μ és la mitjana real de la població, és fixa però no la sabem; x̄ canvia segons la mostra»). |
| 1 (segon intent) | Vull dir que estem segurs al 95% que μ està entre 3,2 i 4,8. |
| 1 (tercer intent) | El 95% es refereix a la freqüència amb què aquest procediment, repetit moltes vegades, dona intervals que contenen μ. |

Resultat esperat: `typical_error` → retrocés a `PRE-PARAM` → pista socràtica → finalment `correct`.

## Cost

Gemini Flash. Cada sessió completa fa entre 4 i 8 crides totals, ~3 500 tokens
en total per sessió. Cost estimat: <0,1 cèntim de dòlar per sessió. Pots fer 20
minuts de demo amb la quota gratuïta sense apropar-te al límit.

## Fitxers

| Fitxer | Què fa |
|---|---|
| `problem.py` | El problema, els passos, el prerequisit, el catàleg d'errors |
| `llm.py` | Tres crides a Gemini (`judge_step`, `diagnose_dependency`, `generate_hint`) |
| `app.py` | UI Streamlit + lògica de torn + rastre JSON |
| `requirements.txt` | Dependències (Streamlit + google-genai) |

## Què NO té (intencionalment)

- Sense persistència a disc (la sessió es perd quan es tanca la pestanya).
- Sense pseudonimització ni RGPD (no és per a un pilot amb alumnes reals).
- Sense reintents en errors de l'API (per a 20 min de demo no calen).
- Sense bilingüisme (només català).
- Sense DAG, sense profunditat de retrocés > 1, sense detecció de mal ús.
- Sense tests.

Per a qualsevol d'aquestes coses, mira els projectes germans `tutor-eq`
i `tutor-grups`.
