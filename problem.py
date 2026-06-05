"""
Tutor — base de dades pedagògica.

Dos problemes disponibles: IC-001 (interval de confiança) i CAUS-001
(correlació vs. causalitat). L'alumne tria quin treballar a l'inici
de la sessió.

Estructura:
  PROBLEMS:           dict[str, dict] — registry indexat per id del
                      problema. Cada entrada conté:
                        "id":            id del problema
                        "title_human":   etiqueta breu per al picker UI
                        "problem":       dict amb id/tema/enunciat/passos
                        "prerequisites": dict de prerequisits (PRE-*)
                        "dependencies":  dict de dependències conceptuals
                        "error_catalog": dict d'errors típics
                        "prereq_id":     id del prerequisit únic
  DEFAULT_PROBLEM_ID: id per defecte per a back-compat (tests, scripts
                      que accedeixen als noms globals PROBLEM, etc.).
  get(problem_id):    retorna el bundle per a aquest id.
  list_ids():         retorna [(id, title_human), ...] per al picker.

Per a codi que encara depèn dels noms globals (PROBLEM, PREREQUISITES,
DEPENDENCIES, ERROR_CATALOG), aquests apunten al problema per defecte
(CAUS-001) per back-compat. Codi nou hauria d'usar PB.get(problem_id).
"""

# =============================================================================
# IC-001 — Interpretació d'un interval de confiança
# =============================================================================

_IC001_ERROR_CATALOG = {
    "INT_prob_param": (
        "Atribueix probabilitat al paràmetre poblacional. "
        "Tracta μ com si fos una variable aleatòria."
    ),
    "INT_prob_sample": (
        "Confon l'IC amb una afirmació sobre futures mostres."
    ),
    "KEY_only": (
        "Resposta-keyword: conté un terme correcte (constant, fix, "
        "paràmetre, confiança, repetició, procediment...) però no el "
        "justifica ni l'aplica a la pregunta concreta. Cal desenvolupar "
        "el raonament: explicar QUÈ vol dir el terme en aquest context "
        "i PER QUÈ respon la pregunta."
    ),
    "GEN_other": "Error no catalogat.",
}

_IC001_DEPENDENCIES = {
    "param_vs_stat": {
        "description": (
            "Diferència entre paràmetre poblacional (μ, fix, "
            "desconegut) i estadístic mostral (x̄, aleatori)."
        ),
        "keywords": ["fix", "fixa", "fixe", "constant", "paràmetre",
                     "aleatori", "aleatòri", "varia", "no aleatori"],
        "prerequisite": "PRE-PARAM",
    },
}

_IC001_PREREQUISITES = {
    "PRE-PARAM": {
        "id": "PRE-PARAM",
        "concept": "param_vs_stat",
        "question": (
            "Quina diferència hi ha entre μ (la mitjana poblacional) i "
            "x̄ (la mitjana d'una mostra concreta)? "
            "Quina de les dues és aleatòria i quina és fixa?"
        ),
        "keywords_required": ["fix", "fixa", "fixe", "constant",
                              "paràmetre", "no aleatori"],
        "forbidden_keywords": ["μ és aleatòria", "mu és aleatòria",
                               "μ és aleatòri", "mu és aleatòri"],
        "explanation": (
            """**μ és un paràmetre poblacional**: un nombre fix, desconegut, però **no aleatori**.
**x̄ és un estadístic mostral**: varia d'una mostra a una altra, és **aleatori**.

La inferència freqüentista fa afirmacions probabilístiques sobre x̄ (i els intervals construïts a partir de x̄), però no sobre μ."""
        ),
    },
}

