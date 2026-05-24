"""
simulator.py — CLI simulator del tutor IC (arquitectura Nivell 1).

Permet provar el sistema des de la línia de comandes amb una clau
Gemini real, sense Streamlit ni UI. Pensat per iterar el system prompt
amb feedback ràpid abans d'invertir en interfície gràfica.

Ús bàsic:
    GEMINI_API_KEY=... python3 simulator.py
    GEMINI_API_KEY=... python3 simulator.py --debug
    GEMINI_API_KEY=... python3 simulator.py --save sessio.json

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

PREREQ_ID = "PRE-PARAM"

# ANSI colors per llegibilitat al terminal. Desactivables amb --no-color.
TUTOR_COLOR = "\033[36m"      # cyan
STUDENT_COLOR = "\033[33m"    # yellow
META_COLOR = "\033[90m"       # gris fluix
ERROR_COLOR = "\033[31m"      # vermell
RESET = "\033[0m"


# -----------------------------------------------------------------------------
# Estat
# -----------------------------------------------------------------------------

def new_session():
    """Estat inicial. El tutor obre la conversa amb una presentació +
    pregunta del Pas 1 generada per Python (sense crida LLM)."""
    opening = (
        f"Hola. Treballarem un problema d'inferència estadística junts.\n\n"
        f"{PB.PROBLEM['enunciat']}\n\n"
        f"Comencem pel primer pas: {PB.PROBLEM['passos'][0]['text']}"
    )
    return {
        "started_at": time.time(),
        "transcript": [{"role": "tutor", "content": opening}],
        "current_step": 1,
        "active_prereq": None,
        "step_before_prereq": None,
        "finished": False,
        "turn_count": 0,
        "history": [],            # rastre detallat de cada torn LLM
        "last_raw_output": None,
    }


def apply_action(state, action):
    """Aplica una transició d'estat segons l'acció del control block."""
    if action == "stay":
        return

    if action == "advance":
        if state["active_prereq"]:
            # Sortida del reforç: tornem al step que el va activar.
            state["current_step"] = state["step_before_prereq"]
            state["active_prereq"] = None
            state["step_before_prereq"] = None
        elif state["current_step"] is not None:
            total = len(PB.PROBLEM["passos"])
            if state["current_step"] < total:
                state["current_step"] += 1
            else:
                state["finished"] = True
        return

    if action == "retreat_to_prereq":
        if state["active_prereq"] is None:
            state["step_before_prereq"] = state["current_step"]
            state["active_prereq"] = PREREQ_ID
        # Si ja està a prereq, no-op (el model l'estaria demanant per error).
        return


def position_dict(state):
    """Format que rep llm.tutor_turn (paràmetre reservat per v1)."""
    return {"step": state["current_step"], "prereq": state["active_prereq"]}


def position_summary(state):
    """Resum llegible per al display al terminal."""
    if state["finished"]:
        return "sessió acabada"
    if state["active_prereq"]:
        return (f"reforç {state['active_prereq']} "
                f"(tornarà a pas {state['step_before_prereq']})")
    if state["current_step"]:
        return f"pas {state['current_step']} de {len(PB.PROBLEM['passos'])}"
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
# Loop principal
# -----------------------------------------------------------------------------

def run_session(debug_mode=False, save_path=None, use_color=True):
    disp = Display(use_color=use_color)
    debug_mode_ref = [debug_mode]
    state = new_session()

    disp.meta(f"=== Sessió iniciada — "
              f"{datetime.now().isoformat(timespec='seconds')} ===")
    disp.meta(f"Estat inicial: {position_summary(state)}")
    disp.meta(f"Model: {L.MODEL} | Prompt: tutor_system_{L.PROMPT_VERSION}.md")
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
        state["turn_count"] += 1

        # Cridem el model
        try:
            disp.meta(f"[cridant... posició: {position_summary(state)}]")
            t0 = time.time()
            result = L.tutor_turn(PB.PROBLEM, position_dict(state),
                                  state["transcript"])
            elapsed = time.time() - t0
        except Exception as e:
            disp.error(f"⚠ Error a la crida LLM: {type(e).__name__}: {e}")
            # Retirem el torn de l'alumne perquè pugui tornar-ho a provar
            state["transcript"].pop()
            state["turn_count"] -= 1
            continue

        state["last_raw_output"] = result["raw_output"]

        # Afegim la resposta del tutor al transcript. Sense aquesta línia,
        # cada crida posterior enviaria una seqüència de missatges 'student'
        # consecutius (violant l'alternança user/model que espera Gemini) i
        # el model perdria memòria del que ha dit en torns anteriors —
        # quedant-li només el position_marker com a font de veritat.
        # Veure `test_tutor_turn.py` Test 17/18.
        state["transcript"].append({"role": "tutor", "content": result["reply"]})

        # Anotació al rastre detallat
        position_before = {"step": state["current_step"],
                           "prereq": state["active_prereq"]}

        # Apliquem la transició al state
        apply_action(state, result["action"])

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

        # Mostrem la resposta del tutor
        disp.tutor(result["reply"])

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

    # Tancament: save automàtic si --save
    if save_path:
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2, default=str)
            disp.meta(f"Sessió desada a {save_path}")
        except Exception as e:
            disp.error(f"Error desant a {save_path}: {e}")

    disp.meta(f"=== Fi de sessió ({state['turn_count']} torns LLM) ===")
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
        description="CLI simulator del tutor IC (Nivell 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples:\n"
            "  GEMINI_API_KEY=... python3 simulator.py\n"
            "  GEMINI_API_KEY=... python3 simulator.py --debug\n"
            "  GEMINI_API_KEY=... python3 simulator.py --save sessio.json\n"
        ),
    )
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
        )
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
