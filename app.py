import streamlit as st
from openai import OpenAI
import json
import time

# --- SEITENKONFIGURATION ---
st.set_page_config(page_title="bruno di liran App", page_icon="🎓", layout="centered")

# --- API KEY & CLIENT SETUP ---
try:
    API_KEY = st.secrets["OPENAI_API_KEY"]
    client = OpenAI(api_key=API_KEY)
except KeyError:
    st.error("Fehler: API Key nicht gefunden. Bitte richte die Streamlit Secrets ein.")
    st.stop()

# --- SYSTEM PROMPT ---
# (Dein bestehender Prompt bleibt absolut identisch)
SYSTEM_PROMPT = """
Du bist ein Experte für das Umschreiben von Multiple Choice Prüfungsfragen im Versicherungswesen.

DEINE REGELN (ABSOLUT ZWINGEND):
1. Du MUSST die Original-Frage sprachlich neu formulieren.
2. Du MUSST jede einzelne Original-Antwortmöglichkeit sprachlich neu formulieren (andere Verben, anderer Satzbau, Synonyme). 1:1 Kopien sind streng verboten!
3. Die inhaltliche Bedeutung und die exakte Reihenfolge der Antworten müssen absolut identisch bleiben. Antwort 1 bleibt Antwort 1.
4. Fachbegriffe (z.B. VAG, FINMA) bleiben erhalten.

BEISPIEL FÜR DEINE ARBEITSWEISE:
Original Frage: "Wer überwacht die Versicherungsunternehmen?"
Original Antwort 1: "Die Eidgenössische Finanzmarktaufsicht (FINMA)."
Original Antwort 2: "Das Parlament."

Deine Variante 1:
Frage: "Welche Institution ist für die Kontrolle der Versicherungsgesellschaften zuständig?"
Antwort 1: "Für diese Aufsicht ist die FINMA (Eidgenössische Finanzmarktaufsicht) verantwortlich."
Antwort 2: "Die gesetzgebende Behörde (Parlament)."

OUTPUT-FORMAT (NUR JSON):
{
  "variante_1": {
    "frage": "...",
    "antworten": ["...", "..."]
  },
  "variante_2": {
    "frage": "...",
    "antworten": ["...", "..."]
  }
}
"""

def generiere_varianten(frage, antworten_liste):
    """Sendet die Frage und Antworten an die OpenAI API."""
    user_content = f"ORIGINAL-FRAGE:\n{frage}\n\nORIGINAL-ANTWORTEN:\n"
    for idx, ant in enumerate(antworten_liste):
        user_content += f"Antwort {idx + 1}: {ant}\n"
        
    user_content += "\nWARNUNG: Generiere jetzt das JSON. Formuliere zwingend JEDE EINZELNE Antwort sprachlich neu! Nutze neue Satzstrukturen."

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.5,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Fehler bei API-Abfrage: {e}")
        return None


# --- STREAMLIT UI ---
st.title("🎓 bruno di liran App")
st.markdown("""
Lade hier deine JSON-Datei hoch. Das Tool analysiert die bestehenden Fragen und generiert pro Frage **zwei neue, methodisch korrekte Varianten** (Fragetexte und Antworten) direkt in die dafür vorgesehenen Datenfelder.
""")

# 1. Datei Upload Widget - nur noch für JSON
uploaded_file = st.file_uploader("Wähle eine JSON-Datei (.json)", type=['json'])

if uploaded_file is not None:
    st.success(f"Datei '{uploaded_file.name}' erfolgreich geladen!")
    
    # 2. Button zum Starten
    if st.button("🚀 Verarbeitung starten", type="primary"):
        
        with st.status("Verarbeite JSON-Datei...", expanded=True) as status:
            try:
                # JSON nativ einlesen
                data = json.load(uploaded_file)
            except Exception as e:
                st.error(f"Fehler beim Lesen der JSON-Datei: {e}")
                st.stop()
                
            if "questions" not in data or not isinstance(data["questions"], list):
                st.error("Fehler: Das JSON-File enthält kein gültiges 'questions' Array.")
                st.stop()
                
            questions_list = data["questions"]
            total_rows = len(questions_list)
            updates_gemacht = 0
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Verarbeitungsschleife durch das JSON-Array
            for i, q in enumerate(questions_list):
                # Fortschritt aktualisieren
                progress_bar.progress((i + 1) / total_rows)
                
                frage = q.get("title", "")
                orig_id = q.get("id", "Unbekannt (ID)")
                
                # Wenn kein Titel da ist, überspringen
                if not frage:
                    continue
                    
                # Antworten aus dem aktuellen Fragen-Objekt extrahieren
                answers_obj_list = q.get("answers", [])
                antworten_liste = [ans.get("content", "") for ans in answers_obj_list if isinstance(ans, dict)]
                
                status_text.write(f"⏳ Verarbeite ID {orig_id}: '{frage[:30]}...'")
                
                # KI aufrufen
                varianten = generiere_varianten(frage, antworten_liste)
                
                if varianten:
                    try:
                        # 1. Fragentexte befüllen (Neu: title_variants_de als String-Array)
                        q["title_variants_de"] = [
                            varianten["variante_1"]["frage"],
                            varianten["variante_2"]["frage"]
                        ]
                        
                        # Alte "title_variants" entfernen, falls vorhanden
                        if "title_variants" in q:
                            del q["title_variants"]
                            
                        # 2. Antworttexte befüllen (Neu: content_variants_de als String-Array)
                        for idx, ans_obj in enumerate(answers_obj_list):
                            if isinstance(ans_obj, dict):
                                # Absicherung, falls die KI weniger Antworten liefert als im Original vorhanden
                                v1_ans = varianten["variante_1"]["antworten"][idx] if len(varianten["variante_1"]["antworten"]) > idx else ""
                                v2_ans = varianten["variante_2"]["antworten"][idx] if len(varianten["variante_2"]["antworten"]) > idx else ""
                                
                                ans_obj["content_variants_de"] = [v1_ans, v2_ans]
                                
                                # Alte "content_variants" entfernen, falls vorhanden
                                if "content_variants" in ans_obj:
                                    del ans_obj["content_variants"]
                                    
                        updates_gemacht += 1
                        time.sleep(0.5) # Kurze Pause gegen Rate Limits
                    except (KeyError, IndexError, TypeError) as e:
                        st.warning(f"Warnung bei ID {orig_id}: JSON-Struktur der KI entspricht nicht den Erwartungen ({e})")
                        
            status.update(label="Verarbeitung abgeschlossen!", state="complete", expanded=False)
            
        if updates_gemacht > 0:
            st.success(f"🎉 Fertig! Es wurden {updates_gemacht} Fragen und deren Antworten umformuliert.")
            
            # 3. Download Vorbereitung (Direkt als formatierter JSON-String)
            processed_data = json.dumps(data, ensure_ascii=False, indent=2)
            
            # 4. Download Button
            st.download_button(
                label="📥 Fertige JSON-Datei herunterladen",
                data=processed_data,
                file_name=uploaded_file.name.replace(".json", "_fertig.json"),
                mime="application/json"
            )
        else:
            st.info("Es wurden keine gültigen Fragen zur Bearbeitung gefunden.")
