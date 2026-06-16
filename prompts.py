# Template dei Prompt per il Generatore di Dispense

COURSE_PROFILER_PROMPT = """
Analizza tutte le fonti caricate in questo notebook (trascrizioni, slide, capitoli) e compila un'analisi dettagliata degli argomenti trattati.

Identifica in modo specifico:
1. Quali argomenti principali sono stati trattati e in quali file/trascrizioni audio.
2. Per ciascun argomento, stima l'enfasi/tempo dedicato dal professore nelle lezioni (es. "Molto Alto" se trattato in più lezioni, "Alto" se trattato in un'intera lezione, "Medio" se trattato in mezza lezione, "Basso" se solo accennato).
3. I concetti chiave correlati.

Rispondi esclusivamente in formato JSON valido con questa struttura:
{
  "topics": [
    {
      "name": "Nome dell'argomento",
      "sources": ["Nome_Sorgente_A", "Nome_Sorgente_B"],
      "emphasis": "Molto Alto / Alto / Medio / Basso",
      "key_concepts": ["Concetto 1", "Concetto 2"],
      "description": "Breve descrizione del focus del professore su questo argomento."
    }
  ]
}
"""

CHAPTERS_OUTLINE_PROMPT = """
Analizza il profilo del corso fornito di seguito e le fonti caricate nel notebook. Crea una struttura di capitoli di alto livello per organizzare la dispensa del corso.
La dispensa deve essere organizzata per capitoli tematici che riflettano l'ordine didattico.

Profilo del Corso:
{course_profile_json}

Rispondi esclusivamente in formato JSON valido con questa struttura:
{
  "course_name": "Nome ufficiale del corso",
  "chapters": [
    {
      "chapter_number": 1,
      "title": "Titolo del Capitolo 1",
      "summary": "Riassunto concettuale di cosa coprirà questo capitolo."
    }
  ]
}
"""

CHAPTER_SECTIONS_PROMPT = """
Sei un progettista accademico. Basandoti sulle fonti del notebook e sul profilo del corso, progetta il prossimo blocco di sotto-paragrafi (sezioni) di dettaglio per il **Capitolo {chapter_number}: {chapter_title}**.

Profilo del Corso:
{course_profile_json}

Il capitolo tratta: {chapter_summary}

Sezioni già pianificate finora per questo capitolo:
{existing_sections_str}

Pianifica le PROSSIME sezioni di dettaglio (al massimo 5 in questo turno), partendo dopo l'ultima sezione già pianificata.
Per ciascuna sezione, assegna un target di parole per la stesura (da 1000 a 3000 parole) direttamente proporzionale all'enfasi/tempo dedicato nelle lezioni (es. un argomento con enfasi "Molto Alto" riceverà 2500-3000 parole, uno con "Basso" riceverà 1000-1200 parole).

Rispondi esclusivamente in formato JSON valido con questa struttura:
{{
  "sections": [
    {{
      "section_number": "{chapter_number}.N",
      "title": "Titolo della Sezione",
      "focus_sources": ["Nome_Sorgente_A", "Nome_Sorgente_B"],
      "key_concepts": ["Concetto chiave 1", "Concetto chiave 2"],
      "description": "Descrizione dettagliata del focus e degli argomenti specifici da trattare.",
      "target_word_count": 2000
    }}
  ],
  "has_more": true / false
}}

Se ci sono altri argomenti di questo capitolo ancora da trattare e pianificare nelle fonti, imposta "has_more" a true. Se hai completato la pianificazione del capitolo, imposta "has_more" a false.
"""

SECTION_WRITER_PROMPT = """
Sei un redattore accademico senior esperto nella stesura di dispense universitarie e testi di studio ad alto valore aggiunto. 

Il tuo compito è scrivere la sezione "{section_number}: {section_title}" per la dispensa del corso "{course_name}".

I concetti chiave da trattare in questa sezione sono:
{key_concepts}

Usa le seguenti sorgenti caricate come contesto unico e vincolante (il testo delle trascrizioni lezioni e dei materiali integrativi come slide/libri):
- Sorgenti di riferimento: {focus_sources}

LINEE GUIDA CRITICHE PER LA STESURA:
1. **Estensione e Dettaglio**: Scrivi una trattazione estesa, approfondita e discorsiva (target specifico di circa {target_word_count} parole per questa sezione). Evita riassunti generici o sintesi stringate. Sviluppa ogni concetto in paragrafi esaustivi proporzionalmente a questa lunghezza.
2. **Filtro Esame (Rilevanza)**: Usa le slide e il sillabo ufficiale come guida su ciò che è d'esame. Se nella trascrizione dell'audio il professore fa digressioni personali, battute, commenti amministrativi o aneddoti irrilevanti per lo studio teorico, ignorali o condensali al minimo. Concentrati sui concetti accademici.
3. **Integrazione delle Fonti**: Fondi la spiegazione verbale del professore (con i suoi esempi esplicativi ed analogie utili a far capire il concetto) con le definizioni formali e rigorose presenti nelle slide o nel libro di testo.
4. **Formattazione & Strumenti Visivi**:
   - Usa tabelle in formato Markdown standard per riassumere differenze, classificazioni o dati strutturati.
   - Usa blocchi di codice LaTeX (es. `$formula$` o `$$formula$$`) per formule matematiche, logiche o economiche.
   - Inserisci citazioni letterali significative tratte dalla trascrizione audio usando il blocco di citazione (`> "[Citazione]" — Prof. [Cognome]`).
5. **Collegamenti Obsidian**: Riferisci i concetti cardine o le persone citate racchiudendoli tra doppi brackets `[[Concetto]]` (es. `[[Spinoza]]`, `[[Legge Naturale]]`), per consentire la creazione del grafo semantico in Obsidian. *IMPORTANTE: Scrivi i brackets direttamente nel testo, non racchiuderli MAI in backticks o codice inline (es. NON scrivere `[[Franz Boas]]` con accenti gravi, scrivi semplicemente [[Franz Boas]] direttamente).*

Inizia a scrivere direttamente il testo della sezione in formato Markdown, senza preamboli come "Ecco la sezione..." o titoli duplicati a livello di capitolo.
"""

