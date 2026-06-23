"""
Tutor — base de dades pedagògica.

Un problema disponible: IC-001 (interval de confiança). L'alumne el
treballa des de l'inici de la sessió.

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
(IC-001) per back-compat. Codi nou hauria d'usar PB.get(problem_id).
"""

# =============================================================================
# IC-001 — Construcció i disseny d'un interval de confiança
# =============================================================================
# Tema: NO la (re)interpretació freqüentista del 95%, sinó COM es construeix
# l'interval (error estàndard, mida de mostra), el biaix de selecció de la
# mostra, i la tria del nivell de confiança. Vegeu el document de disseny.

_IC001_ERROR_CATALOG = {
    "CONSTR_s_vs_se": (
        "Confon la dispersió de les DADES (s, com de diferents són els "
        "individus entre ells) amb la precisió de l'ESTIMACIÓ (l'error "
        "estàndard s/√n, com de precisa és la mitjana mostral). Espera "
        "un marge de l'ordre de s, sense veure la divisió per √n."
    ),
    "CONSTR_critic_magic": (
        "Tracta el valor crític com un 1,96 fix i universal, sense veure "
        "que surt d'una distribució (t de Student amb n−1 g.ll. quan "
        "estimem σ amb s) i que depèn de n i del nivell de confiança."
    ),
    "BIAS_n_no_corregeix": (
        "Creu que augmentar la mida de la mostra corregeix el biaix de "
        "selecció. No veu que n redueix l'AMPLADA (via s/√n) però mai el "
        "BIAIX (el desplaçament del centre): una mostra esbiaixada gran "
        "és igual de descentrada, només amb més falsa seguretat."
    ),
    "CONF_mes_sempre_millor": (
        "Creu que més confiança és sempre millor (99,9% > 95%), sense "
        "veure el cost: pujar la confiança eixampla l'interval i el fa "
        "menys informatiu. No percep el trade-off fiabilitat ↔ utilitat."
    ),
    "KEY_only": (
        "Resposta-keyword: conté un terme correcte (error estàndard, "
        "arrel de n, biaix, representativa, confiança, marge...) però no "
        "el justifica ni l'aplica a la pregunta concreta. Cal desenvolupar "
        "el raonament: explicar QUÈ vol dir el terme en aquest context "
        "i PER QUÈ respon la pregunta."
    ),
    "GEN_other": "Error no catalogat.",
}

_IC001_DEPENDENCIES = {
    "error_estandard": {
        "description": (
            "L'error estàndard de la mitjana és s/√n: mesura la dispersió "
            "de la mitjana mostral (com de precisa és l'estimació), i és "
            "diferent de s (la dispersió de les dades). És el concepte que "
            "explica per què l'interval és estret tot i que les dades són "
            "disperses, i per què la n entra sota una arrel."
        ),
        "keywords": ["error estàndard", "error estandard", "s/√n", "arrel",
                     "arrel de n", "√n", "dividir per", "precisió",
                     "precisio", "estabilitat de la mitjana"],
        "prerequisite": "PRE-SE",
    },
}

_IC001_PREREQUISITES = {
    "PRE-SE": {
        "id": "PRE-SE",
        "concept": "error_estandard",
        "question": (
            "Abans de seguir, aclarim una peça clau. Tens dues quantitats: "
            "s = 1,6 h, que diu com de diferents són els adolescents entre "
            "ells, i s/√n, que diu com de precisa és la mitjana de la "
            "mostra. Per què la mitjana de 100 persones és molt més estable "
            "(varia molt menys) que una sola persona? I què hi pinta el √n?"
        ),
        "keywords_required": ["arrel", "√n", "dividir", "mitjana",
                              "precis", "estable", "compensen",
                              "error estàndard", "error estandard"],
        "forbidden_keywords": [],
        "explanation": (
            """**Hi ha dues dispersions diferents, i confondre-les és l'error clàssic:**

- **s ≈ 1,6 h** és la dispersió de les **dades**: com de diferents són els adolescents entre ells (n'hi ha de 5 h i de 9 h).
- **s/√n ≈ 0,16 h** és l'**error estàndard**: la dispersió de la **mitjana mostral**, és a dir, com de precisa és l'estimació.

Quan fas la mitjana de 100 persones, els valors alts i baixos es **compensen** parcialment: la mitjana resultant és molt més estable que un individu sol. Quant més estable? La dispersió cau amb **√n**, no amb n. Per això l'interval és estret (±0,32 h) tot i que les dades són molt disperses (s = 1,6 h).

Conseqüència pràctica: per reduir el marge a la meitat cal **quadruplicar** la mostra (perquè √4 = 2), no doblar-la."""
        ),
    },
}

