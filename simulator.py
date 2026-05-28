"""
simulator.py — CLI simulator del tutor (arquitectura Nivell 1).

Permet provar el sistema des de la línia de comandes amb una clau
Gemini real, sense Streamlit ni UI. Pensat per iterar el system prompt
amb feedback ràpid abans d'invertir en interfície gràfica.

Ús bàsic:
    GEMINI_API_KEY=... python3 simulator.py
    GEMINI_API_KEY=... python3 simulator.py --problem IC-001
    GEMINI_API_KEY=... python3 simulator.py --problem CAUS-001 --debug
    GEMINI_API_KEY=... python3 simulator.py --save sessio.json

Si no s'especifica `--problem`, el simulador presenta un picker
interactiu a l'inici amb els problemes disponibles a `PB.PROBLEMS`.

Entrada de l'alumne (stdin):
    text normal     → torn de conversa
    ?               → demana pista (es passa com a "(L'alumne demana una pista)")
    !!  o  /quit    → sortida

Comandes locals (no consumeixen torn LLM):
    /state          mostra estat actual (pas, prereq, torns)
    /raw            mostra raw_output del darrer torn LLM
    /debug          toggle mode debug (mostra action, parse_ok, temps)
    /save [FILE]    desa l'estat a FILE.json (default: session_<ts>.json)
    /help           llista de comandes

L'opening del tutor (presentació + pregunta del Pas 1) la genera Python
directament des de problem.py. tutor_turn() s'invoca sempre amb un
transcript que acaba en torn 'student', mai per generar l'opening.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import problem as PB
import llm as L


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Sostre de seguretat contra bucles llargs. No és la quota de producció;
# és un límit defensiu per al simulador.
MAX_TURNS_PER_SESSION = 30


def _prereq_id_for(state):
    """Retorna l'id del prerequisit del problema actiu a `state`.

    Multi-problema: cada problema té el seu prereq (PRE-PARAM per a
    IC-001, PRE-CONFOUNDER per a CAUS-001). El state guarda el
    `problem_id` de la sessió i d'aquí en deriva el prereq. Si el
    state no porta problem_id (estats heretats o construïts a mà
    pels tests), tornem al problema per defecte de PB.
    """
    pid = state.get("problem_id", PB.DEFAULT_PROBLEM_ID)
    return PB.PROBLEMS[pid]["prereq_id"]

# ANSI colors per llegibilitat al terminal. Desactivables amb --no-color.
TUTOR_COLOR = "\033[36m"      # cyan
STUDENT_COLOR = "\033[33m"    # yellow
META_COLOR = "\033[90m"       # gris fluix
ERROR_COLOR = "\033[31m"      # vermell
RESET = "\033[0m"


# -----------------------------------------------------------------------------
# Estat
# -----------------------------------------------------------------------------

def new_session(problem_id=None):
    """Estat inicial. El tutor obre la conversa amb una presentació +
    pregunta del Pas 1 generada per Python (sense crida LLM).

    Args:
        problem_id: id del problema (clau a PB.PROBLEMS). Si és None,
            usa PB.DEFAULT_PROBLEM_ID (back-compat amb codi heretat).

    Aquesta funció no afegeix cap etiqueta "Pregunta." al contingut —
    aquesta decoració es fa al renderer (app.py per a Streamlit). El
    CLI (simulator.py) no l'afegeix; mostra el text en cru."""
    if problem_id is None:
        problem_id = PB.DEFAULT_PROBLEM_ID
    bundle = PB.get(problem_id)
    p = bundle["problem"]

    opening = (
        f"{p['enunciat']}\n\n"
        f"{p['passos'][0]['text']}"
    )
    return {
        "problem_id": problem_id,
        "started_at": time.time(),
        "transcript": [{"role": "tutor", "content": opening}],
        # `display`: registre orientat a la UI. Cada bombolla porta el seu
        # `source` perquè el renderer la pugui acolorir segons qui l'ha
        # generada — "py" (determinista, Python) o "ai" (heurística, model).
        # L'enunciat d'obertura i les preguntes canòniques dels passos són
        # sempre "py". Es manté separat del `transcript` (context del model)
        # perquè el transcript no ha de duplicar les bombolles deterministes.
        "display": [{"role": "tutor", "content": opening, "source": "py"}],
        "current_step": 1,
        "active_prereq": None,
        "step_before_prereq": None,
        "finished": False,
        "turn_count": 0,
        "history": [],            # rastre detallat de cada torn LLM
        "last_raw_output": None,
    }