_IC001_PROBLEM = {
    "id": "IC-001",
    "tema": "Interpretació d'un interval de confiança",
    "enunciat": (
        """S'ha fet una recerca per estimar quantes hores al dia estudien, durant l'època d'exàmens, els estudiants de primer curs d'un Grau universitari. La població d'interès són aproximadament 250 estudiants.
A partir d'una mostra aleatòria de 44 estudiants obtenim:
  - Mitjana mostral: x̄ = 4,0 hores/dia
  - Desviació estàndard estimada: σ ≈ 2,7 hores

S'obté un interval de confiança del 95% per a la mitjana (μ):

  [3,2 ; 4,8] hores/dia"""
    ),
    "dependencies": ["param_vs_stat"],
    "passos": [
        {
            "id": 1,
            "text": (
                """El nivell de confiança del 95% que apareix a l'enunciat fa referència a una probabilitat. 

Sobre què fa referència aquesta probabilitat?"""
            ),
            "expected_summary": (
                "El 95% és una propietat del procediment: si "
                "repetíssim el procés amb moltes mostres diferents, "
                "el 95% dels intervals construïts contindrien μ. "
                "És una afirmació sobre intervals (que sí són "
                "aleatoris perquè depenen de la mostra), NO sobre μ."
            ),
            "typical_error": (
                "Dir que hi ha un 95% de probabilitat que μ "
                "estigui entre 3,2 i 4,8 (atribuir probabilitat al "
                "paràmetre poblacional)."
            ),
            "typical_error_label": "INT_prob_param",
            "key_concepts": ["param_vs_stat"],
            "canonical_question": (
                """El nivell de confiança del 95% que apareix a l'enunciat fa referència a una probabilitat. 

Sobre què fa referència aquesta probabilitat?"""
            ),
            "pistes": [
                """La mitjana mostral i l'interval que en surt canviarien si repetíssim l'estudi; en canvi, la mitjana (μ) no canviaria.""",
                "El 95% és una propietat del *procediment*: de tots els "
                "intervals que construiríem repetint el mostreig, el 95% "
                "contindrien μ. No és una afirmació sobre μ.",
            ],
        },
        {
            "id": 2,
            "text": (
                """Imagina que algú diu:
«Hi ha una probabilitat del 95% que la mitjana real (μ) estigui entre 3,2h/dia i 4,8h/dia».

Per què aquesta frase és incorrecta?"""
            ),
            "expected_summary": (
                "Perquè μ és un paràmetre fix, no una variable "
                "aleatòria. Un cop l'interval [3,2; 4,8] està "
                "calculat, μ hi és o no hi és — no té sentit parlar "
                "de probabilitat sobre un fet ja determinat. "
                "L'aleatorietat era a la mostra (i a l'interval "
                "construït a partir d'ella), no al paràmetre."
            ),
            "typical_error": (
                "Justificar-ho parlant de mostres futures, o "
                "no veure que un cop construït l'interval ja "
                "no queda aleatorietat residual."
            ),
            "typical_error_label": "INT_prob_param",
            "key_concepts": ["param_vs_stat"],
            "canonical_question": (
                """Imagina que algú diu:
«Hi ha una probabilitat del 95% que la mitjana real (μ) estigui entre 3,2h/dia i 4,8h/dia».

Per què aquesta frase és incorrecta?"""
            ),
            "pistes": [
                "Què té de diferent μ respecte de la mostra? Una de les "
                "dues coses és aleatòria i l'altra no.",
                "Un cop l'interval [3,2 ; 4,8] ja està calculat, μ hi és "
                "o no hi és. No té sentit parlar de probabilitat sobre un "
                "fet ja determinat: l'aleatorietat era a la mostra.",
            ],
        },
        {
            "id": 3,
            "text": (
                """Per acabar, explica amb les teves paraules com interpretes l'interval [3,2 ; 4,8] hores/dia, per a la mitjana μ d'hores d'estudi diari."""
            ),
            "expected_summary": (
                "Tenim una *confiança* del 95% que μ estigui dins "
                "de [3,2; 4,8], entenent 'confiança' com la "
                "fiabilitat a llarg termini del procediment: si "
                "repetíssim moltes vegades, el 95% dels intervals "
                "construïts d'aquesta manera contindrien μ. "
                "Per a aquest interval concret no podem parlar de "
                "probabilitat."
            ),
            "typical_error": (
                "Tornar a dir 'probabilitat del 95%' encara que "
                "estigui demanant una formulació correcta."
            ),
            "typical_error_label": "INT_prob_param",
            "key_concepts": ["param_vs_stat"],
            "canonical_question": (
                """Per acabar, explica amb les teves paraules com interpretes l'interval [3,2 ; 4,8] hores/dia, per a la mitjana μ d'hores d'estudi diari."""
            ),
            "pistes": [
                "Comença la frase amb «Tenim una confiança del 95%...» en "
                "lloc de «la probabilitat...». El canvi de paraula no és "
                "cosmètic: és el cor del concepte.",
                "'Confiança' aquí vol dir la fiabilitat a llarg termini "
                "del procediment: si el repetíssim moltes vegades, el 95% "
                "dels intervals construïts contindrien μ.",
            ],
        },
    ],
}


# =============================================================================
# CAUS-001 — Correlació vs. causalitat
# =============================================================================

_CAUS001_ERROR_CATALOG = {
    "CAUS_direct": (
        "Atribueix causalitat directa a partir d'una associació "
        "observada, sense considerar alternatives. Tracta una "
        "diferència estadística entre grups (o una correlació alta) "
        "com si fos evidència de mecanisme."
    ),
    "CAUS_no_alternatives": (
        "Quan se li demana, no genera (o genera de manera incompleta) "
        "explicacions alternatives a la causalitat directa. Sol "
        "quedar-se amb una sola variable confusora sense veure el feix "
        "de factors que actuen alhora, o no reconèixer la diferència "
        "entre 'l'origen causa X' i 'el context associat a l'origen "
        "causa X'."
    ),
    "KEY_only": (
        "Resposta-keyword: conté un terme correcte (correlació, "
        "causalitat, confusora, context, socioeconòmic...) però no el "
        "justifica ni l'aplica a la pregunta concreta. Cal "
        "desenvolupar el raonament: explicar QUÈ vol dir el terme en "
        "aquest context i PER QUÈ respon la pregunta."
    ),
    "GEN_other": "Error no catalogat.",
}