_IC001_PROBLEM = {
    "id": "IC-001",
    "tema": "Construcció d'un interval de confiança: error estàndard, biaix i nivell de confiança",
    "enunciat": (
        """Un equip de salut pública vol estimar quantes hores dormen, de mitjana, els adolescents de 14 a 16 anys escolaritzats en un institut de la ciutat, les **nits de diari** (de diumenge a dijous, amb institut l'endemà). No existeix cap registre d'aquesta dada: cal preguntar-ho a una mostra. Per no barrejar hàbits diferents, les nits de divendres i dissabte queden **fora** de l'estudi.

Es pregunta a una **mostra aleatòria de n = 100 adolescents** quantes hores van dormir la nit anterior. S'obté:
  - Mitjana mostral: x̄ = 6,8 hores
  - Desviació mostral: s = 1,6 hores (molta variabilitat: força alumnes dormen ~5 h, però encara n'hi ha que arriben a 8–9 h)

Com que la desviació poblacional σ NO es coneix (s'ha estimat amb la pròpia mostra), l'interval es construeix amb la distribució t de Student amb n−1 = 99 graus de llibertat. S'obté un interval de confiança del 95% per a la mitjana poblacional μ:

  [6,48 ; 7,12] hores"""
    ),
    "dependencies": ["error_estandard"],
    "passos": [
        {
            "id": 1,
            "text": (
                """L'interval és [6,48 ; 7,12], centrat en x̄ = 6,8 amb un marge de només ±0,32 h (uns 19 minuts). Però els adolescents dormen de manera molt diversa: la desviació de les dades és s = 1,6 h. Com pot ser que el marge sigui tan petit comparat amb com de diferents són els uns dels altres? D'on surt aquest ±0,32, i d'on surt el número que multiplica?"""
            ),
            "expected_summary": (
                "El marge és (valor crític) · (s/√n). Depèn de l'error "
                "estàndard s/√n (la dispersió de la MITJANA, no la de les "
                "dades): la mitjana de 100 és molt més estable que un "
                "individu, per això ±0,32 i no ±1,6. La n entra sota arrel "
                "(reduir el marge a la meitat exigeix ×4 la mostra). I el "
                "valor crític (≈1,984) surt de la taula t amb 99 g.ll., NO "
                "és un 1,96 màgic: és la t perquè hem estimat σ amb s."
            ),
            "typical_error": (
                "Confondre la dispersió de les dades (s = 1,6) amb la "
                "precisió de l'estimació (s/√n = 0,16) i esperar un marge "
                "de l'ordre d'1,6; o creure que el valor crític és sempre "
                "1,96 sense veure que surt d'una distribució t."
            ),
            "typical_error_label": "CONSTR_s_vs_se",
            "key_concepts": ["error_estandard"],
            "canonical_question": (
                """Mirant l'interval [6,48 ; 7,12] amb marge ±0,32 h: com és que el marge és tan petit si la desviació de les dades és s = 1,6 h? D'on surt el ±0,32 i d'on surt el número que multiplica l'error estàndard?"""
            ),
            "pistes": [
                """Separa dues coses: s = 1,6 h diu com de diferents són els adolescents entre ells; el marge depèn de com de precisa és la MITJANA de 100 persones, que és molt més estable. Quina operació converteix s en aquesta precisió?""",
                "El marge = (valor crític) · (s/√n). El s/√n = 1,6/10 = 0,16 "
                "és l'error estàndard. I el número que multiplica (≈1,984) "
                "no és un 1,96 fix: surt de la taula t amb 99 graus de "
                "llibertat, justament perquè σ l'hem estimada amb s.",
            ],
            "pistes_per_error": {
                "CONSTR_s_vs_se": (
                    "Fixa't: s = 1,6 h és la dispersió de les DADES (un "
                    "individu qualsevol pot allunyar-se molt de 6,8). Però "
                    "l'interval parla de la MITJANA de 100, que és molt més "
                    "estable. Què fas amb s i amb n per passar d'una a l'altra?"
                ),
                "CONSTR_critic_magic": (
                    "El número que multiplica no és sempre 1,96. Com que no "
                    "coneixem σ i l'estimem amb s, el crític surt de la "
                    "distribució t de Student amb n−1 graus de llibertat. "
                    "Per a n = 100 val ≈1,984. Per a n petita creix molt."
                ),
            },
        },
        {
            "id": 2,
            "text": (
                """Tot el càlcul assumeix que els 100 adolescents són una mostra aleatòria de tota la ciutat. Imagina que, en realitat, l'enquesta es va passar a les 8 del matí, a l'entrada de l'institut: just els qui es van quedar despierts fins tardíssim potser no han vingut o han arribat tard, i no entren a la mostra. L'interval [6,48 ; 7,12] seguiria sent de fiar? I si, en lloc de 100, n'haguéssim enquestat 5.000 a la mateixa porta i a la mateixa hora, quedaria arreglat?"""
            ),
            "expected_summary": (
                "La fórmula assumeix que la mostra representa la població. "
                "Si el mètode de mostreig deixa fora un subgrup sencer (els "
                "qui dormen poc i no arriben a l'hora), x̄ deixa d'estimar μ "
                "sense biaix: l'interval pot ser PRECÍS però DESCENTRAT — "
                "estret i al lloc equivocat. Augmentar n estreny l'interval "
                "(via s/√n) però NO toca el centre: una mostra esbiaixada de "
                "5.000 està igual de mal centrada que una de 100, només amb "
                "més falsa seguretat. n ataca la variància, mai el biaix."
            ),
            "typical_error": (
                "Creure que augmentar la mostra (5.000 en lloc de 100) "
                "arregla el biaix de selecció, confonent una mostra GRAN "
                "amb una mostra ALEATÒRIA/representativa."
            ),
            "typical_error_label": "BIAS_n_no_corregeix",
            "key_concepts": ["error_estandard"],
            "canonical_question": (
                """Si l'enquesta es passa només a l'entrada de l'institut a les 8 del matí (i els qui van dormir poc no hi són), l'interval [6,48 ; 7,12] és de fiar? Augmentar la mostra a 5.000 al mateix lloc i hora ho arreglaria?"""
            ),
            "pistes": [
                "Pregunta't qui queda FORA de la mostra amb aquest mètode, i "
                "si els qui queden fora dormen diferent dels qui hi entren. "
                "Si falten sistemàticament els qui dormen poc, cap a on es "
                "desplaça la mitjana observada?",
                "Distingeix dues coses que la n NO afecta igual: l'AMPLADA "
                "de l'interval (s/√n, que sí baixa amb més mostra) i el "
                "CENTRE (que el biaix desplaça). Amb 5.000 enquestats al "
                "mateix lloc, l'interval s'estreny... però segueix centrat "
                "on? El biaix es queda.",
            ],
            "pistes_per_error": {
                "BIAS_n_no_corregeix": (
                    "Pensa-ho amb els extrems: amb 5.000 enquestats a la "
                    "mateixa porta el matí, l'interval es fa estretíssim. "
                    "Però si els tardans segueixen sense aparèixer-hi, el "
                    "centre no s'ha mogut: tens un interval molt precís "
                    "al voltant del valor equivocat. La n redueix la "
                    "variància, no el biaix."
                ),
            },
        },
        {
            "id": 3,
            "text": (
                """Hem treballat amb un 95% de confiança i ha sortit un marge de ±0,32 h. Si l'equip hagués volgut estar molt més segur —diguem un 99,9%— què li hauria passat a l'amplada de l'interval [6,48 ; 7,12]? I per què, llavors, no demanem sempre el 99,9%, o fins i tot el 99,99%?"""
            ),
            "expected_summary": (
                "El nivell de confiança és una ELECCIÓ, no una constant. "
                "Marge = (valor crític) · (error estàndard); pujar la "
                "confiança puja el valor crític (de ≈1,984 a ≈3,392) i per "
                "tant EIXAMPLA el marge (de ±0,32 a ±0,54). Hi ha un "
                "trade-off: més confiança = més seguretat de capturar μ a la "
                "llarga, però interval més ample i menys informatiu. El 95% "
                "és convenció, un equilibri habitual entre fiabilitat i "
                "utilitat; no hi ha un nivell 'correcte'."
            ),
            "typical_error": (
                "Creure que més confiança és sempre millor ('posem 99,99% i "
                "som més rigorosos') sense veure que l'interval es fa tan "
                "ample que deixa de ser informatiu."
            ),
            "typical_error_label": "CONF_mes_sempre_millor",
            "key_concepts": ["error_estandard"],
            "canonical_question": (
                """Si en lloc del 95% l'equip hagués demanat un 99,9% de confiança, què li passaria a l'amplada de l'interval? I per què no demanem sempre el màxim de confiança possible?"""
            ),
            "pistes": [
                "El marge té dos factors: el valor crític i l'error "
                "estàndard. L'error estàndard (s/√n) no canvia si només "
                "toques la confiança. Quin dels dos factors mou, doncs, el "
                "nivell de confiança, i en quina direcció?",
                "Porta-ho a l'extrem: amb 99,99% el crític creix tant que "
                "l'interval s'eixampla cap a gairebé [6,4 ; 8,0]. Un interval "
                "tan ample, encara distingeix un bon dormidor d'un de dolent? "
                "Aquí és on apareix el preu de la confiança.",
            ],
            "pistes_per_error": {
                "CONF_mes_sempre_millor": (
                    "Més confiança no és gratis. Puja el valor crític "
                    "(1,984 → 3,392 → més encara), i això eixampla "
                    "l'interval. Al límit, un interval del 99,99% és tan "
                    "ample que ja no informa de res útil: capturaria μ quasi "
                    "sempre, però sense dir-te on és. Per això 95% és un "
                    "compromís, no una veritat."
                ),
            },
        },
    ],
}