def apply_action(state, action):
    """Aplica una transició d'estat segons l'acció del control block.

    Retorna un codi de transició perquè el caller sàpiga quina pregunta
    canònica (determinista) ha d'injectar al display:
        "stay"            → cap canvi de posició
        "next_step"       → avançat a un pas nou dins del problema
        "finished"        → avançat des de l'últim pas (sessió completa)
        "enter_prereq"    → entrat al reforç
        "exit_prereq"     → sortit del reforç (torna al pas que el va activar)
        "noop"            → acció sense efecte (p.ex. retreat ja dins reforç)

    Compatibilitat: els callers antics que ignoren el valor de retorn
    segueixen funcionant; només muta `state` com sempre.
    """
    if action == "stay":
        return "stay"

    if action == "advance":
        if state["active_prereq"]:
            # Sortida del reforç: tornem al step que el va activar.
            state["current_step"] = state["step_before_prereq"]
            state["active_prereq"] = None
            state["step_before_prereq"] = None
            return "exit_prereq"
        elif state["current_step"] is not None:
            pid = state.get("problem_id", PB.DEFAULT_PROBLEM_ID)
            total = len(PB.PROBLEMS[pid]["problem"]["passos"])
            if state["current_step"] < total:
                state["current_step"] += 1
                return "next_step"
            else:
                state["finished"] = True
                return "finished"
        return "noop"

    if action == "retreat_to_prereq":
        if state["active_prereq"] is None:
            state["step_before_prereq"] = state["current_step"]
            state["active_prereq"] = _prereq_id_for(state)
            return "enter_prereq"
        # Si ja està a prereq, no-op (el model l'estaria demanant per error).
        return "noop"

    return "noop"


# -----------------------------------------------------------------------------
# Capa determinista: Python garanteix la pregunta canònica
# -----------------------------------------------------------------------------

def append_display(state, role, content, source):
    """Afegeix una bombolla al registre de display (UI), amb el seu origen.

    source ∈ {"py", "ai", "student"}. No toca el `transcript` (context del
    model): això ho fan els callers explícitament quan cal.
    """
    state.setdefault("display", []).append(
        {"role": role, "content": content, "source": source}
    )


def canonical_text_for_transition(state, transition):
    """Pregunta canònica (determinista) que toca mostrar després d'una
    transició, o None si la transició no en necessita.

    - next_step / exit_prereq → pregunta canònica del pas actual.
    - enter_prereq            → pregunta del prerequisit.
    - la resta                → None.
    """
    pid = state.get("problem_id", PB.DEFAULT_PROBLEM_ID)
    if transition in ("next_step", "exit_prereq"):
        return PB.canonical_question(pid, state["current_step"])
    if transition == "enter_prereq":
        return PB.prereq_question(pid)
    return None


