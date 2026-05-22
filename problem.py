"""
Tutor IC — base de dades mínima.

Un sol problema (IC-001), tres passos, un prerequisit (PRE-PARAM), un
catàleg petit d'errors. Aquest fitxer és tot el contingut pedagògic del
sistema; canviar-lo és canviar el que s'ensenya.
"""

ERROR_CATALOG = {
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

# Una sola dependència: la distinció paràmetre vs. estadístic.
DEPENDENCIES = {
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

PREREQUISITES = {
    "PRE-PARAM": {
        "id": "PRE-PARAM",
        "concept": "param_vs_stat",
        "question": (
            "Quina diferència hi ha entre μ (la mitjana poblacional) i "
            "x̄ (la mitjana d'una mostra concreta)? "
            "Quina de les dues és aleatòria i quina és fixa?"
        ),
        # Validació deterministica: cal almenys una keyword "required" i
        # cap "forbidden". És intencionalment generosa.
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

PROBLEM = {
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