# =============================================================================
# IC-002 — Interval de confiança per a una PROPORCIÓ
# =============================================================================
# Tema germà d'IC-001 però amb una arquitectura conceptual diferent: aquí no
# estimem la mitjana d'una variable contínua, sinó la PROPORCIÓ p d'una
# població que compleix una condició binària (dormir < 7 h). Idees pròpies:
#   - variable Bernoulli (sí/no), no una mesura contínua;
#   - la variància NO és lliure: està lligada a p, val p(1-p) (màxima a 0,5);
#   - per això NO cal una "s" externa, i tornem a la z (no a la t);
#   - el sostre natural [0, 1] fa que l'absurd sigui OMPLIR tot l'espai
#     possible ([1%, 99%] = no dir res), no sortir-se'n.

_IC002_ERROR_CATALOG = {
    "PROP_se_lliure": (
        "No veu que la variància d'una proporció està LLIGADA a p "
        "(val p(1-p)) i busca una desviació estàndard externa, com si "
        "calgués mesurar-la a part igual que amb una variable contínua. "
        "No reconeix que el percentatge ja conté la seva pròpia dispersió."
    ),
    "PROP_var_max_50": (
        "No percep que la incertesa (la variància p(1-p)) és MÀXIMA quan "
        "p ronda el 50% i mínima als extrems: creu que la precisió no "
        "depèn de quin sigui el percentatge estimat."
    ),
    "BIAS_n_no_corregeix": (
        "Creu que augmentar la mida de la mostra corregeix el biaix de "
        "selecció. No veu que n redueix l'AMPLADA (via √(p(1-p)/n)) però "
        "mai el BIAIX (el desplaçament del centre): una mostra esbiaixada "
        "gran és igual de descentrada, només amb més falsa seguretat."
    ),
    "CONF_mes_sempre_millor": (
        "Creu que més confiança és sempre millor (99,99% > 95%), sense "
        "veure el cost: pujar la confiança eixampla l'interval fins a "
        "omplir tot el rang [0%, 100%] i el fa vàcuament cert i inútil."
    ),
    "KEY_only": (
        "Resposta-keyword: conté un terme correcte (proporció, p(1-p), "
        "error estàndard, arrel de n, biaix, confiança...) però no el "
        "justifica ni l'aplica a la pregunta concreta. Cal desenvolupar "
        "el raonament: explicar QUÈ vol dir el terme en aquest context "
        "i PER QUÈ respon la pregunta."
    ),
    "GEN_other": "Error no catalogat.",
}