def enrich_after_transition(state, transition):
    """Garanteix que la pregunta canònica del nou pas/reforç aparegui sempre.

    És el cor del transvasament Tier 1: en lloc de confiar que el model
    redacti la pregunta del pas següent (i mantingui la coherència
    action/text a còpia de regles al prompt), Python l'injecta de manera
    determinista quan hi ha hagut una transició de posició.

    Variant "xarxa de seguretat" (no la versió dura de A): el model encara
    pot fer una transició conversacional al seu reply; aquí només afegim
    l'enunciat canònic com a àncora **si encara no hi és**, en una bombolla
    pròpia marcada com a determinista (source="py").

    Doble efecte:
      - Al `display`: bombolla determinista separada (es pinta diferent).
      - Al `transcript`: s'enganxa al darrer torn del tutor perquè el model
        vegi en el seu context la pregunta que ara toca respondre i no es
        trenqui l'alternança tutor/student.

    Retorna el text injectat (str) o None si no calia.
    """
    canonical = canonical_text_for_transition(state, transition)
    if not canonical:
        return None

    # Anti-duplicació: si el reply del model ja conté (gairebé) la pregunta
    # canònica, no la repetim. Comparem un tros distintiu normalitzat.
    last_tutor = next(
        (t["content"] for t in reversed(state["transcript"])
         if t["role"] == "tutor"),
        "",
    )
    probe = _normalize_for_dup(canonical)[:60]
    if probe and probe in _normalize_for_dup(last_tutor):
        return None

    # Display: bombolla determinista pròpia.
    append_display(state, "tutor", canonical, "py")
    # Transcript: enganxa al darrer tutor (manté l'alternança i informa el
    # model de la pregunta vigent).
    for m in reversed(state["transcript"]):
        if m["role"] == "tutor":
            m["content"] += f"\n\n{canonical}"
            break
    return canonical


def _normalize_for_dup(s):
    """Normalització laxa per detectar si una pregunta ja és al text."""
    import unicodedata
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


def position_dict(state):
    """Format que rep llm.tutor_turn (paràmetre reservat per v1)."""
    return {"step": state["current_step"], "prereq": state["active_prereq"]}


def compute_quality_signals(state: dict) -> dict:
    """Calcula mètriques agregades de qualitat de la sessió a partir del
    rastre detallat (state['history']) i metadades. Aquest bloc s'adjunta
    al state al final de la sessió per al professor que la revisa.

    Cada camp respon a una pregunta concreta:
      - completed, total_turns_llm: acaba? en quants torns?
      - action_counts, stay_advance_ratio: quanta dificultat? (molt stay
        per advance = molt encallat)
      - turns_per_step: a quin pas s'ha encallat?
      - used_prereq, turns_in_prereq: necessita base prèvia?
      - hint_requests: confiança? (moltes pistes = inseguretat)
      - parse_failures: salut tècnica de la sessió
      - elapsed_seconds_total, avg_elapsed_seconds_per_turn: latència

    Cost: O(N) sobre len(history). Barat per a sessions normals (<50 torns).
    """
    history = state.get("history", [])

    # Comptadors d'accions presos pel model
    action_counts = {"stay": 0, "advance": 0, "retreat_to_prereq": 0}
    for e in history:
        action = e.get("action")
        if action in action_counts:
            action_counts[action] += 1

    # Ràtio stay:advance. Si no hi ha advances, és None — el professor
    # ho llegirà com "no hi ha hagut progressió". No el forcem a 0.0
    # o a infinit perquè cap dels dos transmet la idea correctament.
    if action_counts["advance"] > 0:
        stay_advance_ratio = round(
            action_counts["stay"] / action_counts["advance"], 2
        )
    else:
        stay_advance_ratio = None

    # Distribució de torns per pas i en reforç.
    # Per cada entrada del rastre, mirem on estava l'alumne ABANS de la
    # crida (position_before): aquell torn s'imputa allà. Així, un torn
    # que avança del pas 2 al pas 3 compta com a "torn al pas 2".
    pid = state.get("problem_id", PB.DEFAULT_PROBLEM_ID)
    total_steps = len(PB.PROBLEMS[pid]["problem"]["passos"])
    turns_per_step = {n: 0 for n in range(1, total_steps + 1)}
    turns_in_prereq = 0
    for e in history:
        pb = e.get("position_before", {})
        if pb.get("prereq"):
            turns_in_prereq += 1
        elif pb.get("step") in turns_per_step:
            turns_per_step[pb["step"]] += 1

    # Sol·licituds de pista. Marcador literal que el simulador injecta
    # quan l'alumne escriu `?` — si algun dia canvia, aquesta línia
    # també.
    hint_marker = "(L'alumne demana una pista)"
    hint_requests = sum(1 for e in history
                        if e.get("student_msg") == hint_marker)

    # Falles de parse del control block (model va retornar sense
    # separador, o JSON malformat → fallback a action=stay).
    parse_failures = sum(1 for e in history
                         if e.get("control_parse_ok") is False)

    # Temps total i mitjana per torn.
    #
    # Important: elapsed_total NO es calcula amb `time.time() - started_at`
    # perquè la funció es pot cridar molt després del final de la sessió
    # (per ex., re-processant un JSON desat) i donaria temps absurds.
    # Calculem el delta entre l'inici i el timestamp del DARRER torn LLM,
    # que sempre és vàlid si la sessió ha tingut almenys un torn.
    if history:
        last_ts = history[-1].get("ts")
        started_at = state.get("started_at")
        if last_ts is not None and started_at is not None:
            elapsed_total = last_ts - started_at
        else:
            # Rastre sense timestamps (cas de tests amb dades sintètiques).
            # Caiem a la suma del temps per torn — informació de sistema,
            # no captura les pauses entre torns, però mai dóna xifres
            # falses.
            elapsed_total = sum(e.get("elapsed_seconds", 0.0)
                                for e in history)
    else:
        elapsed_total = 0.0

    elapsed_times = [e.get("elapsed_seconds", 0.0) for e in history]
    avg_elapsed = (sum(elapsed_times) / len(elapsed_times)
                   if elapsed_times else 0.0)

    return {
        "completed": bool(state.get("finished", False)),
        "total_turns_llm": int(state.get("turn_count", 0)),
        "elapsed_seconds_total": round(elapsed_total, 1),
        "avg_elapsed_seconds_per_turn": round(avg_elapsed, 2),
        "action_counts": action_counts,
        "stay_advance_ratio": stay_advance_ratio,
        "turns_per_step": turns_per_step,
        "used_prereq": turns_in_prereq > 0,
        "turns_in_prereq": turns_in_prereq,
        "hint_requests": hint_requests,
        "parse_failures": parse_failures,
    }


