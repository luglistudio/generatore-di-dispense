#!/usr/bin/env python3
# /// script
# dependencies = [
#   "python-dotenv",
#   "markdown",
#   "jinja2",
#   "notebooklm-py",
# ]
# ///
import os
import sys
import json
import argparse
import subprocess
import tempfile
import re
from pathlib import Path
import datetime
import time
from typing import Union

# Aggiungi la directory corrente al path per importare i moduli locali
sys.path.append(str(Path(__file__).parent))

import config
import prompts
import compiler
from logging_utils import log_info, log_warning, log_error

def clean_notebooklm_citations(text: str) -> str:
    """Rimuove le citazioni quadre di NotebookLM (es. [1], [2-4]) preservando i blocchi codice e formule matematiche."""
    placeholders = {}
    counter = 0
    
    def save_block(match):
        nonlocal counter
        ph = f"__CODE_BLOCK_PH_{counter}__"
        placeholders[ph] = match.group(0)
        counter += 1
        return ph

    # Sostituisci i blocchi ```code```
    text = re.sub(r'```[\s\S]*?```', save_block, text)
    # Sostituisci i blocchi inline code `code`
    text = re.sub(r'`[^`\n]+`', save_block, text)
    # Sostituisci le formule matematiche $$...$$ e $...$
    text = re.sub(r'\$\$[\s\S]*?\$\$', save_block, text)
    text = re.sub(r'\$[^\$\n]+\$', save_block, text)
    
    # Rimuove [1], [1, 2], [1-3] ecc.
    text = re.sub(r'\s*\[\s*\d+(?:[-,\s\d]*)\s*\]', '', text)
    
    # Ripristina i blocchi salvati
    for ph, orig in reversed(list(placeholders.items())):
        text = text.replace(ph, orig)
        
    return text

def load_blueprint_state(state_path: Path) -> dict:
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "step": 1,
        "course_profile": None,
        "chapters_outline": None,
        "course_name": None,
        "chapters": [],
        "completed_chapters": []
    }

def save_blueprint_state(state_path: Path, state: dict):
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_warning(f"⚠️ Errore nel salvataggio dello stato intermedio del blueprint: {e}")

def check_env():
    """Verifica l'autenticazione con NotebookLM."""
    log_info("🔍 Verifica dell'autenticazione con NotebookLM...")
    if not config.check_notebooklm_auth():
        log_error("❌ Errore: Sessione NotebookLM non valida o non trovata.")
        log_error("Esegui prima il comando: notebooklm login")
        sys.exit(1)
    log_info("✅ Autenticazione NotebookLM OK.")

def setup_directories(project_dir: Path):
    """Crea le cartelle necessarie per il progetto."""
    (project_dir / "raw_sources").mkdir(parents=True, exist_ok=True)
    (project_dir / "output").mkdir(parents=True, exist_ok=True)
    (project_dir / "output" / "assets").mkdir(parents=True, exist_ok=True)
    log_info(f"📁 Struttura directory inizializzata in {project_dir}")

def get_output_dir(project_dir: Path, notebook_name: str) -> Path:
    """Restituisce la directory di output specifica per il notebook corrente, sanificandone il nome."""
    if not notebook_name:
        notebook_name = "default"
    # Sostituisce spazi e caratteri speciali con underscore, toglie maiuscole
    safe_name = re.sub(r'[\s_]+', '_', notebook_name.lower().strip())
    safe_name = re.sub(r'[^\w\-]', '', safe_name)
    if not safe_name:
        safe_name = "default"
    
    out_dir = project_dir / "output" / safe_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    return out_dir

def get_or_create_notebook(notebook_name: str) -> str:
    """Verifica se il notebook esiste, altrimenti lo crea, e lo imposta come attivo."""
    log_info(f"🔍 Ricerca del notebook '{notebook_name}'...")
    res = subprocess.run(["notebooklm", "list", "--json"], capture_output=True, text=True)
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            notebooks = []
            if isinstance(data, list):
                notebooks = data
            elif isinstance(data, dict):
                notebooks = data.get("notebooks", []) or data.get("items", []) or []
            
            for nb in notebooks:
                if nb.get("title") == notebook_name:
                    nb_id = nb.get("id")
                    log_info(f"✅ Trovato notebook esistente (ID: {nb_id})")
                    # Imposta come attivo
                    subprocess.run(["notebooklm", "use", nb_id, "--json"], capture_output=True)
                    return nb_id
        except Exception as e:
            log_warning(f"⚠️ Errore nel parsing dei notebook: {e}")

    log_info(f"🆕 Notebook '{notebook_name}' non trovato. Creazione in corso...")
    res = subprocess.run(["notebooklm", "create", notebook_name, "--use", "--json"], capture_output=True, text=True)
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            nb_id = data.get("active_notebook_id") or data.get("notebook_id") or data.get("notebook", {}).get("id")
            if nb_id:
                log_info(f"✅ Notebook creato ed impostato come attivo (ID: {nb_id})")
                return nb_id
        except Exception as e:
            log_warning(f"⚠️ Errore durante la creazione del notebook: {e}")
    
    log_error("❌ Impossibile creare o trovare il notebook.")
    sys.exit(1)

def get_sources_in_notebook() -> list[dict]:
    """Ottiene l'elenco delle sorgenti caricate nel notebook attivo."""
    res = subprocess.run(["notebooklm", "source", "list", "--json"], capture_output=True, text=True)
    if res.returncode != 0:
        log_error(f"❌ Impossibile ottenere l'elenco delle sorgenti: {res.stderr}")
        return []
    try:
        data = json.loads(res.stdout)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("sources", []) or data.get("items", []) or []
    except Exception as e:
        log_error(f"❌ Errore decodifica JSON sorgenti: {e}")
    return []

