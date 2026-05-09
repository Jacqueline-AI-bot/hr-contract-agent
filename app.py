import json
import re
from datetime import datetime
from typing import Dict, Any, List

import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


APP_TITLE = "HR Contract Module Agent v2"

CORPORATE_HEADER = """Interner Vertragsentwurf · vertraulich
HR Contract Management · Version zur fachlichen Prüfung"""

CORPORATE_FOOTER = """Hinweis: Dieser Text ist ein KI-gestützter Entwurf und ersetzt keine arbeitsrechtliche Prüfung.
Freigabe erforderlich durch HR / Legal vor finaler Verwendung."""

TEXT_MODULES = {
    "Remote Work": {
        "trigger": ["remote", "homeoffice", "mobil", "arbeitsort"],
        "module": """Remote-Work-Regelung:
Die Tätigkeit kann nach vorheriger Abstimmung an bis zu [Anzahl] Tagen pro Woche remote erbracht werden. Die Erreichbarkeit während der vereinbarten Arbeitszeit, die Einhaltung datenschutzrechtlicher Vorgaben sowie der sorgsame Umgang mit Arbeitsmitteln sind sicherzustellen. Die Regelung kann aus betrieblichen Gründen angepasst oder widerrufen werden.""",
        "required_data": ["Anzahl Remote-Tage pro Woche", "Gültigkeitsbeginn", "Erreichbarkeitszeiten", "Arbeitsmittel", "Widerrufsregelung"]
    },
    "Arbeitszeit": {
        "trigger": ["teilzeit", "stunden", "arbeitszeit", "wochenstunden"],
        "module": """Arbeitszeitregelung:
Die regelmäßige wöchentliche Arbeitszeit beträgt ab dem [Datum] [Stunden] Stunden. Die konkrete Verteilung der Arbeitszeit erfolgt in Abstimmung mit der Führungskraft und unter Berücksichtigung betrieblicher Anforderungen.""",
        "required_data": ["Wochenstunden", "Verteilung der Arbeitszeit", "Gültigkeitsbeginn", "Auswirkungen auf Vergütung und Urlaub"]
    },
    "Vergütung": {
        "trigger": ["gehalt", "vergütung", "bonus", "salary", "lohn"],
        "module": """Vergütungsregelung:
Die Vergütung wird ab dem [Datum] gemäß der vereinbarten Anpassung geändert. Details zur Höhe, Zahlungsweise und etwaigen variablen Bestandteilen sind durch HR und Finance zu prüfen und zu bestätigen.""",
        "required_data": ["neue Vergütung", "Gültigkeitsdatum", "Kostenstelle", "variable Bestandteile", "Finance-Freigabe"]
    },
    "Probezeit": {
        "trigger": ["probezeit", "kündigungsfrist"],
        "module": """Probezeitregelung:
Während der vereinbarten Probezeit gelten die im Arbeitsvertrag festgelegten Kündigungsfristen. Abweichende Regelungen sind vor Verwendung durch HR bzw. Legal zu prüfen.""",
        "required_data": ["Probezeitdauer", "vertragliche Kündigungsfrist", "Startdatum des Arbeitsverhältnisses"]
    },
    "Vertragsverlängerung": {
        "trigger": ["verlängerung", "befristung", "laufzeit", "vertrag verlängern"],
        "module": """Vertragsverlängerung:
Der bestehende Vertrag wird bis zum [Datum] verlängert. Alle übrigen Vertragsbestandteile bleiben unverändert bestehen, sofern keine abweichende Regelung ausdrücklich vereinbart wird.""",
        "required_data": ["aktuelles Vertragsende", "neues Vertragsende", "Befristungsgrund", "Legal-Prüfung"]
    },
    "Datenschutz": {
        "trigger": ["datenschutz", "personenbezogen", "vertraulich", "daten"],
        "module": """Datenschutz-Hinweis:
Bei der Verarbeitung personenbezogener Daten sind die internen Datenschutzvorgaben sowie geltende gesetzliche Anforderungen einzuhalten. Zugriff, Speicherung und Weitergabe dürfen nur im erforderlichen Umfang erfolgen.""",
        "required_data": ["Datenkategorie", "Zugriffsberechtigung", "Speicherort", "Löschfrist"]
    }
}