QA_GENERATOR_PROMPT = """
Sei un docente universitario esperto nella materia di questo corso.
Basandoti sulle fonti caricate in questo notebook per la sezione "{section_number}: {section_title}" (in particolare le trascrizioni e le slide corrispondenti), genera due blocchi di materiali di supporto per lo studio:
1. **Flashcard stile Anki**: Crea una lista di sole 2 o 3 flashcard domanda/risposta sui dettagli più complessi o nozionistici. Formattale esattamente in questo modo:
   **D**: [Domanda chiara e concisa]
   **R**: [Risposta precisa e approfondita]
   ---
2. **Domande d'Esame Simulate**: Crea 1 domanda a risposta aperta tipica di un esame universitario, con relative soluzione ideale e dettagliata.

Rispondi in formato Markdown pronto da appendere in coda alla sezione, senza introduzioni o commenti di servizio.
"""

MERMAID_PROMPT = """
Basandoti sulle fonti caricate in questo notebook per la sezione "{section_number}: {section_title}", individua le relazioni concettuali, i processi sequenziali o le strutture tassonomiche principali che trarrebbero giovamento da una rappresentazione visiva.
Genera un diagramma in sintassi **Mermaid.js** (es. `graph TD`, `flowchart LR`, ecc.).

Regole:
- Genera SOLO il diagramma Mermaid racchiuso all'interno di un blocco di codice ```mermaid ... ```.
- Se la sezione non ha bisogno di grafici, rispondi con stringa vuota.
- Mantieni le etichette dei nodi brevi e racchiuse tra virgolette per evitare errori di sintassi (es. `A["Etnocentrismo"]`).
- Non inserire spiegazioni di testo prima o dopo il blocco di codice Mermaid.
"""

CONCEPT_CHUNK_EXPLORER_PROMPT = """
Sei un assistente accademico esperto e un tutor didattico.
Basandoti sulle fonti caricate in questo notebook, scrivi una scheda sintetica/definizione di circa 100-200 parole per ciascuno dei seguenti concetti o persone:
{concepts_list_str}

Per ciascun concetto, rispondi usando ESATTAMENTE questa struttura per consentirci di dividere le schede in automatico:

=== CONCEPT: [Nome Concetto] ===
[Spiegazione in modo chiaro e rigoroso di cos'è il concetto, come si colloca nella materia di questo corso, ed eventuali esempi o definizioni chiave fornite dal professore o dai testi di riferimento. Circa 100-200 parole.]

=== END ===

IMPORTANTE:
- Rispondi direttamente in formato Markdown seguendo questa struttura per tutti i concetti richiesti, senza preamboli, saluti o introduzioni.
- Non racchiudere MAI i link Obsidian [[Concetto]] tra apici o backticks (es. NON scrivere `[[Concetto]]` ma [[Concetto]]).
"""

SYLLABUS_AUDIT_PROMPT = """
Sei un ispettore accademico senior. Il tuo compito è verificare che la struttura provvisoria della dispensa copra il 100% degli argomenti del sillabo ufficiale, delle slide del corso e delle trascrizioni delle lezioni.

Struttura provvisoria pianificata:
{draft_summary_str}

Profilo didattico del corso:
{course_profile_json}

Analizza attentamente tutte le fonti caricate (in particolare il sillabo, il programma d'esame e le slide). Identifica eventuali argomenti cardine, concetti d'esame o parti del programma che NON sono coperti o che sono stati trascurati nella struttura provvisoria.

Rispondi esclusivamente in formato JSON valido con questa struttura:
{{
  "missing_sections": [
    {{
      "chapter_number": 1,
      "section_number": "1.4",
      "title": "Titolo della Sezione Mancante",
      "focus_sources": ["Nome_Sorgente_A"],
      "key_concepts": ["Concetto mancante 1", "Concetto mancante 2"],
      "description": "Descrizione dettagliata di cosa manca e perché deve essere integrato.",
      "target_word_count": 1500
    }}
  ]
}}

Se non manca nulla e il programma è coperto al 100%, rispondi con una lista "missing_sections" vuota.
"""



