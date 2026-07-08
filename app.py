import streamlit as st
from openai import OpenAI
import json
import io

# --- SEITENKONFIGURATION ---
st.set_page_config(page_title="Bruno di Brun JSON App", page_icon="🎓", layout="centered")

# --- API KEY SETUP ---
try:
    API_KEY = st.secrets["OPENAI_API_KEY"]
    client = OpenAI(api_key=API_KEY)
except KeyError:
    st.error("Fehler: API-Key nicht gefunden. Bitte richte die Streamlit Secrets ein.")
    st.stop()

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
Du bist ein Experte für das Umformulieren von Multiple-Choice-Prüfungsfragen im Versicherungswesen.
Deine Regeln:
1. Formuliere die Frage (Title) und JEDE einzelne Antwortmöglichkeit sprachlich komplett neu.
2. Behalte den fachlichen Inhalt und die Bedeutung strikt bei.
3. Fachbegriffe (VAG, FINMA etc.) bleiben unangetastet.
4. Gib das Ergebnis AUSSCHLIESSLICH als JSON im folgenden Format zurück:
{
  "title_variants": ["Variante 1 der Frage", "Variante 2 der Frage"],
  "answer_variants": [ 
      ["Antwort A Variante 1", "Antwort A Variante 2"], 
      ["Antwort B Variante 1", "Antwort B Variante 2"]
  ]
}
Stelle sicher, dass die Liste in 'answer_variants' exakt dieselbe Länge wie die Anzahl der Eingabe-Antworten hat.
"""

def generiere_varianten(frage, antworten_liste):
    """Sendet Frage und Antworten an OpenAI und erhält JSON mit Varianten."""
    prompt = f"Original Frage: {frage}\nOriginal Antworten: {', '.join(antworten_liste)}"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.7,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Fehler bei API-Abfrage: {e}")
        return None

# --- STREAMLIT UI ---
st.title("🎓 Bruno di Brun JSON App")
st.markdown("Lade dein `data_import.json` hoch. Das Tool generiert für jede Frage und jede Antwort neue Varianten.")

uploaded_file = st.file_uploader("Wähle eine JSON-Datei", type=['json'])

if uploaded_file is not None:
    data = json.load(uploaded_file)
    st.success("JSON erfolgreich geladen!")

    if st.button("🚀 Verarbeitung starten", type="primary"):
        with st.status("Verarbeite Fragen...", expanded=True) as status:
            questions = data.get("questions", [])
            
            for i, q in enumerate(questions):
                st.write(f"Verarbeite Frage {i+1}/{len(questions)}: {q.get('title')[:30]}...")
                
                # Extrahiere aktuelle Inhalte
                orig_title = q.get("title")
                orig_answers = [a.get("content") for a in q.get("answers", [])]
                
                # API Call
                result = generiere_varianten(orig_title, orig_answers)
                
                if result:
                    # Update JSON Struktur
                    q["title_variants"] = result.get("title_variants", [])
                    
                    # Update Antworten
                    for idx, a in enumerate(q.get("answers", [])):
                        # Sicherstellen, dass Index existiert
                        if idx < len(result.get("answer_variants", [])):
                            a["content_variants"] = result.get("answer_variants")[idx]
            
            status.update(label="Verarbeitung abgeschlossen!", state="complete", expanded=False)
            st.success("Fertig! Die Datei ist bereit für den Download.")

        # --- Download Vorbereitung ---
        json_output = json.dumps(data, indent=2, ensure_ascii=False)
        
        st.download_button(
            label="💾 Fertige JSON-Datei herunterladen",
            data=json_output,
            file_name="data_fertig.json",
            mime="application/json"
        )