def format_quality_signals(qs: dict) -> str:
    """Render llegible del bloc quality_signals per al terminal al final
    de la sessió. JSON crud per al fitxer; aquest format per a la persona."""
    ratio = (f"{qs['stay_advance_ratio']:.2f}"
             if qs['stay_advance_ratio'] is not None else "n/a")
    ac = qs["action_counts"]
    tps_parts = [f"pas {n}: {c}" for n, c in qs["turns_per_step"].items() if c > 0]
    tps = ", ".join(tps_parts) if tps_parts else "(cap torn registrat)"
    prereq_info = (f"sí ({qs['turns_in_prereq']} torns)"
                   if qs["used_prereq"] else "no")
    lines = [
        "=== Quality signals ===",
        f"  Completat: {qs['completed']}",
        f"  Torns LLM: {qs['total_turns_llm']}    "
        f"Temps total: {qs['elapsed_seconds_total']}s    "
        f"Mitja/torn: {qs['avg_elapsed_seconds_per_turn']}s",
        f"  Accions: stay={ac['stay']}, advance={ac['advance']}, "
        f"retreat={ac['retreat_to_prereq']}    Ràtio stay/advance: {ratio}",
        f"  Distribució torns: {tps}",
        f"  Reforç usat: {prereq_info}",
        f"  Sol·licituds de pista: {qs['hint_requests']}    "
        f"Parse failures: {qs['parse_failures']}",
    ]
    return "\n".join(lines)


def position_summary(state):
    """Resum llegible per al display al terminal."""
    if state["finished"]:
        return "sessió acabada"
    if state["active_prereq"]:
        return (f"reforç {state['active_prereq']} "
                f"(tornarà a pas {state['step_before_prereq']})")
    if state["current_step"]:
        pid = state.get("problem_id", PB.DEFAULT_PROBLEM_ID)
        total = len(PB.PROBLEMS[pid]["problem"]["passos"])
        return f"pas {state['current_step']} de {total}"
    return "indefinit"


# -----------------------------------------------------------------------------
# Render
# -----------------------------------------------------------------------------