DEPARTMENT_MODULES = {
    "HR": "HR achtet auf klare, mitarbeiterorientierte und nachvollziehbare Formulierungen sowie auf vollständige Personaldaten und saubere Dokumentation.",
    "Legal": "Legal prüft rechtliche Risiken, Vertragsklarheit, Widerrufsvorbehalte, Befristungen und mögliche arbeitsrechtliche Auswirkungen.",
    "Finance": "Finance prüft Kostenstelle, Vergütung, Budgetwirkung, Abrechnungslogik und mögliche Auswirkungen auf Payroll.",
    "Operations": "Operations prüft Umsetzbarkeit im Alltag, Zuständigkeiten, Abläufe, Erreichbarkeit und Übergaben.",
    "People Lead": "People Lead achtet auf Akzeptanz, Kommunikation, Teamwirkung und faire Umsetzung."
}

SYSTEM_PROMPT = """
Du bist ein sehr präziser HR Contract Management Agent.
Du erstellst keine Rechtsberatung, sondern hochwertige interne Vertrags- und HR-Entwürfe zur Prüfung.

Regeln:
1. Nutze den Corporate Header und Footer exakt.
2. Formuliere professionell, klar, natürlich und nicht generisch.
3. Trenne sauber zwischen Vertragsentwurf, Prüfpunkten und fehlenden Informationen.
4. Nutze nur Textbausteine, die zum Fall passen.
5. Wenn Informationen fehlen, verwende Platzhalter in eckigen Klammern.
6. Weise klar auf HR-/Legal-Freigabe hin.
7. Antworte ausschließlich als valides JSON.

JSON-Struktur:
{
  "case_summary": "",
  "detected_topics": ["..."],
  "risk_level": "niedrig | mittel | hoch",
  "missing_information": ["..."],
  "department_notes": ["..."],
  "selected_text_modules": ["..."],
  "contract_draft": "",
  "hr_legal_checklist": ["..."],
  "next_steps": ["..."]
}
"""


def detect_topics(text: str) -> List[str]:
    lowered = text.lower()
    topics = []
    for topic, data in TEXT_MODULES.items():
        if any(t in lowered for t in data["trigger"]):
            topics.append(topic)
    return topics or ["Allgemeiner HR-Fall"]


def get_required_data(topics: List[str]) -> List[str]:
    required = []
    for topic in topics:
        if topic in TEXT_MODULES:
            required.extend(TEXT_MODULES[topic]["required_data"])
    seen = []
    for item in required:
        if item not in seen:
            seen.append(item)
    return seen


def get_modules(topics: List[str]) -> List[str]:
    modules = []
    for topic in topics:
        if topic in TEXT_MODULES:
            modules.append(TEXT_MODULES[topic]["module"])
    return modules


def estimate_risk(text: str, topics: List[str], department: str) -> str:
    high_keywords = ["kündigung", "abmahnung", "befristung", "datenschutz", "personenbezogen", "gehalt", "vergütung"]
    if department == "Legal" or any(k in text.lower() for k in high_keywords) or "Datenschutz" in topics or "Vertragsverlängerung" in topics:
        return "hoch"
    if "Remote Work" in topics or "Arbeitszeit" in topics:
        return "mittel"
    return "niedrig"