_CAUS001_DEPENDENCIES = {
    "confounding_variable": {
        "description": (
            "Una variable confusora és una tercera variable que causa "
            "alhora les dues variables observades, produint una "
            "associació entre elles sense relació causal directa."
        ),
        "keywords": [
            "confus", "tercera", "amagada", "oculta", "comuna",
            "calor", "temperatura", "estiu", "estival", "fa calor",
            "afecta totes dues", "afecta les dues",
            "afecta a totes dues", "afecta a les dues",
        ],
        "prerequisite": "PRE-CONFOUNDER",
    },
}

_CAUS001_PREREQUISITES = {
    "PRE-CONFOUNDER": {
        "id": "PRE-CONFOUNDER",
        "concept": "confounding_variable",
        "question": (
            """En un poble de la costa observem que, dia a dia, les **hores de sol** i les **vendes de begudes fredes** estan fortament correlacionades (r = 0,85).

1. Podem afirmar que tenir més hores de sol **és la causa** que la gent compri més begudes fredes? 
2. Creus que pots explicar millor per quin motiu estan correlacionades?"""
        ),
        "keywords_required": [
            "confus", "tercera", "amagada", "oculta", "comuna",
            "calor", "temperatura", "estiu", "estival", "fa calor",
            "afecta totes dues", "afecta les dues",
            "afecta a totes dues", "afecta a les dues",
        ],
        "forbidden_keywords": [],
        "explanation": (
            """Una **variable confusora** és una tercera variable que causa alhora les dues variables observades, produint una associació entre elles sense que cap de les dues causi l'altra.

En aquest exemple, la **calor** (o, més en general, el fet que sigui un dia d'estiu) causa alhora moltes hores de sol i moltes vendes de begudes fredes.

El sol i les begudes fredes no estan en una relació causal directa: tots dos són efectes de la mateixa causa subjacent. Aquesta és la raó fonamental per la qual una correlació observada, per alta que sigui, no permet inferir causalitat: sempre podem estar veient l'ombra d'una variable confusora que no hem mesurat."""
        ),
    },
}