def upload_new_sources(project_dir: Path):
    """Carica i file da raw_sources/ non ancora presenti nel notebook."""
    raw_dir = project_dir / "raw_sources"
    files_to_upload = sorted([f for f in raw_dir.iterdir() if f.is_file() and not f.name.startswith(".")])
    
    if not files_to_upload:
        log_info("ℹ️ Nessun file trovato in raw_sources/. Aggiungi le trascrizioni o slide per iniziare.")
        return

    existing_sources = get_sources_in_notebook()
    existing_titles = {s.get("title") for s in existing_sources}

    total_files = len(files_to_upload)
    for idx, f in enumerate(files_to_upload, 1):
        progress_str = f"{idx}/{total_files}"
        # Se il file è già caricato (confrontando il titolo), saltalo
        if f.name in existing_titles or f.stem in existing_titles:
            log_info(f"⏭️ [{progress_str}] File '{f.name}' già presente nel notebook, salto il caricamento.")
            continue
        
        log_info(f"📥 [{progress_str}] Caricamento di '{f.name}' su NotebookLM...")
        cmd = ["notebooklm", "source", "add", str(f), "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            log_info(f"✅ [{progress_str}] Caricato con successo: {f.name}")
        else:
            log_error(f"❌ [{progress_str}] Errore durante il caricamento di {f.name}: {res.stderr}")

def ask_notebooklm(
    prompt: str,
    source_ids: list[str] = None,
    max_retries: int = 5,
    conversation_id: str = None,
    new_conversation: bool = False,
    return_full_response: bool = False,
    timeout: int = 300
) -> Union[str, dict]:
    """Interroga NotebookLM salvando il prompt su file temporaneo, con supporto a conversazioni continuative, timeout e backoff esponenziale."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as temp_file:
        temp_file.write(prompt)
        temp_file_path = temp_file.name
    
    try:
        cmd = ["notebooklm", "ask", "--json"]
        if new_conversation:
            cmd += ["--new", "-y"]
        elif conversation_id:
            cmd += ["-c", conversation_id]
            
        if source_ids:
            for s_id in source_ids:
                cmd += ["-s", s_id]
        cmd += ["--prompt-file", temp_file_path]
        
        for attempt in range(1, max_retries + 1):
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                if res.returncode == 0:
                    try:
                        data = json.loads(res.stdout)
                        if return_full_response:
                            return data
                        return data.get("answer", "")
                    except Exception as e:
                        log_error(f"❌ Errore nel parsing della risposta JSON: {e}\nRaw stdout: {res.stdout}")
                        if return_full_response:
                            return {}
                        return ""
                
                log_warning(f"⚠️ Chiamata a NotebookLM fallita (tentativo {attempt}/{max_retries}). Dettaglio: {res.stderr.strip()}")
            except subprocess.TimeoutExpired:
                log_warning(f"⚠️ Timeout scaduto ({timeout}s) durante la chiamata a NotebookLM (tentativo {attempt}/{max_retries}).")
            
            if attempt < max_retries:
                # Backoff esponenziale con jitter basato sull'orologio di sistema (nanosecondi) per evitare collisioni
                jitter = (time.time_ns() % 1000000) / 1000000.0
                sleep_time = min(60, (2 ** attempt) + jitter)
                log_info(f"🕒 Attesa di {sleep_time:.2f} secondi prima di riprovare...")
                time.sleep(sleep_time)
        
        log_error("❌ Raggiunto il limite massimo di tentativi per NotebookLM.")
        if return_full_response:
            return {}
        return ""
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def parse_json_response(answer: str) -> dict:
    """Pulisce e carica una stringa JSON restituita da NotebookLM usando raw_decode per maggiore robustezza."""
    clean_str = answer.strip()
    if clean_str.startswith("```"):
        clean_str = re.sub(r"^```(?:json)?\n", "", clean_str)
        clean_str = re.sub(r"\n```$", "", clean_str)
    try:
        return json.loads(clean_str)
    except Exception as e:
        # Trova la prima parentesi graffa e decodifica usando JSONDecoder.raw_decode
        start_idx = clean_str.find('{')
        if start_idx != -1:
            try:
                decoder = json.JSONDecoder()
                obj, _ = decoder.raw_decode(clean_str, start_idx)
                return obj
            except Exception:
                pass
        raise e

def _step1_profile(project_dir: Path, state: dict, state_path: Path) -> bool:
    """Step 1: Profilazione del corso"""
    log_info("🗺️ [1/5] Analisi e Profilazione didattica delle lezioni/fonti...")
    profile_answer = ask_notebooklm(prompts.COURSE_PROFILER_PROMPT)
    if not profile_answer:
        log_error("❌ Errore: Impossibile generare il profilo del corso.")
        return False
    try:
        course_profile = parse_json_response(profile_answer)
        log_info("   ✅ Profilazione delle fonti completata con successo.")
        state["course_profile"] = course_profile
        state["step"] = 2
        save_blueprint_state(state_path, state)
        return True
    except Exception as e:
        log_error(f"❌ Errore di parsing del profilo del corso: {e}\nRisposta ricevuta:\n{profile_answer}")
        return False

def _step2_chapters(project_dir: Path, state: dict, state_path: Path) -> bool:
    """Step 2: Outlining dei Capitoli"""
    log_info("🗺️ [2/5] Generazione della struttura dei Capitoli principali...")
    course_profile_json = json.dumps(state["course_profile"], indent=2, ensure_ascii=False)
    chapters_prompt = prompts.CHAPTERS_OUTLINE_PROMPT.format(course_profile_json=course_profile_json)
    
    chapters_answer = ask_notebooklm(chapters_prompt)
    if not chapters_answer:
        log_error("❌ Errore: Impossibile generare la struttura dei capitoli.")
        return False
    try:
        chapters_outline = parse_json_response(chapters_answer)
        state["course_name"] = chapters_outline.get("course_name", "Corso")
        state["chapters_outline"] = chapters_outline.get("chapters", [])
        state["step"] = 3
        save_blueprint_state(state_path, state)
        log_info(f"   ✅ Capitoli strutturati per il corso: '{state['course_name']}' ({len(state['chapters_outline'])} capitoli).")
        return True
    except Exception as e:
        log_error(f"❌ Errore di parsing dell'outline dei capitoli: {e}\nRisposta ricevuta:\n{chapters_answer}")
        return False

def _step3_sections(project_dir: Path, state: dict, state_path: Path) -> bool:
    """Step 3: Generazione dettagliata delle Sezioni capitolo per capitolo (con ripresa)"""
    log_info("🗺️ [3/5] Pianificazione dettagliata dei sotto-paragrafi per ciascun capitolo...")
    course_profile_json = json.dumps(state["course_profile"], indent=2, ensure_ascii=False)
    chapters = state["chapters_outline"]
    
    final_chapters = state.get("chapters") or []
    completed_chapters = state.get("completed_chapters") or []
    
    for ch in chapters:
        ch_num = ch.get("chapter_number")
        ch_title = ch.get("title")
        ch_summary = ch.get("summary", "")
        
        if ch_num in completed_chapters:
            log_info(f"   📌 Capitolo {ch_num}: {ch_title} (già pianificato da sessione precedente).")
            continue
            
        log_info(f"   📌 Capitolo {ch_num}: {ch_title}...")
        chapter_sections = []
        has_more = True
        batch_idx = 1
        conversation_id = None
        
        while has_more:
            if chapter_sections:
                existing_sections_str = "\n".join([
                    f"- Sezione {s['section_number']}: {s['title']} (tratta: {s['description']})"
                    for s in chapter_sections
                ])
            else:
                existing_sections_str = "Nessuna sezione pianificata ancora."
                
            sections_prompt = prompts.CHAPTER_SECTIONS_PROMPT.format(
                chapter_number=ch_num,
                chapter_title=ch_title,
                chapter_summary=ch_summary,
                course_profile_json=course_profile_json,
                existing_sections_str=existing_sections_str
            )
            
            if conversation_id:
                response_dict = ask_notebooklm(
                    sections_prompt, 
                    conversation_id=conversation_id, 
                    return_full_response=True
                )
            else:
                response_dict = ask_notebooklm(
                    sections_prompt, 
                    new_conversation=True, 
                    return_full_response=True
                )
                
            if not response_dict or not response_dict.get("answer"):
                log_error(f"      ❌ Errore nella generazione del batch {batch_idx} per il Capitolo {ch_num}.")
                break
                
            answer = response_dict["answer"]
            conversation_id = response_dict.get("conversation_id")
            
            try:
                sections_data = parse_json_response(answer)
                new_sections = sections_data.get("sections", [])
                has_more = sections_data.get("has_more", False)
                
                if not new_sections:
                    log_info("      ℹ️ Nessuna nuova sezione restituita, fine capitolo.")
                    break
                    
                chapter_sections.extend(new_sections)
                log_info(f"      ✅ Batch {batch_idx}: generate {len(new_sections)} sezioni (has_more: {has_more}).")
                batch_idx += 1
            except Exception as e:
                log_error(f"      ❌ Errore di parsing nel batch {batch_idx} per il Capitolo {ch_num}: {e}\nRisposta ricevuta:\n{answer}")
                break
        
        final_chapter = {
            "chapter_number": ch_num,
            "title": ch_title,
            "sections": chapter_sections
        }
        # Rimpiazza se presente
        final_chapters = [c for c in final_chapters if c.get("chapter_number") != ch_num]
        final_chapters.append(final_chapter)
        completed_chapters.append(ch_num)
        
        # Salva lo stato dopo ogni singolo capitolo completato
        state["chapters"] = final_chapters
        state["completed_chapters"] = completed_chapters
        save_blueprint_state(state_path, state)
        
    state["step"] = 4
    save_blueprint_state(state_path, state)
    return True

def _step4_audit(project_dir: Path, state: dict, state_path: Path) -> bool:
    """Step 4: Audit di Copertura del Sillabo & Slide"""
    log_info("\n🗺️ [4/5] Esecuzione Audit di copertura su Sillabo e Slide...")
    course_profile_json = json.dumps(state["course_profile"], indent=2, ensure_ascii=False)
    final_chapters = state["chapters"]
    
    draft_summary = []
    for ch in final_chapters:
        draft_summary.append(f"Capitolo {ch['chapter_number']}: {ch['title']}")
        for s in ch.get("sections", []):
            draft_summary.append(f"  - Sezione {s['section_number']}: {s['title']} (Tratta: {', '.join(s.get('key_concepts', []))})")
    draft_summary_str = "\n".join(draft_summary)
    
    audit_prompt = prompts.SYLLABUS_AUDIT_PROMPT.format(
        draft_summary_str=draft_summary_str,
        course_profile_json=course_profile_json
    )
    
    audit_answer = ask_notebooklm(audit_prompt)
    if audit_answer:
        try:
            audit_data = parse_json_response(audit_answer)
            missing_sections = audit_data.get("missing_sections", [])
            if missing_sections:
                log_warning(f"   ⚠️ L'audit ha rilevato {len(missing_sections)} sezioni mancanti per coprire al 100% il sillabo/slide:")
                for ms in missing_sections:
                    ch_num = ms.get("chapter_number")
                    sec_num = ms.get("section_number")
                    title = ms.get("title")
                    log_info(f"      - Iniezione Sezione {sec_num}: '{title}' nel Capitolo {ch_num}")
                    
                    inserted = False
                    for ch in final_chapters:
                        if ch.get("chapter_number") == ch_num:
                            if not any(s.get("section_number") == sec_num for s in ch.get("sections", [])):
                                ch.get("sections", []).append({
                                    "section_number": sec_num,
                                    "title": title,
                                    "focus_sources": ms.get("focus_sources", []),
                                    "key_concepts": ms.get("key_concepts", []),
                                    "description": ms.get("description", ""),
                                    "target_word_count": ms.get("target_word_count", 1500)
                                })
                                inserted = True
                                break
                    if not inserted:
                        log_warning(f"      ⚠️ Capitolo {ch_num} non trovato, salto iniezione per: {title}")
            else:
                log_info("   ✅ Audit di copertura superato! Nessun argomento d'esame tralasciato.")
        except Exception as e:
            log_warning(f"   ⚠️ Impossibile analizzare l'audit di copertura: {e}. Procedo con la struttura provvisoria.")
            
    # Riordina le sezioni di ciascun capitolo in modo logico (es. 1.1, 1.2, 1.10)
    for ch in final_chapters:
        try:
            ch.get("sections", []).sort(key=lambda s: [int(x) for x in s["section_number"].split(".") if x.isdigit()])
        except Exception:
            pass
            
    state["chapters"] = final_chapters
    state["step"] = 5
    save_blueprint_state(state_path, state)
    return True

def _step5_sources(project_dir: Path, state: dict, state_path: Path, blueprint_path: Path) -> dict:
    """Step 5: Audit Algoritmico delle Fonti (Verifica sorgenti caricate)"""
    log_info("🗺️ [5/5] Verifica algoritmica di mappatura dei file sorgente...")
    final_chapters = state["chapters"]
    all_sources = get_sources_in_notebook()
    
    transcript_sources = [
        s.get("title", "") for s in all_sources 
        if not any(keyword in s.get("title", "").lower() for keyword in ["sillabo", "syllabus", "programma", "index"])
    ]
    
    referenced_sources = set()
    for ch in final_chapters:
        for s in ch.get("sections", []):
            for fs in s.get("focus_sources", []):
                referenced_sources.add(fs.lower())
                
    unreferenced_transcripts = []
    for ts in transcript_sources:
        is_mapped = False
        ts_lower = ts.lower()
        for rs in referenced_sources:
            if rs in ts_lower or ts_lower in rs:
                is_mapped = True
                break
        if not is_mapped:
            unreferenced_transcripts.append(ts)
            
    if unreferenced_transcripts:
        log_warning("\n   ⚠️ ATTENZIONE: Le seguenti sorgenti caricate nel notebook non risultano mappate in nessuna sezione del blueprint:")
        for ut in unreferenced_transcripts:
            log_warning(f"      - {ut}")
        log_warning("   Consigliamo di verificare se mancano argomenti importanti o di aggiungere manualmente queste fonti al blueprint.json prima di avviare la stesura.\n")
    else:
        log_info("   ✅ Tutte le sorgenti caricate sono correttamente mappate a una o più sezioni.")

    blueprint_data = {
        "course_name": state["course_name"],
        "chapters": final_chapters
    }
    
    try:
        with open(blueprint_path, "w", encoding="utf-8") as f:
            json.dump(blueprint_data, f, indent=2, ensure_ascii=False)
        log_info(f"\n🎉 Blueprint finale verificato e salvato correttamente in {blueprint_path}")
        
        # Pulisce lo stato al successo finale
        if state_path.exists():
            os.remove(state_path)
        return blueprint_data
    except Exception as e:
        log_error(f"❌ Errore nel salvataggio del blueprint.json finale: {e}")
        return {}

def generate_blueprint(project_dir: Path, notebook_name: str = "default", force: bool = False, dry_run: bool = False) -> dict:
    """Genera il blueprint del corso in modalità multi-step con supporto a salvataggi intermedi, ripresa automatica e simulazione dry-run."""
    output_dir = get_output_dir(project_dir, notebook_name)
    blueprint_path = output_dir / "blueprint.json"
    state_path = output_dir / "blueprint_state.json"
    
    if force:
        if state_path.exists():
            os.remove(state_path)
            log_info("🔄 [Blueprint] Stato precedente rimosso tramite opzione --force.")
        if blueprint_path.exists():
            os.remove(blueprint_path)
            
    if dry_run:
        log_info("✨ [DRY-RUN] Simulazione generazione del blueprint in corso...")
        all_sources = get_sources_in_notebook()
        log_info(f"   Sorgenti rilevate nel notebook: {len(all_sources)}")
        for s in all_sources:
            log_info(f"      - {s.get('title')}")
        log_info("   [DRY-RUN] Verrebbero eseguiti i 5 step di profilazione, capitoli, sezioni, audit sillabo e verifica fonti.")
        return {}

    state = load_blueprint_state(state_path)
    
    # Step 1: Profilazione del corso
    if state["step"] == 1:
        if not _step1_profile(project_dir, state, state_path):
            return {}
            
    if state["course_profile"]:
        profile_path = output_dir / "course_profile.json"
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(state["course_profile"], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # Step 2: Outlining dei Capitoli
    if state["step"] == 2:
        if not _step2_chapters(project_dir, state, state_path):
            return {}

    # Step 3: Generazione dettagliata delle Sezioni capitolo per capitolo (con ripresa)
    if state["step"] == 3:
        if not _step3_sections(project_dir, state, state_path):
            return {}

    # Step 4: Audit di Copertura del Sillabo & Slide
    if state["step"] == 4:
        if not _step4_audit(project_dir, state, state_path):
            return {}

    # Step 5: Audit Algoritmico delle Fonti (Verifica sorgenti caricate)
    if state["step"] == 5:
        return _step5_sources(project_dir, state, state_path, blueprint_path)
        
    return {}

def find_source_ids_by_names(source_names: list[str], existing_sources: list[dict]) -> list[str]:
    """Mappa i nomi delle sorgenti indicati nel blueprint con gli ID reali in modo non greedy."""
    mapped_ids = []
    for name in source_names:
        found = False
        name_clean = Path(name).stem.lower().strip()
        
        # 1. Tentativo di match esatto (senza estensione e case-insensitive)
        for s in existing_sources:
            title = s.get("title", "")
            title_clean = Path(title).stem.lower().strip()
            if name_clean == title_clean:
                mapped_ids.append(s.get("id"))
                found = True
                break
                
        # 2. Fallback: match parziale escludendo collisioni grossolane (es. "Lezione 1" in "Lezione 10")
        if not found:
            for s in existing_sources:
                title = s.get("title", "")
                title_lower = title.lower()
                name_lower = name.lower()
                
                if (name_lower in title_lower) or (title_lower in name_lower):
                    # Controllo numerico per evitare collisioni greedy
                    num_in_name = re.search(r'\d+$', name_clean)
                    num_in_title = re.search(r'\d+$', title_clean)
                    if num_in_name and num_in_title:
                        if num_in_name.group(0) != num_in_title.group(0):
                            continue
                            
                    mapped_ids.append(s.get("id"))
                    found = True
                    break
                    
        if not found:
            log_warning(f"⚠️ Attenzione: Sorgente '{name}' menzionata nel blueprint non trovata nel notebook.")
    return mapped_ids

def log_progress(sec_num: str, msg: str):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_info(f"[{timestamp}] [Sezione {sec_num}] {msg}")

def write_sections(project_dir: Path, notebook_name: str = "default", force: bool = False, target_section: str = None, dry_run: bool = False):
    """Avvia il loop di stesura dei micro-chunk di ciascuna sezione con supporto dry-run e pulizia sicura delle citazioni."""
    output_dir = get_output_dir(project_dir, notebook_name)
    blueprint_path = output_dir / "blueprint.json"
    if not blueprint_path.exists():
        log_error("❌ Errore: Blueprint non trovato. Generalo prima usando l'azione 'blueprint'.")
        return

    with open(blueprint_path, "r", encoding="utf-8") as f:
        blueprint = json.load(f)

    course_name = blueprint.get("course_name", "Corso")
    
    # Conta il numero totale di sezioni da elaborare (filtrando se target_section è specificato)
    all_sections = []
    total_target_words = 0
    for chapter in blueprint.get("chapters", []):
        for sec in chapter.get("sections", []):
            if not target_section or sec["section_number"] == target_section:
                all_sections.append(sec)
                total_target_words += sec.get("target_word_count", 1500)
    total_sections = len(all_sections)

    if dry_run:
        log_info(f"✨ [DRY-RUN] Simulazione stesura sezioni per il corso: '{course_name}'")
        log_info(f"   Totale sezioni da elaborare: {total_sections}")
        log_info(f"   Target totale parole stimate: {total_target_words} parole")
        log_info("   Dettaglio pianificazione sezioni:")
        
        current_idx = 0
        for chapter in blueprint.get("chapters", []):
            ch_num = chapter["chapter_number"]
            ch_title = chapter["title"]
            log_info(f"     📖 Capitolo {ch_num}: {ch_title}")
            
            for sec in chapter.get("sections", []):
                sec_num = sec["section_number"]
                sec_title = sec["title"]
                if target_section and sec_num != target_section:
                    continue
                current_idx += 1
                clean_sec_num = sec_num.replace(".", "_")
                output_file = output_dir / f"Sezione_{clean_sec_num}.md"
                status = "Esistente (salto)" if output_file.exists() and not force else ("Esistente (sovrascrivo)" if output_file.exists() else "Da creare")
                log_info(f"       [{current_idx}/{total_sections}] Sezione {sec_num}: '{sec_title}'")
                log_info(f"         - Target: {sec.get('target_word_count', 1500)} parole")
                log_info(f"         - Fonti: {', '.join(sec.get('focus_sources', []))}")
                log_info(f"         - Concetti: {', '.join(sec.get('key_concepts', []))}")
                log_info(f"         - Stato file: {status}")
        log_info("\n   [DRY-RUN] Nessun file modificato e nessuna chiamata API effettuata.")
        return

    existing_sources = get_sources_in_notebook()
    current_sec_idx = 0

    for chapter in blueprint.get("chapters", []):
        ch_num = chapter["chapter_number"]
        ch_title = chapter["title"]
        log_info(f"\n📖 Capitolo {ch_num}: {ch_title}")

        sections_in_chapter = chapter.get("sections", [])
        for sec in sections_in_chapter:
            sec_num = sec["section_number"]
            sec_title = sec["title"]
            
            # Se è specificata una sezione target e questa non corrisponde, la saltiamo
            if target_section and sec_num != target_section:
                continue

            current_sec_idx += 1
            progress_str = f"{current_sec_idx}/{total_sections}"

            clean_sec_num = sec_num.replace(".", "_")
            output_file = output_dir / f"Sezione_{clean_sec_num}.md"

            # Checkpoint: evita di sovrascrivere se il file esiste (a meno di --force)
            if output_file.exists() and not force:
                log_progress(sec_num, f"⏭️ [{progress_str}] File '{output_file.name}' già esistente, salto la stesura.")
                continue

            log_progress(sec_num, f"🚀 [{progress_str}] Avvio stesura per: \"{sec_title}\"")
            
            # Mappatura delle fonti specifiche
            focus_sources = sec.get("focus_sources", [])
            source_ids = find_source_ids_by_names(focus_sources, existing_sources)
            
            # Costruisci il prompt compilato per la stesura
            concepts_str = "\n".join([f"- {c}" for c in sec.get("key_concepts", [])])
            prompt_write = prompts.SECTION_WRITER_PROMPT.format(
                section_number=sec_num,
                section_title=sec_title,
                course_name=course_name,
                key_concepts=concepts_str,
                focus_sources=", ".join(focus_sources),
                target_word_count=sec.get("target_word_count", 2000)
            )

            # Esegui la chiamata a NotebookLM restringendo il contesto alle sole fonti mappate
            log_progress(sec_num, f"📡 Invio richiesta a NotebookLM per la bozza principale (fonti: {', '.join(focus_sources)})...")
            section_content = ask_notebooklm(prompt_write, source_ids=source_ids)
            if not section_content:
                log_progress(sec_num, "❌ Errore durante la generazione della bozza principale.")
                continue
            log_progress(sec_num, f"✅ Bozza principale ricevuta ({len(section_content.split())} parole).")

            # Genera materiali QA di supporto ed appendili in coda (solo se è l'ultima sezione del capitolo)
            is_last_section = (sec == sections_in_chapter[-1])
            if is_last_section:
                log_progress(sec_num, f"📡 Invio richiesta a NotebookLM per materiale di autoverifica dell'intero Capitolo {ch_num} (3 flashcard e 1 domanda d'esame)...")
                prompt_qa = prompts.CHAPTER_QA_GENERATOR_PROMPT.format(
                    chapter_number=ch_num,
                    chapter_title=ch_title
                )
                # Attinge a tutto il notebook per il riepilogo del capitolo (source_ids=None)
                qa_content = ask_notebooklm(prompt_qa, source_ids=None)
                if qa_content:
                    log_progress(sec_num, "✅ Materiale di autoverifica del capitolo ricevuto.")
                    section_content += "\n\n---\n\n## 🧠 Materiale di Autoverifica del Capitolo\n\n" + qa_content
                else:
                    log_progress(sec_num, "⚠️ Impossibile generare materiale di autoverifica, proseguo comunque.")

            # Genera Diagramma Mermaid se necessario ed appendilo
            log_progress(sec_num, "📡 Invio richiesta a NotebookLM per diagramma concettuale Mermaid...")
            prompt_mermaid = prompts.MERMAID_PROMPT.format(
                section_number=sec_num,
                section_title=sec_title,
                section_content=section_content
            )
            mermaid_content = ask_notebooklm(prompt_mermaid, source_ids=source_ids)
            if mermaid_content and "```mermaid" in mermaid_content:
                log_progress(sec_num, "✅ Diagramma Mermaid ricevuto.")
                section_content = "## 📊 Diagramma Concettuale\n\n" + mermaid_content + "\n\n" + section_content
            else:
                log_progress(sec_num, "ℹ️ Nessun diagramma Mermaid generato o rilevato.")

            # Pulizia finale dei citation references e immagini markdown
            log_progress(sec_num, "🧹 Esecuzione filtri di pulizia (rimozione parentesi quadre citazioni e tag immagini)...")
            
            # Pulisce citazioni usando il nostro helper sicuro (protegge code/math blocks)
            section_content = clean_notebooklm_citations(section_content)
            
            # Rimuove markdown image tag
            section_content = re.sub(r'!\[.*?\]\(.*?\)', '', section_content)
            # Rimuove apici singoli / backticks attorno ai doppi brackets (es. `[[Concetto]]` -> [[Concetto]])
            section_content = re.sub(r'`\[\[(.*?)\]\]`', r'[[\1]]', section_content)

            # Salva il file markdown della sezione
            with open(output_file, "w", encoding="utf-8") as out_f:
                out_f.write(section_content)
            log_progress(sec_num, f"💾 Sezione salvata in {output_file.name}\n")

def generate_concept_cards(project_dir: Path, notebook_name: str = "default", force: bool = False, chunk_size: int = 5, dry_run: bool = False):
    """Trova tutti i wikilink nelle sezioni generate e crea file markdown dedicati in output/concepts/ in chunk configurabili."""
    log_info("\n📇 Scansione e generazione delle schede concettuali in batch (Obsidian wikilinks)...")
    output_dir = get_output_dir(project_dir, notebook_name)
    concepts_dir = output_dir / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Raccogli tutti i file di sezione (Sezione_*.md)
    section_files = sorted(list(output_dir.glob("Sezione_*.md")))
    if not section_files:
        log_warning(f"⚠️ Nessuna sezione trovata in {output_dir.name}/. Genera prima le sezioni con l'azione 'write'.")
        return
        
    # 2. Cerca tutti i doppi bracket [[Concetto]]
    unique_concepts_map = {} # lower_case -> original_case
    wikilink_regex = re.compile(r'\[\[(.*?)\]\]')
    
    for f_path in section_files:
        with open(f_path, "r", encoding="utf-8") as f:
            text = f.read()
            for match in wikilink_regex.finditer(text):
                concept = match.group(1).split('|')[0].strip()
                concept = Path(concept).name.strip()
                if concept:
                    concept_lower = concept.lower()
                    if concept_lower not in unique_concepts_map:
                        unique_concepts_map[concept_lower] = concept
                        
    # Ricerca ricorsiva per trovare link annidati nei concetti esistenti o generati in precedenza
    scanned_concepts = set()
    while True:
        current_found = list(unique_concepts_map.values())
        new_found_this_iteration = False
        
        for concept in current_found:
            concept_lower = concept.lower()
            if concept_lower in scanned_concepts:
                continue
            scanned_concepts.add(concept_lower)
            
            safe_name = re.sub(r'[\\/*?:"<>|]', "_", concept).strip()
            concept_file = concepts_dir / f"{safe_name}.md"
            if concept_file.exists():
                try:
                    with open(concept_file, "r", encoding="utf-8") as f:
                        text = f.read()
                        for match in wikilink_regex.finditer(text):
                            linked_concept = match.group(1).split('|')[0].strip()
                            linked_concept = Path(linked_concept).name.strip()
                            if linked_concept:
                                linked_lower = linked_concept.lower()
                                if linked_lower not in unique_concepts_map:
                                    unique_concepts_map[linked_lower] = linked_concept
                                    new_found_this_iteration = True
                except Exception:
                    pass
                    
        if not new_found_this_iteration:
            break
        
    # Filtra solo i concetti che devono essere effettivamente generati
    concepts_to_generate = []
    unique_concepts_list = sorted(list(unique_concepts_map.values()))
    
    for concept in unique_concepts_list:
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", concept).strip()
        concept_file = concepts_dir / f"{safe_name}.md"
        if concept_file.exists() and not force:
            continue
        concepts_to_generate.append(concept)
        
    if dry_run:
        log_info(f"✨ [DRY-RUN] Trovati {len(unique_concepts_map)} concetti unici (case-insensitive).")
        log_info(f"   Concetti già esistenti in {concepts_dir.name}: {len(unique_concepts_map) - len(concepts_to_generate)}")
        log_info(f"   Concetti da generare: {len(concepts_to_generate)}")
        if concepts_to_generate:
            chunks_count = (len(concepts_to_generate) + chunk_size - 1) // chunk_size
            log_info(f"   Verrebbero inviati {chunks_count} batch di dimensione max {chunk_size} a NotebookLM.")
            log_info("   Lista dei concetti pianificati per generazione:")
            for c in concepts_to_generate:
                log_info(f"      - {c}")
        log_info("\n   [DRY-RUN] Nessuna chiamata API effettuata e nessun file creato.")
        return

    if not concepts_to_generate:
        log_info(f"ℹ️ Tutte le {len(unique_concepts_map)} schede concettuali sono già esistenti.")
        return
        
    log_info(f"🔍 Trovati {len(unique_concepts_map)} concetti unici (case-insensitive). {len(concepts_to_generate)} da generare.")
    
    # Raggruppa i concetti in chunk configurabili
    chunks = [concepts_to_generate[i:i + chunk_size] for i in range(0, len(concepts_to_generate), chunk_size)]
    total_chunks = len(chunks)
    
    for idx, chunk in enumerate(chunks, 1):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        concepts_str = ", ".join([f'"{c}"' for c in chunk])
        log_info(f"[{timestamp}] [Batch {idx}/{total_chunks}] 📡 Invio richiesta a NotebookLM per i concetti: {concepts_str}...")
        
        # Costruisce l'elenco dei concetti formattato per il prompt
        concepts_list_str = "\n".join([f"- {c}" for c in chunk])
        prompt = prompts.CONCEPT_CHUNK_EXPLORER_PROMPT.format(concepts_list_str=concepts_list_str)
        
        # Interroga NotebookLM (attingendo a tutte le fonti)
        response = ask_notebooklm(prompt)
        if not response:
            log_error(f"   ❌ Errore durante la generazione del batch {idx}/{total_chunks}.")
            continue
            
        # Parsea la risposta separando i concetti tramite "=== CONCEPT:"
        parts = re.split(r'===\s*CONCEPT\s*:', response, flags=re.IGNORECASE)
        saved_count = 0
        
        for part in parts:
            if not part.strip():
                continue
                
            # Il blocco ha il formato: " [Nome Concetto] ===\n[Descrizione]\n=== END ==="
            subparts = part.split("===", 1)
            if len(subparts) < 2:
                continue
                
            c_name = subparts[0].strip()
            c_content = subparts[1].strip()
            
            # Pulisce eventuali tag === END ===
            c_content = re.sub(r'===?\s*END\s*===?', '', c_content, flags=re.IGNORECASE).strip()
            
            if not c_name:
                continue
                
            # Pulisce citazioni di NotebookLM in modo sicuro, tag immagini e backticks intorno ai wikilink
            c_content = clean_notebooklm_citations(c_content)
            c_content = re.sub(r'!\[.*?\]\(.*?\)', '', c_content)
            c_content = re.sub(r'`\[\[(.*?)\]\]`', r'[[\1]]', c_content)
            
            # Trova la corrispondenza esatta nella nostra lista di concetti richiesti (case-insensitive)
            matched_concept = None
            for c in chunk:
                if c.lower() == c_name.lower():
                    matched_concept = c
                    break
            
            # Se non c'è corrispondenza diretta nel chunk, prova a confrontare sanificando
            if not matched_concept:
                matched_concept = c_name
                
            safe_name = re.sub(r'[\\/*?:"<>|]', "_", matched_concept).strip()
            concept_file = concepts_dir / f"{safe_name}.md"
            
            with open(concept_file, "w", encoding="utf-8") as out_f:
                out_f.write(c_content + "\n")
            log_info(f"   💾 Scheda salvata: {concept_file.name}")
            saved_count += 1
        log_info(f"   ✅ Salvate {saved_count} schede per il batch {idx}/{total_chunks}.")
        
    log_info("✅ Generazione schede concettuali completata!")

def create_obsidian_config(project_dir: Path, notebook_name: str = "default"):
    """Crea le configurazioni di base di Obsidian (es. graph view colors) in output/.obsidian/"""
    output_dir = get_output_dir(project_dir, notebook_name)
    obsidian_dir = output_dir / ".obsidian"
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    
    appearance_path = obsidian_dir / "appearance.json"
    if not appearance_path.exists():
        appearance_data = {
            "theme": "obsidian",
            "accentColor": "#3b82f6"
        }
        try:
            with open(appearance_path, "w", encoding="utf-8") as f:
                json.dump(appearance_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
            
    graph_path = obsidian_dir / "graph.json"
    if not graph_path.exists():
        # Configurazione colori del Grafo Obsidian:
        # - Arancione vivace (#ff6c3b) -> 16739387 per i concetti
        # - Blu (#3b82f6) -> 3899638 per le sezioni principali
        graph_data = {
            "collapse-filter": False,
            "search": "",
            "showTags": False,
            "showAttachments": False,
            "hideUnresolved": False,
            "showOrphans": True,
            "loop": False,
            "forceDecay": 100,
            "nodeSizeMultiplier": 1.5,
            "lineThicknessMultiplier": 1,
            "connectionStrength": 1,
            "linkDistance": 100,
            "colorGroups": [
                {
                    "query": "path:concepts",
                    "color": {
                        "a": 1,
                        "rgb": 16739387
                    }
                },
                {
                    "query": "file:Sezione_",
                    "color": {
                        "a": 1,
                        "rgb": 3899638
                    }
                }
            ],
            "colorGroupsEnabled": True
        }
        try:
            with open(graph_path, "w", encoding="utf-8") as f:
                json.dump(graph_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

def select_notebook_terminal() -> str:
    """Interroga la CLI per ottenere i notebook esistenti e mostra un menu interattivo nel terminale."""
    log_info("🔍 Recupero della lista dei notebook su NotebookLM...")
    res = subprocess.run(["notebooklm", "list", "--json"], capture_output=True, text=True)
    notebooks = []
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            if isinstance(data, list):
                notebooks = data
            elif isinstance(data, dict):
                notebooks = data.get("notebooks", []) or data.get("items", []) or []
        except Exception:
            pass

    if not notebooks:
        name = input("Nessun notebook trovato. Inserisci il nome del nuovo notebook da creare: ").strip()
        if not name:
            name = "Dispensa_Corso_Autonoma"
        return name

    options = ["[Crea un nuovo notebook...]"] + [nb.get("title") for nb in notebooks if nb.get("title")]
    
    import sys
    if sys.stdin.isatty():
        try:
            import tty
            import termios
            
            def getch():
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    ch = sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                return ch
                
            selected = 0
            while True:
                # Pulisce lo schermo
                sys.stdout.write("\x1b[2J\x1b[H")
                sys.stdout.write("\x1b[36m=== SELEZIONA IL NOTEBOOK DA USARE ===\x1b[0m\n\n")
                for i, opt in enumerate(options):
                    if i == selected:
                        sys.stdout.write(f"  \x1b[1;32m>\x1b[0m \x1b[1;37m{opt}\x1b[0m\n")
                    else:
                        sys.stdout.write(f"    {opt}\n")
                sys.stdout.write("\n(Usa le frecce ⬆️/⬇️ per navigare, premi INVIO per selezionare)\n")
                sys.stdout.flush()
                
                ch = getch()
                if ch in ('\r', '\n'):
                    break
                elif ch == '\x1b':
                    ch2 = getch()
                    ch3 = getch()
                    if ch2 == '[':
                        if ch3 == 'A':
                            selected = (selected - 1) % len(options)
                        elif ch3 == 'B':
                            selected = (selected + 1) % len(options)
            
            sys.stdout.write("\n\n")
            sys.stdout.flush()
            
            if selected == 0:
                name = input("Inserisci il nome del nuovo notebook da creare: ").strip()
                return name if name else "Dispensa_Corso_Autonoma"
            else:
                return options[selected]
        except Exception:
            pass

    # Fallback standard
    print("\n=== NOTEBOOK DISPONIBILI ===")
    for i, opt in enumerate(options):
        print(f"[{i}] {opt}")
    
    try:
        scelta = input(f"\nInserisci il numero desiderato (0-{len(options)-1}): ").strip()
        idx = int(scelta)
        if idx == 0:
            name = input("Inserisci il nome del nuovo notebook: ").strip()
            return name if name else "Dispensa_Corso_Autonoma"
        elif 0 < idx < len(options):
            return options[idx]
    except Exception:
        pass
        
    return "Dispensa_Corso_Autonoma"

def main():
    parser = argparse.ArgumentParser(description="Generatore Autonomo di Dispense via NotebookLM CLI")
    parser.add_argument(
        "-a", "--action",
        choices=["init", "blueprint", "write", "concepts", "compile", "all"],
        default="all",
        help="Azione da compiere: init (cartelle), blueprint (sillabo), write (stesura), concepts (schede concetti), compile (assemblaggio PDF), all (tutto in sequenza)."
    )
    parser.add_argument(
        "-n", "--notebook-name",
        default="Dispensa_Corso_Autonoma",
        help="Nome del notebook di NotebookLM da usare o creare."
    )
    parser.add_argument(
        "--section",
        default=None,
        help="Specifica una singola sezione da rigenerare (es. '1.1'). Funziona solo con l'azione 'write'."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forza la riscrittura delle sezioni già generate o la rigenerazione del blueprint."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula le operazioni senza chiamare le API di NotebookLM."
    )
    parser.add_argument(
        "--concept-chunk-size",
        type=int,
        default=5,
        help="Dimensione massima dei batch di concetti da generare simultaneamente (default: 5)."
    )
    args = parser.parse_args()

    project_dir = Path(__file__).parent.resolve()
    
    # Se il notebook non è esplicitato negli argomenti CLI, lo facciamo selezionare interattivamente
    if "-n" not in sys.argv and "--notebook-name" not in sys.argv and args.action != "init" and args.action != "compile":
        args.notebook_name = select_notebook_terminal()

    # 1. Inizializzazione cartelle e controllo Auth
    if args.action == "init":
        setup_directories(project_dir)
        check_env()
        return

    # Esegui controlli preliminari per le altre azioni
    check_env()
    setup_directories(project_dir)
    create_obsidian_config(project_dir, args.notebook_name)
    
    # Assicura il notebook e carica i file
    get_or_create_notebook(args.notebook_name)
    upload_new_sources(project_dir)

    # 2. Generazione del Blueprint
    if args.action in ["blueprint", "all"]:
        output_dir = get_output_dir(project_dir, args.notebook_name)
        blueprint_path = output_dir / "blueprint.json"
        if not blueprint_path.exists() or args.force or args.action == "blueprint":
            generate_blueprint(project_dir, notebook_name=args.notebook_name, force=args.force, dry_run=args.dry_run)

    # 3. Micro-stesura delle sezioni
    if args.action in ["write", "all"]:
        write_sections(project_dir, notebook_name=args.notebook_name, force=args.force, target_section=args.section, dry_run=args.dry_run)

    # 3b. Generazione delle schede concettuali
    if args.action in ["concepts", "all"]:
        generate_concept_cards(
            project_dir,
            notebook_name=args.notebook_name,
            force=args.force,
            chunk_size=args.concept_chunk_size,
            dry_run=args.dry_run
        )

    # 4. Compilazione della dispensa
    if args.action in ["compile", "all"] and not args.dry_run:
        log_info("\n🗂️ Compilazione della dispensa finale in corso...")
        output_dir = get_output_dir(project_dir, args.notebook_name)
        blueprint_path = output_dir / "blueprint.json"
        res = compiler.compile_dispensa(blueprint_path, output_dir)
        if res["success"]:
            log_info(f"🎉 Compilazione completata con successo!")
            log_info(f"📝 Markdown: {res['markdown_path']}")
            log_info(f"🌐 HTML: {res['html_path']}")
            if res["pdf_path"]:
                log_info(f"📄 PDF ({res['pdf_method']}): {res['pdf_path']}")
            else:
                log_info(f"ℹ️ {res['msg']}")
        else:
            log_error(f"❌ Errore di compilazione: {res['error']}")

if __name__ == "__main__":
    main()