class Display:
    """Encapsula la sortida formatada per facilitar --no-color."""

    def __init__(self, use_color=True):
        self.use_color = use_color

    def _c(self, color):
        return color if self.use_color else ""

    def _r(self):
        return RESET if self.use_color else ""

    def tutor(self, text):
        print(f"\n{self._c(TUTOR_COLOR)}Tutor:{self._r()} {text}\n")

    def meta(self, text):
        print(f"{self._c(META_COLOR)}{text}{self._r()}")

    def error(self, text):
        print(f"{self._c(ERROR_COLOR)}{text}{self._r()}")

    def student_prompt(self):
        return f"{self._c(STUDENT_COLOR)}Alumne:{self._r()} "


# -----------------------------------------------------------------------------
# Handlers d'entrada
# -----------------------------------------------------------------------------

def handle_local_command(state, raw, disp, debug_mode_ref):
    """Gestiona comandes locals (les que no consumeixen torn LLM).
    Retorna True si era una comanda local i ja s'ha gestionat, False
    altrament. debug_mode_ref és una llista d'un element per permetre
    mutació (toggle)."""
    s = raw.strip()

    if s == "/help":
        disp.meta(
            "Comandes:\n"
            "  ?            demana pista\n"
            "  !!  /quit    sortir\n"
            "  /state       estat actual\n"
            "  /raw         raw_output del darrer torn\n"
            "  /debug       toggle mode debug\n"
            "  /save [FILE] desa sessió a JSON\n"
            "  /help        aquesta llista"
        )
        return True

    if s == "/state":
        disp.meta(f"Estat: {position_summary(state)}; torns LLM: {state['turn_count']}")
        return True

    if s == "/raw":
        if state["last_raw_output"]:
            disp.meta("--- raw output del darrer torn ---")
            print(state["last_raw_output"])
            disp.meta("--- fi ---")
        else:
            disp.meta("(no hi ha encara cap torn LLM)")
        return True

    if s == "/debug":
        debug_mode_ref[0] = not debug_mode_ref[0]
        disp.meta(f"Mode debug: {'ON' if debug_mode_ref[0] else 'OFF'}")
        return True

    if s.startswith("/save"):
        parts = s.split(maxsplit=1)
        fname = parts[1].strip() if len(parts) > 1 else f"session_{int(time.time())}.json"
        try:
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2, default=str)
            disp.meta(f"Sessió desada a {fname}")
        except Exception as e:
            disp.error(f"Error desant a {fname}: {e}")
        return True

    return False


# -----------------------------------------------------------------------------
# Picker de problema
# -----------------------------------------------------------------------------

def pick_problem_interactive(disp=None):
    """Pregunta a l'usuari quin problema vol treballar.

    Mostra la llista de PB.PROBLEMS i accepta:
      - un índex numèric (1, 2, ...)
      - un id literal (IC-001, CAUS-001)

    Retorna el problem_id triat. Si l'usuari prem Enter sense escriure
    res, retorna PB.DEFAULT_PROBLEM_ID.
    """
    options = PB.list_ids()
    print()
    print("Problemes disponibles:")
    for i, (pid, title) in enumerate(options, 1):
        marker = "  (default)" if pid == PB.DEFAULT_PROBLEM_ID else ""
        print(f"  {i}) {pid:10s} — {title}{marker}")
    print()

    while True:
        choice = input(
            f"Tria un problema [1-{len(options)}, "
            f"o Enter per defecte={PB.DEFAULT_PROBLEM_ID}]: "
        ).strip()
        if not choice:
            return PB.DEFAULT_PROBLEM_ID
        # Per índex
        if choice.isdigit():
            n = int(choice)
            if 1 <= n <= len(options):
                return options[n - 1][0]
        # Per id literal (case-insensitive)
        for pid, _ in options:
            if choice.upper() == pid.upper():
                return pid
        print(f"  No reconec '{choice}'. Prova de nou.")


# -----------------------------------------------------------------------------
# Loop principal
# -----------------------------------------------------------------------------

