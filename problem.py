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
            "**μ és un paràmetre poblacional**: un nombre fix, "
            "desconegut, però **no aleatori**. "
            "**x̄ és un estadístic mostral**: varia d'una mostra a una "
            "altra, és **aleatori**. "
            "La inferència freqüentista fa afirmacions probabilístiques "
            "sobre x̄ (i intervals construïts a partir de x̄), no sobre μ."
        ),
    },
}

_IC001_PROBLEM = {
    "id": "IC-001",
    "tema": "Interpretació d'un interval de confiança",
    "enunciat": (
        "Has calculat un interval de confiança del 95% per a la mitjana μ "
        "d'una població. El resultat és **[3,2 ; 4,8]**. "
        "Anem a interpretar aquest interval pas a pas."
    ),
    "dependencies": ["param_vs_stat"],
    "passos": [
        {
            "id": 1,
            "text": (
                "Aquest '95%' que apareix al nivell de confiança "
                "es refereix a una probabilitat. "
                "Probabilitat **sobre què**, exactament?"
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
        },
        {
            "id": 2,
            "text": (
                "Imagina que un company et diu: «la probabilitat que μ "
                "estigui entre 3,2 i 4,8 és del 95%». "
                "**Per què aquesta frase és incorrecta?**"
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
        },
        {
            "id": 3,
            "text": (
                "Per acabar: dona ara **una interpretació correcta** "
                "de l'interval [3,2 ; 4,8]."
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
            "En un poble de la costa observem que, dia a dia, les "
            "**hores de sol** i les **vendes de begudes fredes** estan "
            "fortament correlacionades (r = 0,85). Podem dir que tenir "
            "més hores de sol **causa** que la gent compri més begudes "
            "fredes? Què podria explicar millor per què les dues "
            "variables pugen alhora?"
        ),
        "keywords_required": [
            "confus", "tercera", "amagada", "oculta", "comuna",
            "calor", "temperatura", "estiu", "estival", "fa calor",
            "afecta totes dues", "afecta les dues",
            "afecta a totes dues", "afecta a les dues",
        ],
        "forbidden_keywords": [],
        "explanation": (
            "Una **variable confusora** és una tercera variable que causa "
            "alhora les dues variables observades, produint una associació "
            "entre elles sense que cap de les dues causi l'altra. En aquest "
            "exemple, la **calor** (o, més en general, el fet que sigui un "
            "dia d'estiu) causa alhora moltes hores de sol i moltes vendes "
            "de begudes fredes. El sol i les begudes fredes no estan en una "
            "relació causal directa: tots dos són efectes de la mateixa "
            "causa subjacent. Aquesta és la raó fonamental per la qual una "
            "correlació observada, per alta que sigui, no permet inferir "
            "causalitat: sempre podem estar veient l'ombra d'una variable "
            "confusora que no hem mesurat."
        ),
    },
}

_CAUS001_PROBLEM = {
    "id": "CAUS-001",
    "tema": "Interpretació d'una correlació observada — correlació vs. causalitat",
    "enunciat": (
        "Segons dades de l'**Idescat** (Enquesta de Població Activa, "
        "2022-2023), a Catalunya la **taxa d'abandonament escolar "
        "prematur** entre joves de 18 a 24 anys és d'un **34,2%** "
        "entre joves de nacionalitat estrangera i d'un **10,1%** "
        "entre joves nascuts a Catalunya. La taxa és, doncs, més de "
        "tres vegades superior entre l'alumnat d'origen migrat. "
        "Anem a interpretar aquesta diferència pas a pas."
    ),
    "dependencies": ["confounding_variable"],
    "passos": [
        {
            "id": 1,
            "text": (
                "Davant d'aquesta diferència de taxes — **34,2% vs "
                "10,1%** —, podem concloure que **ser d'origen migrat "
                "causa que aquests joves abandonin més els estudis**? "
                "Per què no?"
            ),
            "expected_summary": (
                "La diferència de taxes mesura una associació estadística "
                "observada a la població, no un mecanisme causal. Que dos "
                "grups tinguin resultats sistemàticament diferents en una "
                "variable no diu res sobre què causa aquesta diferència. "
                "Quan els dos grups que comparem difereixen també en moltes "
                "altres variables que afecten l'outcome (nivell socioeconòmic, "
                "educació dels pares, recursos escolars, llengua...), la "
                "diferència observada pot venir d'aquestes altres variables "
                "i no de l'origen mateix. Per afirmar 'X causa Y' calen "
                "arguments més enllà de la comparació crua entre grups."
            ),
            "typical_error": (
                "Acceptar la lectura causal directa ('l'origen migrat fa "
                "abandonar més els estudis', 'la immigració causa fracàs "
                "escolar') com si la diferència de taxes la confirmés. No "
                "distingeix entre que dos grups tinguin resultats diferents "
                "i que la pertinença a un grup causi aquests resultats."
            ),
            "typical_error_label": "CAUS_direct",
            "key_concepts": ["confounding_variable"],
        },
        {
            "id": 2,
            "text": (
                "Si no podem inferir causalitat només de la diferència de "
                "taxes, **quines explicacions alternatives** a 'l'origen "
                "migrat causa més abandonament' poden explicar que els "
                "dos grups tinguin taxes tan diferents?"
            ),
            "expected_summary": (
                "L'alternativa dominant aquí són les **variables confusores**: "
                "característiques que correlacionen alhora amb l'origen migrat "
                "i amb el risc d'abandonament, i que són la causa real de la "
                "diferència. El feix de confusores és ric i actua entrellaçat: "
                "(a) **nivell socioeconòmic familiar** (renda, ocupació dels "
                "pares); (b) **nivell educatiu dels progenitors** — segons la "
                "Fundació Bofill, la probabilitat d'AEP és fins a 5× més gran "
                "entre joves amb pares amb estudis baixos que entre fills "
                "d'universitaris; (c) **segregació escolar** — alumnat migrat "
                "sovint concentrat en centres amb menys recursos i ràtios "
                "pitjors; (d) **competència en la llengua vehicular** dels "
                "estudis; (e) **discriminació institucional** i expectatives "
                "diferencials del professorat. Una segona via és la **selecció "
                "migratòria**: les famílies que migren no són una mostra "
                "aleatòria de les famílies d'origen, i poden tenir distribucions "
                "diferents en variables que afecten els fills. La causalitat "
                "inversa aquí no s'aplica (abandonar estudis no et fa migrar) "
                "i l'atzar mostral és pràcticament irrellevant donada la mida "
                "de la població."
            ),
            "typical_error": (
                "Donar només una alternativa vaga ('depèn d'altres factors') "
                "sense identificar-ne cap concreta, o quedar-se amb una sola "
                "variable confusora (típicament el nivell socioeconòmic) sense "
                "veure que n'hi ha tot un feix actuant alhora. També "
                "intentar forçar les tres alternatives canòniques quan aquí "
                "la causalitat inversa no s'aplica."
            ),
            "typical_error_label": "CAUS_no_alternatives",
            "key_concepts": ["confounding_variable"],
        },
        {
            "id": 3,
            "text": (
                "Per acabar: **quina mena d'evidència** caldria per defensar "
                "que l'origen migrat, per si mateix, causa l'abandonament "
                "dels estudis?"
            ),
            "expected_summary": (
                "Un experiment aleatoritzat aquí és **èticament i conceptualment "
                "impossible**: no podem assignar a algú la seva nacionalitat o "
                "el seu origen familiar. La via que segueix la literatura és "
                "el **control estadístic dels confusors**: comparar les taxes "
                "d'AEP entre joves d'origen migrat i nascuts a Catalunya **dins "
                "de cada nivell socioeconòmic, dins de cada nivell d'educació "
                "dels pares, dins de cada zona territorial**. Si fent això les "
                "diferències es redueixen o desapareixen, vol dir que el que "
                "veiem és confusió, no causa. La Fundació Bofill documenta "
                "exactament això. Una evidència complementària són els dissenys "
                "**quasi-experimentals**: per exemple, un estudi del Centre "
                "d'Estudis Demogràfics compara fills d'estrangers nascuts a "
                "Catalunya (21,2% no acaben ESO) amb fills d'estrangers "
                "arribats abans dels 7 anys (21,7%) — taxes pràcticament "
                "idèntiques, mateix origen però amb tota o gairebé tota la "
                "trajectòria escolar feta aquí. Si l'origen fos la causa, "
                "esperaríem diferències; el fet que no n'hi hagi descarta "
                "la lectura 'l'origen és la causa'."
            ),
            "typical_error": (
                "Respondre 'fer més estudis' sense especificar el disseny, o "
                "creure que un experiment aleatoritzat seria viable aquí. "
                "Proposar 'controlar pel nivell socioeconòmic' com si fos una "
                "operació trivial sense entendre que requereix dades fines i "
                "estratificació acurada. Confondre 'més dades' amb 'millor "
                "disseny'."
            ),
            "typical_error_label": "CAUS_direct",
            "key_concepts": ["confounding_variable"],
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