_IC002_DEPENDENCIES = {
    "var_proporcio": {
        "description": (
            "La variància d'una proporció està lligada a la pròpia p: "
            "val p(1-p), i és màxima a p=0,5. L'error estàndard de la "
            "proporció mostral és √(p(1-p)/n), de manera que no cal una "
            "desviació estàndard mesurada a part: el percentatge conté "
            "la seva pròpia dispersió. Per això s'usa la z (no la t)."
        ),
        "keywords": ["p(1-p)", "p (1-p)", "bernoulli", "binària", "binaria",
                     "sí/no", "si/no", "proporció", "proporcio",
                     "arrel", "√", "dividir per", "lligada", "màxima",
                     "maxima", "50%", "0,5", "0.5"],
        "prerequisite": "PRE-VARP",
    },
}

_IC002_PREREQUISITES = {
    "PRE-VARP": {
        "id": "PRE-VARP",
        "concept": "var_proporcio",
        "question": (
            "Abans de seguir, aclarim una peça clau d'aquest problema. "
            "Quan estimem un percentatge (una proporció p), la "
            "incertesa no és la mateixa per a tots els valors de p: és "
            "MÀXIMA quan p ronda el 50% i mínima quan p s'acosta al 0% o "
            "al 100%. Per què? Pensa en l'expressió p(1-p): on és més "
            "gran, i què vol dir això sobre com de segurs estem segons "
            "el percentatge estimat?"
        ),
        "keywords_required": ["p(1-p)", "p (1-p)", "màxima", "maxima",
                              "50", "0,5", "0.5", "meitat", "extrems",
                              "variància", "variancia", "dispersió",
                              "dispersio"],
        "forbidden_keywords": [],
        "explanation": (
            """**La variància d'una proporció no és lliure: està lligada a la pròpia p.**

Per a una variable sí/no (Bernoulli), la variància de cada observació val exactament **p(1-p)**. Aquesta expressió:

- val **0** als extrems (p=0 o p=1): si tothom respon igual, no hi ha cap dispersió;
- és **màxima a p=0,5** (val 0,25): quan la població està partida per la meitat, és quan hi ha més incertesa.

Conseqüència 1: l'error estàndard de la proporció és **√(p(1-p)/n)** — i no cal mesurar cap desviació estàndard a part, perquè el percentatge ja conté la seva pròpia dispersió.

Conseqüència 2: com que no estimem cap σ amb una mostra a part, **tornem a la z** (1,96 per al 95%), no a la t de Student."""
        ),
    },
}