_CAUS001_PROBLEM = {
    "id": "CAUS-001",
    "tema": "Interpretació d'una correlació observada — correlació vs. causalitat",
    "enunciat": (
        """La Fundació Bofill (2024) i Idescat i EPA (2023 aporten dades sobre l'AEP: taxa d'abandonament escolar prematur.

A Catalunya l'AEP entre joves de 18 a 24 anys és:
- d'un 36,1% entre joves d'origen estranger
- d'un 10,6% entre joves de nacionalitat espanyola.

La taxa és més de tres vegades superior entre l'alumnat d'origen migrat.
Anem a interpretar aquesta diferència pas a pas, amb dades reals i càlculs."""
    ),
    "dependencies": ["confounding_variable"],
    "passos": [
        {
            "id": 1,
            "text": (
                "Tenim aquestes dades publicades (Bofill / Idescat, "
                "2023):\n\n"
                "a) AEP global a Catalunya (18-24 anys): 14,0%\n"
                "b) Percentatge d'alumnes de secundària de "
                "nacionalitat estrangera: 12,6%\n"
                "c) AEP entre joves d'origen estranger: 36,1%\n\n"
                "Calcula amb una mitjana ponderada la taxa d'AEP que "
                "esperaríem per als joves de nacionalitat espanyola. "
                "Compara-la amb el 10,6%, que reporta la mateixa "
                "font.\n\n"
                "Pregunta 1. Què pots concloure? Creus que la "
                "diferència és real, o bé és un artefacte estadístic, "
                "o bé no podem dir-ho?\n\n"
                "Pregunta 2. Aquesta consistència aritmètica, ens diu "
                "res sobre si l'origen migrat és la causa que la taxa "
                "es tripliqui?"
            ),
            "expected_summary": (
                "L'alumne ha de fer la mitjana ponderada inversa: "
                "14,0 = 0,126 × 36,1 + 0,874 × x, "
                "d'on x = (14,0 − 0,126 × 36,1) / 0,874 ≈ **10,82%**. "
                "Aquest valor calculat quadra raonablement bé amb el "
                "10,6% reportat per la mateixa font; la petita "
                "discrepància s'explica per arrodoniments i pel fet que "
                "el 12,6% és el % d'alumnes de secundària, no exactament "
                "el % de joves 18-24 amb nacionalitat estrangera. "
                "**Lliçó central**: el gap de 25,5 punts (36,1% vs 10,6%) "
                "és aritmèticament consistent dins de les fonts oficials "
                "— NO és un artefacte de mostra ni un error de càlcul, és "
                "una diferència empíricament ben establerta entre grups. "
                "Però que el gap sigui **real** NO vol dir que sigui "
                "**causal**. La verificació aritmètica és el punt de "
                "partida del problema, no la seva resposta. Per atribuir "
                "el gap a 'l'origen migrat com a causa directa' calen "
                "arguments més enllà de la comparació crua, perquè dos "
                "grups que difereixen en una variable solen també diferir "
                "en moltes altres."
            ),
            "typical_error": (
                "Confondre 'la diferència és real' amb 'l'origen és la "
                "causa': un cop verificat aritmèticament el gap, l'alumne "
                "pot saltar a la conclusió causal directa. O al revés: no "
                "fer el càlcul i discutir filosòficament si la diferència "
                "existeix, quan amb 5 línies d'aritmètica es comprova. "
                "També: no saber fer la mitjana ponderada — el tutor li "
                "ha d'explicar la fórmula en una frase i tirar endavant, "
                "no és el moment d'aturar la sessió per ensenyar "
                "aritmètica de l'ESO."
            ),
            "typical_error_label": "CAUS_direct",
            "key_concepts": ["confounding_variable"],
            "canonical_question": (
                """1) Fes la mitjana ponderada per estimar l'AEP esperada dels joves de nacionalitat espanyola
2) Compara-la amb el 10,6% que tenim de les dades.
3) La diferència entre grups, és real o és un artefacte? I si és real, ja en podem concloure que l'origen migrat n'és la causa?"""
            ),
            "pistes": [
                """Equació per a trobar la mitjana ponderada: 
14,0 = 0,126 · 36,1 + 0,874 · x.""",
                """El càlcul només confirma que el gap és aritmèticament consistent (és real, no un error de mostra).

Però real no implica causal: els dos grups que difereixen en l'origen també difereixen en moltes altres coses.""",
            ],
        },
        {
            "id": 2,
            "text": (
                "El Pas 2 es desplega en quatre subapartats. Treballarem "
                "cada un per separat.\n\n"
                "── PAS 2.a (concepte). ──\n\n"
                "Sabem que el gap entre les dues taxes és real. Però "
                "no sabem encara si l'origen migrat n'és la causa o "
                "si es tracta d'una associació espúria. Una associació "
                "és espúria quan una tercera variable (una variable "
                "confusora) genera la correlació sense que les dues "
                "variables observades tinguin relació causal entre "
                "elles.\n\n"
                "Per ser confusora de la relació origen → AEP, una "
                "variable X ha de complir dos criteris alhora:\n\n"
                "(a) X correlaciona amb l'AEP (prediu-la).\n"
                "(b) X es distribueix de manera diferent entre joves "
                "d'origen migrat i joves nadius.\n\n"
                "Atenció: complir només (a) no és suficient. Hi ha "
                "variables que prediuen molt bé l'AEP però que NO són "
                "confusores d'aquesta relació.\n\n"
                "── PAS 2.b (Variable 1: renda familiar). ──\n\n"
                "Dades reals publicades (Bofill 2024 / PISA 2022):\n\n"
                "  - AEP entre joves de renda baixa: 19,4%\n"
                "  - AEP entre joves de renda alta: 1,9%\n"
                "  - Alumnat d'origen migrat amb nivell socioeconòmic "
                "baix: 52,7%\n"
                "  - Alumnat autòcton amb nivell socioeconòmic baix: "
                "13,4%\n\n"
                "Fes la mitjana ponderada per calcular l'AEP esperada "
                "per a cada grup d'origen, suposant que la renda fos "
                "l'únic factor. Quants punts del gap (25,5) explica? "
                "És confusora? Per què?\n\n"
                "── PAS 2.c (Variable 2: sexe). ──\n\n"
                "Dades reals publicades (Bofill 2024 / Idescat 2024):\n\n"
                "  - AEP entre nois: 15,8%\n"
                "  - AEP entre noies: 12,0%\n"
                "  - Homes entre població de nacionalitat estrangera: "
                "51,7%\n"
                "  - Homes entre població de nacionalitat espanyola: "
                "48,7%\n\n"
                "Mateixa pregunta: AEP esperada per cada grup, punts "
                "de gap, és confusora?\n\n"
                "── PAS 2.d (Variable 3: centres d'alta complexitat). ──\n\n"
                "Dades reals publicades (Zancajo & Bueno, Bofill 2024):\n\n"
                "  - Taxa d'abandonament en centres d'alta complexitat: "
                "11,8%\n"
                "  - Taxa d'abandonament a la resta de centres: 5,4%\n"
                "  - Alumnat estranger en centres d'alta complexitat: "
                "~28%\n"
                "  - Alumnat autòcton en centres d'alta complexitat: "
                "~4%\n\n"
                "Mateixa pregunta. I quan acabis: quina part del gap "
                "real (25,5 punts) queda explicada per les tres "
                "variables sumades? Què podria explicar la resta?"
            ),
            "expected_summary": (
                "L'alumne ha de fer els tres càlculs i classificar-los "
                "correctament.\n\n"
                "VARIABLE 1 — Renda: **CONFUSORA FORTA**.\n"
                "  AEP nadius esperada = 0,134 × 19,4 + 0,866 × 1,9 ≈ "
                "**4,25%**\n"
                "  AEP migrats esperada = 0,527 × 19,4 + 0,473 × 1,9 ≈ "
                "**11,12%**\n"
                "  Gap predit: **~6,9 punts** (de 25,5 reals) → "
                "**~27% del gap**.\n"
                "  Compleix els dos criteris: (a) gran predicció (10× "
                "entre renda baixa i alta) i (b) distribució molt "
                "diferent per origen (52,7% vs 13,4%).\n\n"
                "VARIABLE 2 — Sexe: **NO CONFUSORA**.\n"
                "  AEP nadius esperada = 0,487 × 15,8 + 0,513 × 12,0 ≈ "
                "**13,85%**\n"
                "  AEP migrats esperada = 0,517 × 15,8 + 0,483 × 12,0 "
                "≈ **13,97%**\n"
                "  Gap predit: **~0,12 punts** → **<1% del gap**.\n"
                "  Compleix (a) — gap clar nois/noies de 3,8 pts — "
                "però NO (b): la distribució per sexe és gairebé "
                "idèntica entre nadius i migrats (51,7% vs 48,7%). Per "
                "ser confusora cal que la variable es distribueixi "
                "**diferent** entre els dos grups que comparem; aquí no "
                "passa. **Aquesta és la trampa pedagògica clau**: el "
                "sexe és un dels predictors més forts de l'AEP, però "
                "NO és confusora d'origen→AEP.\n\n"
                "VARIABLE 3 — Segregació escolar: **CONFUSORA "
                "MODERADA**.\n"
                "  AEP nadius esperada = 0,04 × 11,8 + 0,96 × 5,4 ≈ "
                "**5,66%**\n"
                "  AEP migrats esperada = 0,28 × 11,8 + 0,72 × 5,4 ≈ "
                "**7,19%**\n"
                "  Gap predit: **~1,5 punts** → **~6% del gap**.\n"
                "  Compleix (a) (2,2×) i (b) (7× més migrants), però "
                "amb magnituds més modestes que la renda. Per això la "
                "seva contribució al gap és menor.\n\n"
                "LLIÇÓ CENTRAL: per ser confusora calen LES DUES "
                "correlacions. La trampa del sexe ho il·lustra. Sumant "
                "les contribucions calculades (~27% + ~6% + 0% ≈ 33%), "
                "encara queda ~67% del gap sense explicar amb aquestes "
                "tres variables — pot venir d'altres confusores no "
                "calculades aquí (nivell educatiu dels pares, llengua, "
                "escolarització 0-3, discriminació institucional) o "
                "d'un eventual efecte propi de l'origen. El càlcul no "
                "ho pot distingir per si sol; el Pas 3 entrarà en "
                "aquesta qüestió."
            ),
            "typical_error": (
                "Errors típics:\n"
                "- Classificar el sexe com a confusora només perquè "
                "prediu fort l'AEP, sense comprovar el segon criteri "
                "(distribució per origen).\n"
                "- Saltar-se el càlcul i intentar respondre "
                "intuïtivament — el càlcul és precisament el que "
                "distingeix confusora real de fals predictor.\n"
                "- Confondre el '10× de la renda' (ratio entre extrems "
                "de renda) amb '10× del gap explicat' (la renda explica "
                "~27% del gap, no el 100%).\n"
                "- No saber fer mitjanes ponderades: el tutor li ha "
                "d'explicar la fórmula en una frase i tirar endavant. "
                "No és el moment d'aturar la sessió per ensenyar "
                "aritmètica de l'ESO.\n"
                "- Suposar que la suma de contribucions ha d'arribar al "
                "100% — en general no hi arriba, perquè no totes les "
                "confusores estan al càlcul i perquè la simplificació "
                "binària (renda baixa vs alta) subestima cada "
                "contribució individual."
            ),
            "typical_error_label": "CAUS_no_alternatives",
            "key_concepts": ["confounding_variable"],
            "canonical_question": (
                "Per a cada variable (renda, sexe, segregació escolar), fes "
                "la mitjana ponderada de l'AEP esperada per grup d'origen, "
                "digues quants punts del gap (25,5) explica i si és "
                "confusora. Recorda: cal complir ELS DOS criteris — predir "
                "l'AEP I distribuir-se diferent per origen."
            ),
            "pistes": [
                "Per a cada variable, calcula l'AEP esperada de nadius i de "
                "migrats com a mitjana ponderada amb les seves proporcions, "
                "i resta-les per veure quants punts del gap explica.",
                "Vigila el sexe: prediu fort l'AEP (criteri a), però es "
                "distribueix gairebé igual entre nadius i migrats (51,7% vs "
                "48,7%), així que falla el criteri b. Predir ≠ confondre.",
            ],
        },
        {
            "id": 3,
            "text": (
                "El Pas 3 es desplega en tres subapartats. Treballarem "
                "cada un per separat.\n\n"
                "── PAS 3 (context comú). ──\n\n"
                "Un estudi quasi-experimental del Centre d'Estudis "
                "Demogràfics analitza joves fills d'estrangers segons "
                "l'edat d'arribada a Catalunya. Aquestes són les "
                "taxes de no-graduació a l'ESO:\n\n"
                "  - Nascuts a Catalunya, de pares estrangers: 21,2%\n"
                "  - Arribats a Catalunya abans dels 7 anys: 21,7%\n"
                "  - Per referència, l'AEP entre joves de nacionalitat "
                "espanyola és del 10,6%.\n\n"
                "── PAS 3.a (hipòtesi causal directa). ──\n\n"
                "Si l'origen migrat fos la causa directa de "
                "l'abandonament, quina diferència esperaríem entre "
                "21,2% i 21,7%? Què en treus, doncs, de la igualtat "
                "observada?\n\n"
                "── PAS 3.b (hipòtesi de la trajectòria escolar). ──\n\n"
                "Si la trajectòria escolar dins el sistema català "
                "fos el factor decisiu, quina diferència esperaríem "
                "entre nascuts aquí (21,2%) i arribats als 6 anys "
                "(21,7%)? Què conclous de la igualtat observada?\n\n"
                "── PAS 3.c (el gap residual). ──\n\n"
                "Per què tots dos grups (21,2% i 21,7%) abandonen tant "
                "per sobre del 10,6% dels joves de nacionalitat "
                "espanyola, malgrat haver fet tota o gairebé tota la "
                "trajectòria escolar aquí?\n\n"
                "Quan tinguis resposta a les tres preguntes: quina "
                "lectura causal global en treus?"
            ),
            "expected_summary": (
                "Triple lectura del quasi-experiment del CED:\n\n"
                "1. **Si l'origen migrat fos la causa directa**, no "
                "esperaríem cap diferència entre 21,2% i 21,7% — mateix "
                "origen, mateix efecte. La igualtat 21,2 ≈ 21,7 és "
                "**consistent** amb la hipòtesi causal de l'origen "
                "(però també amb altres alternatives).\n\n"
                "2. **Si la trajectòria escolar dins el sistema català** "
                "fos el factor decisiu, esperaríem que els nascuts aquí "
                "(21,2%) tinguessin un avantatge significatiu sobre els "
                "arribats als 6 anys (21,7%) — uns anys més "
                "d'escolarització en català, integració lingüística "
                "completa, més anys dins el sistema. El fet que les "
                "taxes siguin pràcticament idèntiques **descarta** la "
                "trajectòria escolar com a factor decisiu per si sol.\n\n"
                "3. **Per què tots dos subgrups estan ~10 pts per sobre "
                "dels nadius?** Si no és l'origen (els fills nascuts "
                "aquí tenen passaport espanyol però mateix gap) ni la "
                "trajectòria (els arribats als 6 anys tenen quasi tota "
                "la vida escolar feta aquí), el factor decisiu ha de "
                "ser el **context familiar i estructural compartit** "
                "pels dos subgrups: nivell socioeconòmic dels pares, "
                "capital cultural, segregació residencial, recursos "
                "familiars, expectatives i xarxes. Aquest context és el "
                "mateix per a ambdós subgrups de fills d'estrangers, "
                "però és sistemàticament diferent del context de "
                "famílies autòctones — d'aquí el gap 21% vs 10,6%.\n\n"
                "**Conclusió causal global**: l'origen migrat per si "
                "mateix NO és la causa directa de l'abandonament. El "
                "que opera és el **context socioeconòmic i estructural** "
                "que correlaciona amb l'origen. Aquesta lectura tanca "
                "el cercle obert al Pas 1 (gap real però no "
                "necessàriament causal) i al Pas 2 (confusores reals i "
                "quantificables). L'experiment aleatoritzat és inviable "
                "(no es pot assignar l'origen); el control estadístic "
                "dels confusors i els dissenys quasi-experimentals com "
                "el del CED són la via per generar evidència causal real."
            ),
            "typical_error": (
                "Errors típics:\n"
                "- Llegir 21,2 ≈ 21,7 com a 'confirmació que l'origen "
                "causa l'abandonament', sense veure que aquesta igualtat "
                "NO discrimina entre 'l'origen causa' i 'el context "
                "familiar comú causa'.\n"
                "- No notar que tots dos subgrups estan ~10 pts per "
                "sobre dels nadius, i no preguntar-se per què — és el "
                "moll de l'os causal.\n"
                "- Tractar la igualtat 21,2 vs 21,7 com a evidència que "
                "la trajectòria escolar SÍ que importa molt "
                "(interpretació invertida).\n"
                "- Concloure que 'no es pot saber res' — el "
                "quasi-experiment SÍ que aporta evidència: descarta una "
                "hipòtesi (la trajectòria com a factor decisiu) i "
                "restringeix les alternatives consistents."
            ),
            "typical_error_label": "CAUS_direct",
            "key_concepts": ["confounding_variable"],
            "canonical_question": (
                "Amb les taxes del quasi-experiment del CED (nascuts aquí "
                "21,2%, arribats abans dels 7 anys 21,7%, nacionalitat "
                "espanyola 10,6%): què esperaríem si l'origen fos la causa "
                "directa? I si ho fos la trajectòria escolar? Per què tots "
                "dos grups superen tant el 10,6%? Quina lectura causal "
                "global en treus?"
            ),
            "pistes": [
                "Compara primer 21,2% amb 21,7%: són gairebé iguals. Què "
                "descarta aquesta igualtat — l'origen, o la trajectòria "
                "escolar dins el sistema català?",
                "Si no és ni l'origen en si ni els anys d'escola, què "
                "comparteixen els dos subgrups i els distingeix dels "
                "nadius? El context socioeconòmic i estructural de les "
                "famílies.",
            ],
        },
    ],
}