def fallback_generate(input_text: str, department: str, document_type: str, person_name: str, effective_date: str) -> Dict[str, Any]:
    topics = detect_topics(input_text)
    modules = get_modules(topics)
    required = get_required_data(topics)
    risk = estimate_risk(input_text, topics, department)

    name = person_name.strip() or "[Name Mitarbeiter:in]"
    date = effective_date.strip() or "[Gültigkeitsdatum]"

    department_note = DEPARTMENT_MODULES.get(department, DEPARTMENT_MODULES["HR"])

    missing = []
    for item in required:
        placeholder = item.lower()
        if placeholder not in input_text.lower():
            missing.append(item)
    if not person_name.strip():
        missing.append("Name der betroffenen Person")
    if not effective_date.strip():
        missing.append("Gültigkeitsbeginn")

    selected_modules_text = modules or [
        "Allgemeiner HR-Baustein: Der Sachverhalt wird dokumentiert, fachlich geprüft und bei Bedarf mit HR / Legal abgestimmt."
    ]

    contract_body = f"""{CORPORATE_HEADER}

Betreff: {document_type} – {name}

1. Ausgangslage
Für {name} soll auf Basis des vorliegenden Sachverhalts eine interne Vertrags- bzw. HR-Regelung vorbereitet werden.

Sachverhalt:
{input_text}

2. Vorgeschlagene Regelung
Die nachfolgende Regelung soll ab dem {date} gelten und vor finaler Verwendung durch HR / Legal geprüft werden.

{chr(10).join(selected_modules_text)}

3. Fachbereichliche Einordnung
{department_note}

4. Vorbehalt
Alle übrigen Vertragsbestandteile bleiben unverändert bestehen, sofern sie nicht ausdrücklich durch diese Regelung angepasst werden.

{CORPORATE_FOOTER}"""

    checklist = [
        "Ist der Vertragsgegenstand eindeutig beschrieben?",
        "Sind Gültigkeitsbeginn und ggf. Befristung klar geregelt?",
        "Sind Auswirkungen auf Vergütung, Arbeitszeit, Urlaub oder Payroll geprüft?",
        "Sind Datenschutz- und Vertraulichkeitspflichten berücksichtigt?",
        "Ist eine Freigabe durch HR / Legal dokumentiert?"
    ]

    return {
        "case_summary": f"{document_type} für {name}: {', '.join(topics)}.",
        "detected_topics": topics,
        "risk_level": risk,
        "missing_information": missing or ["Keine offensichtlichen Pflichtinformationen fehlen."],
        "department_notes": [department_note],
        "selected_text_modules": selected_modules_text,
        "contract_draft": contract_body,
        "hr_legal_checklist": checklist,
        "next_steps": [
            "Fehlende Informationen ergänzen",
            "Entwurf durch HR prüfen lassen",
            "Bei Risiko mittel/hoch Legal einbinden",
            "Finale Version im Vertragsmanagement ablegen",
            "Textbaustein bei wiederkehrendem Fall in die Bibliothek übernehmen"
        ]
    }


def extract_json(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def analyze_with_openai(input_text, department, document_type, person_name, effective_date, api_key, model):
    if OpenAI is None:
        raise RuntimeError("OpenAI package is not installed.")

    topics = detect_topics(input_text)
    modules = get_modules(topics)
    required = get_required_data(topics)
    risk = estimate_risk(input_text, topics, department)

    payload = {
        "corporate_header": CORPORATE_HEADER,
        "corporate_footer": CORPORATE_FOOTER,
        "department": department,
        "department_note": DEPARTMENT_MODULES.get(department, DEPARTMENT_MODULES["HR"]),
        "document_type": document_type,
        "person_name": person_name,
        "effective_date": effective_date,
        "detected_topics": topics,
        "risk_estimate": risk,
        "matching_text_modules": modules,
        "required_data": required,
        "case": input_text
    }

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)}
        ]
    )
    return extract_json(response.choices[0].message.content)