def run_session(debug_mode=False, save_path=None, use_color=True,
                problem_id=None):
    disp = Display(use_color=use_color)
    debug_mode_ref = [debug_mode]

    if problem_id is None:
        problem_id = pick_problem_interactive(disp)
    elif problem_id not in PB.PROBLEMS:
        print(f"Error: problema desconegut '{problem_id}'. "
              f"Disponibles: {sorted(PB.PROBLEMS)}", file=sys.stderr)
        sys.exit(2)

    state = new_session(problem_id)

    disp.meta(f"=== Sessió iniciada — "
              f"{datetime.now().isoformat(timespec='seconds')} ===")
    disp.meta(f"Problema: {problem_id} — "
              f"{PB.PROBLEMS[problem_id]['title_human']}")
    disp.meta(f"Estat inicial: {position_summary(state)}")
    disp.meta(f"Model: {L.MODEL} | Prompt: tutor_system_{L.PROMPT_VERSION}_{problem_id}.md")
    disp.meta("Escriu /help per veure les comandes.")
    disp.tutor(state["transcript"][0]["content"])

    while True:
        # Condicions de tancament
        if state["finished"]:
            disp.meta("--- Sessió completada (action=advance des de l'últim pas) ---")
            break
        if state["turn_count"] >= MAX_TURNS_PER_SESSION:
            disp.meta(f"--- Límit de {MAX_TURNS_PER_SESSION} torns assolit ---")
            break

        # Llegir entrada
        try:
            raw = input(disp.student_prompt())
        except EOFError:
            print()
            disp.meta("--- EOF, sortint ---")
            break
        except KeyboardInterrupt:
            print()
            disp.meta("--- interromput (Ctrl-C) ---")
            break

        s = raw.strip()

        # Línia buida: ignora
        if not s:
            continue

        # Sortida
        if s in ("!!", "/quit", "/exit"):
            disp.meta("--- sortida sol·licitada ---")
            break

        # Comandes locals (no consumeixen torn LLM)
        if s.startswith("/"):
            if handle_local_command(state, s, disp, debug_mode_ref):
                continue
            # Comanda no reconeguda; tracta-la com a missatge normal
            disp.meta(f"(comanda no reconeguda: '{s}'. La tracto com a missatge.)")

        # Pista: substitució per la cadena que el prompt espera
        if s == "?":
            student_msg = "(L'alumne demana una pista)"
        else:
            student_msg = s

        # Afegim el torn de l'alumne al transcript
        state["transcript"].append({"role": "student", "content": student_msg})
        append_display(state, "student", student_msg, "student")
        state["turn_count"] += 1

        # Cridem el model
        try:
            disp.meta(f"[cridant... posició: {position_summary(state)}]")
            t0 = time.time()
            active_problem = PB.PROBLEMS[state["problem_id"]]["problem"]
            result = L.tutor_turn(active_problem, position_dict(state),
                                  state["transcript"])
            elapsed = time.time() - t0
        except Exception as e:
            disp.error(f"⚠ Error a la crida LLM: {type(e).__name__}: {e}")
            # Retirem el torn de l'alumne perquè pugui tornar-ho a provar
            state["transcript"].pop()
            if state["display"] and state["display"][-1]["role"] == "student":
                state["display"].pop()
            state["turn_count"] -= 1
            continue

        state["last_raw_output"] = result["raw_output"]

        # Origen del reply: "py" si ha respost el mode de reserva, "ai" si IA.
        reply_source = "py" if result.get("mode") == "py" else "ai"

        # Afegim la resposta del tutor al transcript. Sense aquesta línia,
        # cada crida posterior enviaria una seqüència de missatges 'student'
        # consecutius (violant l'alternança user/model que espera Gemini) i
        # el model perdria memòria del que ha dit en torns anteriors —
        # quedant-li només el position_marker com a font de veritat.
        # Veure `test_tutor_turn.py` Test 17/18.
        state["transcript"].append({"role": "tutor", "content": result["reply"]})
        append_display(state, "tutor", result["reply"], reply_source)

        # Anotació al rastre detallat
        position_before = {"step": state["current_step"],
                           "prereq": state["active_prereq"]}

        # Apliquem la transició al state i obtenim el codi de transició.
        transition = apply_action(state, result["action"])

        # Tier 1: Python garanteix la pregunta canònica del nou pas/reforç
        # com a bombolla determinista (source="py"), en lloc de confiar que
        # el model la redacti i mantingui la coherència action/text.
        canonical = enrich_after_transition(state, transition)

        position_after = {"step": state["current_step"],
                          "prereq": state["active_prereq"]}

        state["history"].append({
            "turn": state["turn_count"],
            "ts": time.time(),
            "student_msg": student_msg,
            "tutor_reply": result["reply"],
            "action": result["action"],
            "objectives_met": result["objectives_met"],
            "control_parse_ok": result["control_parse_ok"],
            "position_before": position_before,
            "position_after": position_after,
            "elapsed_seconds": elapsed,
        })

        # Mostrem la resposta del tutor (amb etiqueta d'origen) i, si Python
        # ha injectat la pregunta canònica, també.
        tag = "[🐍 Python]" if reply_source == "py" else "[🤖 IA]"
        disp.tutor(f"{tag} {result['reply']}")
        if canonical:
            disp.tutor(f"[🐍 Python · enunciat del pas] {canonical}")

        # Meta info: transició si n'hi ha; debug si està actiu
        if position_before != position_after:
            before_str = position_summary_from(position_before)
            after_str = position_summary_from(position_after)
            disp.meta(f"→ transició d'estat: {before_str} → {after_str}")

        if debug_mode_ref[0]:
            disp.meta(
                f"[debug] action={result['action']}, "
                f"parse_ok={result['control_parse_ok']}, "
                f"objectives={result['objectives_met']}, "
                f"temps={elapsed:.1f}s"
            )

    # Tancament: calcular i adjuntar quality_signals abans de desar o
    # imprimir. D'aquesta manera, qualsevol JSON desat (--save o
    # /save) conté el bloc, i la sortida del terminal el mostra a la
    # persona que ha corregut la sessió.
    state["quality_signals"] = compute_quality_signals(state)

    # Tancament: save automàtic si --save
    if save_path:
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2, default=str)
            disp.meta(f"Sessió desada a {save_path}")
        except Exception as e:
            disp.error(f"Error desant a {save_path}: {e}")

    disp.meta(f"=== Fi de sessió ({state['turn_count']} torns LLM) ===")
    disp.meta(format_quality_signals(state["quality_signals"]))
    return state