# =============================================================================
# Registry públic
# =============================================================================

PROBLEMS = {
    "IC-001": {
        "id": "IC-001",
        "title_human": "Interval de confiança",
        "problem": _IC001_PROBLEM,
        "prerequisites": _IC001_PREREQUISITES,
        "dependencies": _IC001_DEPENDENCIES,
        "error_catalog": _IC001_ERROR_CATALOG,
        "prereq_id": "PRE-PARAM",
    },
    "CAUS-001": {
        "id": "CAUS-001",
        "title_human": "Correlació vs. causalitat",
        "problem": _CAUS001_PROBLEM,
        "prerequisites": _CAUS001_PREREQUISITES,
        "dependencies": _CAUS001_DEPENDENCIES,
        "error_catalog": _CAUS001_ERROR_CATALOG,
        "prereq_id": "PRE-CONFOUNDER",
    },
}

# Problema usat per defecte quan no se n'especifica cap (tests,
# back-compat dels accessos globals). Triat CAUS-001 perquè és el
# tema afegit més recentment i fa de "default" natural a la branca
# de migració; canviar aquest valor només afecta el default, no els
# tests que demanen explícitament un problema.
DEFAULT_PROBLEM_ID = "CAUS-001"


def get(problem_id):
    """Retorna el bundle complet per a un problem_id.

    Llança KeyError amb un missatge informatiu si l'id no existeix.
    """
    if problem_id not in PROBLEMS:
        raise KeyError(
            f"Problema desconegut: {problem_id!r}. "
            f"Disponibles: {sorted(PROBLEMS)}"
        )
    return PROBLEMS[problem_id]