_IC002_PROBLEM = {
    "id": "IC-002",
    "tema": "Interval de confiança per a una proporció: variància lligada a p, biaix i nivell de confiança",
    "enunciat": (
        """El mateix equip de salut pública vol estimar ara quin PERCENTATGE dels adolescents de 14 a 16 anys escolaritzats a la ciutat dorm estrictament menys de 7 hores les nits de diari (de diumenge a dijous). En lloc de mesurar quantes hores dorm cadascú, només es registra una resposta sí/no: «dorms menys de 7 hores?».

D'una mostra aleatòria de n = 100 adolescents, 45 responen que sí. La proporció mostral és, doncs:
  - p̂ = 45/100 = 0,45 (un 45%)

Aquí la variància no s'estima a part: per a una variable sí/no, la dispersió ja ve donada per p(1-p). L'error estàndard és √(p̂(1−p̂)/n), i com que no estimem cap σ externa, s'usa la distribució normal (z = 1,96 per al 95%). S'obté un interval de confiança del 95% per a la proporció poblacional p:

  [0,352 ; 0,548] = [35,2% ; 54,8%]"""
    ),
    "dependencies": ["var_proporcio"],
    "passos": [
        {
            "id": 1,
            "text": (
                """L'interval és [35,2% ; 54,8%], centrat en p̂ = 45% amb un marge de ±9,8 punts. Però fixa't en una cosa curiosa: aquí no hem mesurat cap desviació estàndard de les dades, com fèiem amb les hores. D'on surt, doncs, la dispersió que entra al marge? I per què, si el percentatge hagués sortit del 90% en lloc del 45%, el marge seria més petit?"""
            ),
            "expected_summary": (
                "Per a una variable sí/no, la variància no és lliure: està "
                "LLIGADA a p i val p(1-p). Per això no cal mesurar cap "
                "desviació estàndard a part — el percentatge ja conté la "
                "seva pròpia dispersió. L'error estàndard és √(p̂(1−p̂)/n). "
                "I com que p(1-p) és MÀXIMA a 0,5 i petita als extrems, un "
                "p̂ del 90% (proper a l'extrem) dona menys variància i per "
                "tant marge més petit que un p̂ del 45% (proper a la meitat)."
            ),
            "typical_error": (
                "Buscar una desviació estàndard externa com si calgués "
                "mesurar-la a part (com amb les hores), sense veure que la "
                "variància d'una proporció ja surt de p(1-p); o creure que "
                "la precisió no depèn de quin sigui el percentatge."
            ),
            "typical_error_label": "PROP_se_lliure",
            "key_concepts": ["var_proporcio"],
            "canonical_question": (
                """Si aquí no mesurem cap desviació estàndard de les dades, d'on surt la dispersió que entra al marge ±9,8 punts? I per què amb un p̂ del 90% el marge seria més petit que amb el 45%?"""
            ),
            "pistes": [
                """Per a una variable sí/no no hi ha una 's' que mesurar a part: la dispersió surt sola de la pròpia proporció. Quina expressió, feta només amb p, fa de variància? Mira on és més gran: a p=0,5 o als extrems?""",
                "L'error estàndard d'una proporció és √(p(1-p)/n). El factor "
                "p(1-p) val 0,25 a p=0,5 (màxim) i baixa cap a 0 als "
                "extrems. Per això un p̂ del 90% té menys variància (0,09) "
                "que un del 45% (≈0,25): marge més petit.",
            ],
            "pistes_per_error": {
                "PROP_se_lliure": (
                    "No busquis una desviació mesurada a part: amb una "
                    "variable sí/no, la variància ja ve determinada per la "
                    "proporció. Quant val la variància d'una Bernoulli en "
                    "funció de p? És l'expressió p(1-p)."
                ),
                "PROP_var_max_50": (
                    "La precisió SÍ depèn del percentatge. Calcula p(1-p) "
                    "per a p=0,5 i per a p=0,9: 0,25 contra 0,09. Com més "
                    "a prop del 50%, més incertesa; com més a l'extrem, "
                    "menys."
                ),
            },
        },
        {
            "id": 2,
            "text": (
                """Tot el càlcul assumeix que els 100 adolescents són una mostra aleatòria de tota la ciutat. Imagina que, en realitat, l'enquesta es va passar a les 8 del matí a l'entrada de l'institut: just els qui es van quedar despierts fins tardíssim potser no han vingut o han arribat tard, i no entren a la mostra. El percentatge estimat (45%) seria de fiar? I si, en lloc de 100, n'haguéssim enquestat 5.000 a la mateixa porta i a la mateixa hora, quedaria arreglat?"""
            ),
            "expected_summary": (
                "La fórmula assumeix que la mostra representa la població. "
                "Si el mètode de mostreig deixa fora un subgrup sencer "
                "(precisament els qui dormen poc, que són els que ens "
                "interessa comptar!), p̂ deixa d'estimar p sense biaix: el "
                "percentatge surt esbiaixat cap avall (n'hem perdut justament "
                "dels qui dormen <7h). L'interval pot ser PRECÍS però "
                "DESCENTRAT. Augmentar n a 5.000 estreny l'interval (via "
                "√(p(1-p)/n)) però NO toca el centre: una mostra esbiaixada "
                "gran és igual de descentrada, només amb més falsa seguretat. "
                "n ataca la variància, mai el biaix."
            ),
            "typical_error": (
                "Creure que augmentar la mostra (5.000 en lloc de 100) "
                "arregla el biaix de selecció, confonent una mostra GRAN "
                "amb una mostra ALEATÒRIA/representativa."
            ),
            "typical_error_label": "BIAS_n_no_corregeix",
            "key_concepts": ["var_proporcio"],
            "canonical_question": (
                """Si l'enquesta es passa només a l'entrada de l'institut a les 8 del matí (i els qui van dormir poc no hi són), el 45% és de fiar? Augmentar la mostra a 5.000 al mateix lloc i hora ho arreglaria?"""
            ),
            "pistes": [
                "Pregunta't qui queda FORA de la mostra amb aquest mètode. "
                "Justament els qui dormen poc (els que no arriben a l'hora) "
                "són els que compten per al «sí». Si en falten "
                "sistemàticament, el percentatge observat va cap amunt o cap "
                "avall?",
                "Distingeix dues coses que la n NO afecta igual: l'AMPLADA "
                "de l'interval (√(p(1-p)/n), que sí baixa amb més mostra) i "
                "el CENTRE (que el biaix desplaça). Amb 5.000 al mateix lloc, "
                "l'interval s'estreny... però segueix centrat al percentatge "
                "equivocat. El biaix es queda.",
            ],
            "pistes_per_error": {
                "BIAS_n_no_corregeix": (
                    "Pensa-ho amb els extrems: amb 5.000 enquestats a la "
                    "mateixa porta el matí, l'interval es fa estretíssim. "
                    "Però si els qui dormen poc segueixen sense aparèixer-hi, "
                    "el percentatge no s'ha mogut del valor esbiaixat: tens "
                    "un interval molt precís al voltant del número equivocat. "
                    "La n redueix la variància, no el biaix."
                ),
            },
        },
        {
            "id": 3,
            "text": (
                """Hem treballat amb un 95% de confiança i ha sortit [35,2% ; 54,8%]. Si l'equip hagués volgut estar moltíssim més segur —diguem un 99,99%— què li passaria a l'amplada de l'interval? I si, a més, la mostra hagués estat ridícula (per exemple 4 persones), fins on podria arribar l'interval? Per què, llavors, no demanem sempre el màxim de confiança?"""
            ),
            "expected_summary": (
                "El nivell de confiança és una ELECCIÓ. Marge = z·√(p(1-p)/n); "
                "pujar la confiança puja z (1,96 → 3,89 per al 99,99%) i "
                "eixampla el marge. Amb mostra ridícula (n=4) i/o confiança "
                "absurda, l'interval pot omplir gairebé tot el rang possible "
                "[0%, 100%], p. ex. [1% ; 99%]: és vàcuament cert (cap valor "
                "és impossible) però NO DIU RES. Aquí el sostre natural [0,1] "
                "fa l'absurd especialment clar: no et surts de cap límit, "
                "només omples tot l'espai. El 95% és un compromís entre "
                "fiabilitat i utilitat, no una veritat."
            ),
            "typical_error": (
                "Creure que més confiança és sempre millor ('posem 99,99% i "
                "som més rigorosos') sense veure que l'interval s'eixampla "
                "fins a [1%, 99%], que és com no dir res."
            ),
            "typical_error_label": "CONF_mes_sempre_millor",
            "key_concepts": ["var_proporcio"],
            "canonical_question": (
                """Si en lloc del 95% es demana un 99,99% de confiança (o si la mostra és de només 4 persones), què li passa a l'amplada de l'interval? Per què no demanem sempre el màxim de confiança?"""
            ),
            "pistes": [
                "El marge és z·√(p(1-p)/n). El factor √(p(1-p)/n) no canvia "
                "si només toques la confiança; el que mou la confiança és z "
                "(1,96 → 2,58 → 3,89...). En quina direcció va el marge?",
                "Porta-ho a l'extrem que tu intuïes: amb 4 persones (o amb "
                "99,99% de confiança), el marge es dispara i l'interval "
                "s'acosta a [1% ; 99%]. Com que una proporció viu entre 0% i "
                "100%, no et surts de res: simplement omples tot l'espai "
                "possible. L'interval és cert però inútil. Aquí és on es veu "
                "el preu de la confiança.",
            ],
            "pistes_per_error": {
                "CONF_mes_sempre_millor": (
                    "Més confiança no és gratis. Puja z i això eixampla "
                    "l'interval. Al límit, un interval del 99,99% (o amb "
                    "mostra ridícula) s'estira fins a [1%, 99%]: capturaria "
                    "p quasi sempre, però sense dir-te on és. Per això 95% "
                    "és un compromís, no una veritat."
                ),
            },
        },
    ],
}


# =============================================================================
# Registry públic
# =============================================================================

PROBLEMS = {
    "IC-001": {
        "id": "IC-001",
        "title_human": "Interval de confiança (mitjana)",
        "problem": _IC001_PROBLEM,
        "prerequisites": _IC001_PREREQUISITES,
        "dependencies": _IC001_DEPENDENCIES,
        "error_catalog": _IC001_ERROR_CATALOG,
        "prereq_id": "PRE-SE",
    },
    "IC-002": {
        "id": "IC-002",
        "title_human": "Interval de confiança (proporció)",
        "problem": _IC002_PROBLEM,
        "prerequisites": _IC002_PREREQUISITES,
        "dependencies": _IC002_DEPENDENCIES,
        "error_catalog": _IC002_ERROR_CATALOG,
        "prereq_id": "PRE-VARP",
    },
}

# Problema usat per defecte quan no se n'especifica cap (tests,
# back-compat dels accessos globals). Ara IC-001 és l'únic problema
# disponible i, per tant, el default; canviar aquest valor només
# afecta el default, no els tests que demanen explícitament un problema.
DEFAULT_PROBLEM_ID = "IC-001"


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

    L'ordre és el d'inserció al dict (en Python 3.7+). Actualment
    només hi ha IC-001.
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