def position_summary_from(pos):
    """Variant de position_summary que treballa amb un dict de posició
    aïllat (no l'estat sencer). Per mostrar transicions."""
    if pos["prereq"]:
        return f"reforç {pos['prereq']}"
    if pos["step"]:
        return f"pas {pos['step']}"
    return "indefinit"


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="CLI simulator del tutor (Nivell 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples:\n"
            "  GEMINI_API_KEY=... python3 simulator.py\n"
            "  GEMINI_API_KEY=... python3 simulator.py --problem IC-001\n"
            "  GEMINI_API_KEY=... python3 simulator.py --problem CAUS-001 --debug\n"
            "  GEMINI_API_KEY=... python3 simulator.py --save sessio.json\n"
            "\n"
            "Problemes disponibles: IC-001, CAUS-001 "
            f"(default: {PB.DEFAULT_PROBLEM_ID})\n"
            "Sense --problem, el simulador mostra un picker interactiu.\n"
        ),
    )
    p.add_argument("--problem", metavar="ID",
                   choices=sorted(PB.PROBLEMS),
                   help="id del problema a treballar (sense flag: picker interactiu)")
    p.add_argument("--debug", action="store_true",
                   help="mostra action, parse_ok i temps a cada torn")
    p.add_argument("--save", metavar="FILE",
                   help="desa la sessió a FILE.json en sortir")
    p.add_argument("--no-color", action="store_true",
                   help="desactiva codis ANSI de color (per a terminals sense suport)")
    args = p.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY no està definida.", file=sys.stderr)
        print("  export GEMINI_API_KEY=la-teva-clau", file=sys.stderr)
        sys.exit(1)

    try:
        run_session(
            debug_mode=args.debug,
            save_path=args.save,
            use_color=not args.no_color,
            problem_id=args.problem,
        )
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