def list_ids():
    """Retorna [(id, title_human), ...] per construir el picker UI.

    L'ordre és el d'inserció al dict (en Python 3.7+), és a dir:
    primer IC-001, després CAUS-001.
    """
    return [(pid, bundle["title_human"]) for pid, bundle in PROBLEMS.items()]


# =============================================================================
# Accessors per a la capa determinista (Python posa preguntes i pistes)
# =============================================================================
# Aquests helpers donen a la màquina d'estats (simulator.py / app.py) accés
# directe a la pregunta canònica i a les pistes pre-escrites de cada pas,
# sense que el model les hagi de redactar. És el suport del transvasament
# Tier 1 (Python garanteix l'enunciat del pas) i Tier 3 (pistes amb control).

def _step_by_id(problem_id, step_num):
    """Retorna el dict del pas `step_num` (1-based) del problema indicat."""
    passos = PROBLEMS[problem_id]["problem"]["passos"]
    if not (1 <= step_num <= len(passos)):
        raise IndexError(
            f"Pas {step_num} fora de rang per a {problem_id} "
            f"(té {len(passos)} passos)."
        )
    return passos[step_num - 1]


def canonical_question(problem_id, step_num):
    """Pregunta canònica curta del pas `step_num` (1-based) d'un problema.

    És l'àncora determinista que Python injecta quan el tutor avança: així
    l'enunciat del pas següent sempre apareix, encara que el model no
    l'escrigui (o l'escrigui malament). Si un pas no defineix
    `canonical_question` explícitament, caiem al seu camp `text` complet.
    """
    paso = _step_by_id(problem_id, step_num)
    return paso.get("canonical_question") or paso["text"]


