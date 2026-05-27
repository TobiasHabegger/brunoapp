import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import time
import io

# --- SEITENKONFIGURATION ---
st.set_page_config(page_title="Bruno di Brun App", page_icon="🎓", layout="centered")

# --- API KEY & CLIENT SETUP ---
# Greift sicher auf die Streamlit Secrets zu
try:
    API_KEY = st.secrets["OPENAI_API_KEY"]
    client = OpenAI(api_key=API_KEY)
except KeyError:
    st.error("Fehler: API-Key nicht gefunden. Bitte richte die Streamlit Secrets ein.")
    st.stop()

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
Du bist ein hochpräziser KI-Agent für das automatisierte Umformulieren von Multiple-Choice-Prüfungsfragen. 
DEINE AUFGABE:
Der User übergibt dir eine Originalfrage inklusive aller Antwortmöglichkeiten. Du erstellst daraus exakt ZWEI neue, sprachlich und strukturell unterschiedliche Varianten, welche weiterhin exakt dieselbe Kompetenz und denselben Fachinhalt prüfen.
VORGABEN ZUR UMFORMULIERUNG:
1. Sprachliche Variation: Verwende neue Satzstrukturen, abwechslungsreiche Verbformen und Synonyme für allgemeine Begriffe. Verzichte auf verschachtelte oder zu komplexe Sätze.
2. Reihenfolge der Antworten (ABSOLUT ZWINGEND): Die Reihenfolge der Antwortmöglichkeiten MUSS in den beiden neuen Varianten exakt mit der Reihenfolge der Originalvorgabe übereinstimmen. Antwort 1 im Original muss Antwort 1 in deinen Varianten bleiben usw.
3. Fachbegriffe: Versicherungsspezifische Begriffe und terminologisch übliche Begriffe dürfen NICHT verändert werden! 
4. Abkürzungen: Versicherungsspezifische Abkürzungen sind auszuschreiben und die Abkürzung ist in Klammern mitzugeben.
5. Namen: Wenn im Original ein Name vorkommt, ändere diesen in den Varianten.
6. Anspruchsniveau: Erhöhe, wo möglich, das Anspruchsniveau der Fragen leicht, ohne den Lehrplan-Kontext zu verlassen.
7. Fallszenarien: Nutze zur Abwechslung bei mindestens einer Variante ein Fallszenario.
8. Zeitform: Alle Antwortoptionen innerhalb einer Variante müssen in der gleichen Zeitform formuliert sein.
9. Sprache: Schweizer Hochdeutsch (ä, ö, ü ausschreiben, kein ß sondern ss).
10. Geschlechtergerechte Sprache: Verwende zwingend die gekürzte Doppelbezeichnung mit Schrägstrich (z.B. Käufer/-in).

OUTPUT-FORMAT (ZWINGEND):
Du antwortest AUSSCHLIESSLICH mit einem validen JSON-Objekt.
{
  "variante_1": {
    "frage": "...",
    "antworten": ["Antwort 1", "Antwort 2", "..."]
  },
  "variante_2": {
    "frage": "...",
    "antworten": ["Antwort 1", "Antwort 2", "..."]
  }
}
"""

def generiere_varianten(frage, antworten_liste):
    """Sendet die Frage und Antworten an die OpenAI API."""
    user_content = f"FRAGE:\n{frage}\n\nANTWORTEN:\n"
    for idx, ans in enumerate(antworten_liste):
        user_content += f"Antwort {idx + 1}: {ans}\n"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o", # Empfohlen für JSON und System Prompts
            response_format={ "type": "json_object" }, 
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
st.title("🎓 Bruno di Brun App")
st.markdown("""
Lade hier deine Excel-Liste hoch. Das Tool analysiert die bestehenden Fragen und generiert pro Frage **zwei neue, methodisch korrekte Varianten** mithilfe von KI.
""")

# 1. Datei Upload Widget
uploaded_file = st.file_uploader("Wähle eine Excel-Datei (.xlsx)", type=['xlsx'])

if uploaded_file is not None:
    st.success(f"Datei '{uploaded_file.name}' erfolgreich geladen!")
    
    # 2. Button zum Starten
    if st.button("🚀 Verarbeitung starten", type="primary"):
        
        with st.status("Verarbeite Excel-Datei...", expanded=True) as status:
            df = pd.read_excel(uploaded_file)
            df['questions/id'] = df['questions/id'].astype(str)
            
            # Zählen wie viele Fragen wir bearbeiten müssen (für die Progress Bar)
            total_rows = len(df)
            updates_gemacht = 0
            
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Verarbeitungs-Schleife
            for i in range(len(df)):
                # Fortschritt aktualisieren
                progress_bar.progress((i + 1) / total_rows)
                
                if pd.notna(df.iloc[i].get('questions/title')):
                    if i + 2 < len(df) and pd.isna(df.iloc[i+1].get('questions/title')) and pd.isna(df.iloc[i+2].get('questions/title')):
                        
                        orig_id = str(df.iloc[i]['questions/id']).replace('.0', '')
                        frage = df.iloc[i]['questions/title']
                        
                        antworten_liste = []
                        for j in range(6):
                            col = f'questions/answers/{j}/content'
                            if col in df.columns and pd.notna(df.iloc[i][col]):
                                antworten_liste.append(df.iloc[i][col])
                        
                        status_text.write(f"⏳ Verarbeite ID {orig_id}: {frage[:40]}...")
                        varianten = generiere_varianten(frage, antworten_liste)
                        
                        # --- NEU: DIAGNOSE-FENSTER ---
                        with st.expander(f"KI-Output für ID {orig_id} ansehen"):
                            st.json(varianten)
                        # -----------------------------
                        
                        if varianten:
                            try:
                                df.at[i+1, 'questions/id'] = f"{orig_id}.1"
                                df.at[i+1, 'questions/title'] = varianten['variante_1']['frage']
                                for idx, neue_antwort in enumerate(varianten['variante_1']['antworten']):
                                    if idx < 6:
                                        df.at[i+1, f'questions/answers/{idx}/content'] = neue_antwort
                                
                                df.at[i+2, 'questions/id'] = f"{orig_id}.2"
                                df.at[i+2, 'questions/title'] = varianten['variante_2']['frage']
                                for idx, neue_antwort in enumerate(varianten['variante_2']['antworten']):
                                    if idx < 6:
                                        df.at[i+2, f'questions/answers/{idx}/content'] = neue_antwort
                                        
                                updates_gemacht += 1
                                time.sleep(0.5) # Kurze Pause gegen Rate-Limits
                            except KeyError as e:
                                st.warning(f"Warnung bei ID {orig_id}: JSON-Struktur nicht wie erwartet ({e})")
            
            status.update(label="Verarbeitung abgeschlossen!", state="complete", expanded=False)

        if updates_gemacht > 0:
            st.success(f"🎉 Fertig! Es wurden {updates_gemacht} Fragen umformuliert.")
            
            # 3. Download Vorbereitung (In Memory)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            processed_data = output.getvalue()
            
            # 4. Download Button
            st.download_button(
                label="📥 Fertige Excel-Datei herunterladen",
                data=processed_data,
                file_name=uploaded_file.name.replace(".xlsx", "_Fertig.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Es wurden keine leeren Zeilen zur Generierung gefunden. Bitte prüfe die Struktur deiner Excel-Datei.")