def render_result(result: Dict[str, Any]):
    st.subheader("1. Fallanalyse")
    c1, c2, c3 = st.columns(3)
    c1.metric("Risiko", result.get("risk_level", "-"))
    c2.metric("Themen", len(result.get("detected_topics", [])))
    c3.metric("Fehlende Infos", len(result.get("missing_information", [])))

    st.write(result.get("case_summary", ""))

    st.subheader("2. Erkannte Themen")
    st.write(", ".join(result.get("detected_topics", [])))

    st.subheader("3. Fehlende Informationen")
    for item in result.get("missing_information", []):
        st.markdown(f"- {item}")

    st.subheader("4. Fachbereichliche Hinweise")
    for item in result.get("department_notes", []):
        st.markdown(f"- {item}")

    st.subheader("5. Verwendete Textbausteine")
    for item in result.get("selected_text_modules", []):
        st.text_area("Textbaustein", item, height=110)

    st.subheader("6. Vertrags-/HR-Entwurf")
    st.text_area("Entwurf", result.get("contract_draft", ""), height=460)

    st.subheader("7. HR-/Legal-Checkliste")
    for item in result.get("hr_legal_checklist", []):
        st.checkbox(item, value=False)

    st.subheader("8. Nächste Schritte")
    for item in result.get("next_steps", []):
        st.markdown(f"- {item}")

    st.subheader("JSON Output")
    st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

    st.title("📄 HR Contract Module Agent v2")
    st.caption("Stabilerer MVP für HR-Vertragsmanagement, Textbausteine, Fachbereichslogik und CI-konforme Entwürfe.")

    with st.sidebar:
        st.header("Setup")
        api_key = st.text_input("OpenAI API Key optional", type="password")
        model = st.text_input("Model", value="gpt-4o-mini")
        st.divider()
        st.markdown("**Corporate Identity**")
        st.code(CORPORATE_HEADER)
        st.code(CORPORATE_FOOTER)

    sample = """Eine Mitarbeiterin möchte ab dem 01.06.2026 dauerhaft zwei Tage pro Woche remote arbeiten.
Die Führungskraft ist grundsätzlich einverstanden.
Geregelt werden sollen Erreichbarkeit, Datenschutz, Arbeitsmittel und eine Widerrufsmöglichkeit aus betrieblichen Gründen."""

    col1, col2 = st.columns([2, 1])

    with col1:
        input_text = st.text_area("Sachverhalt / Personalfrage / Vertragsfall", sample, height=230)

    with col2:
        department = st.selectbox("Fachbereich", list(DEPARTMENT_MODULES.keys()), index=0)
        document_type = st.selectbox("Dokumenttyp", ["Vertragsänderung", "Vertragsverlängerung", "HR-Antwort", "Interner Hinweis"], index=0)
        person_name = st.text_input("Name", "Mara Beispiel")
        effective_date = st.text_input("Gültig ab", "01.06.2026")

    if st.button("Entwurf erstellen", type="primary"):
        with st.spinner("Agent erstellt strukturierten HR-Entwurf..."):
            try:
                if api_key:
                    result = analyze_with_openai(input_text, department, document_type, person_name, effective_date, api_key, model)
                    source = "OpenAI"
                else:
                    result = fallback_generate(input_text, department, document_type, person_name, effective_date)
                    source = "Fallback-Regel-Logik"
            except Exception as exc:
                st.error(f"OpenAI-Ausgabe fehlerhaft. Fallback wird genutzt. Fehler: {exc}")
                result = fallback_generate(input_text, department, document_type, person_name, effective_date)
                source = "Fallback-Regel-Logik"

        st.success(f"Erstellt über: {source}")
        render_result(result)

        export = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "input": input_text,
            "result": result,
            "source": source
        }
        st.download_button(
            "JSON exportieren",
            data=json.dumps(export, ensure_ascii=False, indent=2),
            file_name="hr_contract_module_agent_v2_result.json",
            mime="application/json"
        )

    st.divider()
    st.subheader("Textbaustein-Bibliothek")
    rows = []
    for topic, data in TEXT_MODULES.items():
        rows.append({
            "Thema": topic,
            "Trigger": ", ".join(data["trigger"]),
            "Benötigte Daten": ", ".join(data["required_data"])
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


if __name__ == "__main__":
    main()