def step_hints(problem_id, step_num):
    """Llista de pistes progressives pre-escrites del pas (pot ser buida)."""
    return list(_step_by_id(problem_id, step_num).get("pistes", []))


def prereq_question(problem_id):
    """Pregunta canònica del prerequisit del problema (per al retrocés)."""
    bundle = PROBLEMS[problem_id]
    return bundle["prerequisites"][bundle["prereq_id"]]["question"]


# =============================================================================
# Accessors del catàleg d'errors (Tasca 4: el control block diagnostica)
# =============================================================================
# El `diagnostic` que retorna el model nomena la MALENTESA conceptual en curs
# fent servir un codi del catàleg d'errors del problema. Aquests helpers
# exposen els codis i les seves descripcions a la capa LLM (per injectar-los
# al position marker del pas actual) i al caller (per validar i normalitzar el
# codi rebut). El catàleg sempre conté `GEN_other` com a calaix de sastre.

# Codi que es retorna quan el model no diagnostica res (alumne encertant /
# acció d'avançar) o quan el codi rebut no encaixa al catàleg del pas.
GEN_OTHER = "GEN_other"


def error_catalog(problem_id):
    """Catàleg d'errors del problema: {codi: descripció}."""
    return PROBLEMS[problem_id].get("error_catalog", {})


def allowed_diagnostics(problem_id, step_num=None):
    """Codis de diagnòstic vàlids per al pas indicat (o per a tot el
    problema si step_num és None).

    Estratègia: oferim al model el catàleg sencer del problema com a opcions
    (els catàlegs són curts i els codis són transversals als passos), i a més
    destaquem el `typical_error_label` del pas actual com a candidat probable.
    Sempre s'hi inclou `GEN_other`. La validació final (codi rebut → catàleg)
    la fa el caller; aquí només enumerem el que és acceptable.

    Retorna una llista de codis (strings), amb `GEN_other` garantit al final.
    """
    catalog = error_catalog(problem_id)
    codes = [c for c in catalog.keys() if c != GEN_OTHER]
    if GEN_OTHER not in codes:
        codes.append(GEN_OTHER)
    return codes


def likely_diagnostic_for_step(problem_id, step_num):
    """`typical_error_label` del pas (codi més probable), o None si no en té
    o el pas no existeix. Pur ajut per pista/prompt; mai obligatori."""
    try:
        paso = _step_by_id(problem_id, step_num)
    except (IndexError, KeyError, TypeError):
        return None
    return paso.get("typical_error_label")


def normalize_diagnostic(problem_id, step_num, code):
    """Normalitza un codi de diagnòstic rebut del model.

    - None / "" / no-string → None (cap diagnòstic).
    - codi del catàleg del problema → es retorna tal qual.
    - codi desconegut → GEN_other (l'spec: out-of-catalog → GEN_other).

    Aquesta funció és el punt únic de validació del caller. El parser de
    llm.py es manté "ximple" i no valida contra el catàleg.
    """
    if not isinstance(code, str):
        return None
    code = code.strip()
    if not code or code.lower() == "null":
        return None
    catalog = error_catalog(problem_id)
    if code in catalog:
        return code
    return GEN_OTHER


def hint_for_diagnostic(problem_id, step_num, code):
    """Pista mapejada a un codi de diagnòstic, si el pas en defineix via
    `pistes_per_error: {codi: pista}`. Si no n'hi ha cap per al codi, retorna
    None i el caller cau a la pista per defecte (`step_hints(...)[0]`)."""
    if not code:
        return None
    try:
        paso = _step_by_id(problem_id, step_num)
    except (IndexError, KeyError, TypeError):
        return None
    mapping = paso.get("pistes_per_error") or {}
    return mapping.get(code)


# =============================================================================
# Back-compat: noms globals apuntant al problema per defecte
# =============================================================================
# Codi antic que accedeix directament a PB.PROBLEM (per exemple, tests
# heretats) continua funcionant sense canvis. Codi nou hauria d'usar
# PB.get(problem_id) per ser explícit sobre quin problema treballa.

PROBLEM = PROBLEMS[DEFAULT_PROBLEM_ID]["problem"]
PREREQUISITES = PROBLEMS[DEFAULT_PROBLEM_ID]["prerequisites"]
DEPENDENCIES = PROBLEMS[DEFAULT_PROBLEM_ID]["dependencies"]
ERROR_CATALOG = PROBLEMS[DEFAULT_PROBLEM_ID]["error_catalog"]


# =============================================================================
# Validació d'invariants al càrrega del mòdul
# =============================================================================
# Aquestes comprovacions detecten errors a la base de dades pedagògica
# tan aviat com s'importa el mòdul, en comptes de fallar a runtime
# enmig d'una sessió. Si fallen, és que algú ha trencat l'esquema en
# editar un problema.

for _pid, _bundle in PROBLEMS.items():
    assert _bundle["id"] == _pid, f"Mismatch id/clau a {_pid}"
    assert len(_bundle["problem"]["passos"]) == 3, (
        f"{_pid} ha de tenir exactament 3 passos (té {len(_bundle['problem']['passos'])})"
    )
    assert _bundle["prereq_id"] in _bundle["prerequisites"], (
        f"prereq_id {_bundle['prereq_id']} no existeix a prerequisites de {_pid}"
    )
    _dep_keys = list(_bundle["dependencies"].keys())
    assert _bundle["problem"]["dependencies"] == _dep_keys[:len(_bundle["problem"]["dependencies"])], (
        f"problem['dependencies'] no coincideix amb DEPENDENCIES a {_pid}"
    )
    for _paso in _bundle["problem"]["passos"]:
        assert _paso["typical_error_label"] in _bundle["error_catalog"], (
            f"typical_error_label {_paso['typical_error_label']} de {_pid} "
            f"no existeix a ERROR_CATALOG"
        )
        for _kc in _paso["key_concepts"]:
            assert _kc in _bundle["dependencies"], (
                f"key_concept {_kc} de {_pid} no existeix a DEPENDENCIES"
            )

del _pid, _bundle, _dep_keys, _paso, _kc
