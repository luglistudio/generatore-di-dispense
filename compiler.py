import os
import subprocess
import shutil
import json
from pathlib import Path
import datetime
import html
import re
import markdown
from jinja2 import Template
from logging_utils import log_info, log_warning, log_error

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>{{ course_name }} - Dispensa Completa</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({ startOnLoad: true, theme: 'default' });
    </script>
    <!-- MathJax per il rendering delle equazioni in LaTeX -->
    <script>
        window.MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
            }
        };
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --text: #1f2937;
            --bg: #ffffff;
            --light-bg: #f9fafb;
            --border: #e5e7eb;
            --muted: #6b7280;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            color: var(--text);
            background: var(--bg);
            line-height: 1.6;
            margin: 0;
            padding: 0;
        }


        .container {
            max-width: 850px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        /* Copertina per la stampa */
        .cover {
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            border-bottom: 2px solid var(--border);
            page-break-after: always;
        }

        .cover h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 3.5rem;
            color: var(--primary);
            margin-bottom: 10px;
        }

        .cover h2 {
            font-size: 1.8rem;
            color: var(--muted);
            font-weight: 400;
            margin-top: 0;
        }

        .cover .meta {
            margin-top: 50px;
            font-size: 1.1rem;
            color: var(--muted);
        }

        /* Elementi del testo */
        h1, h2, h3, h4 {
            font-family: 'Outfit', sans-serif;
            color: #111827;
        }

        h1 {
            font-size: 2.5rem;
            border-bottom: 2px solid var(--border);
            padding-bottom: 10px;
            margin-top: 40px;
            page-break-before: always;
        }

        h2 {
            font-size: 1.8rem;
            margin-top: 30px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 5px;
        }

        h3 {
            font-size: 1.4rem;
            margin-top: 20px;
        }

        /* Tabelle in MD */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: var(--light-bg);
        }

        table th, table td {
            border: 1px solid var(--border);
            padding: 12px 15px;
            text-align: left;
        }

        table th {
            background-color: #f3f4f6;
            font-weight: 600;
        }

        /* Citazioni */
        blockquote {
            border-left: 4px solid var(--primary);
            padding: 10px 20px;
            margin: 20px 0;
            background-color: var(--light-bg);
            font-style: italic;
            color: #374151;
        }

        /* Immagini */
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
            border-radius: 6px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        /* Codeblock e diagrammi */
        pre {
            background-color: var(--light-bg);
            border: 1px solid var(--border);
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
        }

        code {
            font-family: monospace;
            background-color: #f3f4f6;
            padding: 2px 4px;
            border-radius: 4px;
            font-size: 0.9em;
        }

        pre code {
            background-color: transparent;
            padding: 0;
        }

        /* Stile per l'Indice dei Contenuti (TOC) */
        .toc {
            background-color: var(--light-bg);
            border: 1px solid var(--border);
            padding: 24px;
            border-radius: 8px;
            margin: 30px 0;
            page-break-after: always;
        }

        .toc ul {
            list-style-type: none;
            padding-left: 20px;
        }

        .toc > ul {
            padding-left: 0;
        }

        .toc li {
            margin: 10px 0;
            line-height: 1.4;
        }

        .toc a {
            color: var(--primary);
            text-decoration: none;
            font-weight: 500;
        }

        .toc a:hover {
            color: var(--primary-dark);
            text-decoration: underline;
        }

        /* Regole per la stampa PDF */
        @media print {
            body {
                background: white;
                font-size: 11pt;
            }
            .container {
                max-width: 100%;
                padding: 0;
            }
            h1 {
                page-break-before: always;
            }
            blockquote, pre, table, img {
                page-break-inside: avoid;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Copertina -->
        <div class="cover">
            <h1>{{ course_name }}</h1>
            <h2>Dispensa Universitaria Completa</h2>
            <div class="meta">
                <p>Generato autonomamente tramite Pipeline NotebookLM</p>
                <p>Data Generazione: {{ date_str }}</p>
            </div>
        </div>

        <!-- Contenuto della Dispensa -->
        <div class="content">
            {{ content_html }}
        </div>
    </div>
</body>
</html>
"""

def compile_dispensa(blueprint_path: Path, output_dir: Path) -> dict:
    """Assembra tutti i chunk markdown e genera il file finale MD, HTML e PDF."""
    if not blueprint_path.exists():
        return {"success": False, "error": f"Blueprint non trovato in {blueprint_path}"}

    with open(blueprint_path, "r", encoding="utf-8") as f:
        blueprint = json.load(f)

    course_name = blueprint.get("course_name", "Corso")
    
    # 1. Ricomposizione del file Markdown cumulativo
    combined_md = []
    combined_md.append(f"# {course_name}\n\n*Dispensa Completa del Corso*\n\n---\n\n")
    
    # Inserisci il segnaposto per la Table of Contents (TOC)
    combined_md.append("## Indice dei Contenuti\n\n[TOC]\n\n---\n\n")

    for chapter in blueprint.get("chapters", []):
        ch_num = chapter["chapter_number"]
        ch_title = chapter["title"]
        combined_md.append(f"# Capitolo {ch_num}: {ch_title}\n\n")

        for sec in chapter.get("sections", []):
            sec_num = sec["section_number"]
            sec_title = sec["title"]
            
            # Cerca il file markdown corrispondente
            clean_sec_num = sec_num.replace(".", "_")
            chunk_file = output_dir / f"Sezione_{clean_sec_num}.md"
            
            if chunk_file.exists():
                with open(chunk_file, "r", encoding="utf-8") as cf:
                    content = cf.read().strip()
                combined_md.append(f"## {sec_title}\n\n{content}\n\n\n\n")
            else:
                combined_md.append(f"## {sec_title}\n\n*Contenuto in fase di stesura o non generato.*\n\n")

    # Scrivi il file markdown unificato
    final_md_path = output_dir / "dispensa_completa.md"
    with open(final_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(combined_md))

    # 2. Generazione del file HTML
    today_str = datetime.date.today().strftime("%d-%m-%Y")
    
    # Converti MD in HTML con estensioni utili (tabelle, blocchi di codice, blocchi con attributi, TOC)
    md_parser = markdown.Markdown(
        extensions=["tables", "fenced_code", "attr_list", "toc"],
        extension_configs={
            "toc": {
                "toc_depth": "1-2"
            }
        }
    )
    content_html = md_parser.convert("\n".join(combined_md[1:])) # Salta il titolo h1 per inserire la copertina

    # Pulisci e converti i blocchi Mermaid in modo che Mermaid.js possa renderizzarli nel browser
    def clean_mermaid(match):
        code = match.group(1)
        # Decodifica le entità HTML (es. &gt; in >) per far funzionare la sintassi Mermaid
        code = html.unescape(code)
        return f'<div class="mermaid">{code}</div>'
        
    content_html = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        clean_mermaid,
        content_html,
        flags=re.DOTALL
    )

    # Converti i wikilink Obsidian [[Concetto]] in semplice testo in grassetto
    # Gestendo anche alias (es. [[Concetto|Testo Alternativo]]) e percorsi (es. [[path/to/Concetto]])
    def render_wikilink(match):
        inner = match.group(1).strip()
        if '|' in inner:
            display_text = inner.split('|', 1)[1].strip()
        else:
            display_text = Path(inner).name.strip()
        return f'<strong>{display_text}</strong>'

    content_html = re.sub(r'\[\[(.*?)\]\]', render_wikilink, content_html)

    template = Template(HTML_TEMPLATE)
    rendered_html = template.render(
        course_name=course_name,
        date_str=today_str,
        content_html=content_html
    )

    final_html_path = output_dir / "dispensa_completa.html"
    with open(final_html_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    # 3. Compilazione in PDF (se ci sono i compilatori sul sistema)
    pdf_generated = False
    pdf_method = None
    final_pdf_path = output_dir / "dispensa_completa.pdf"

    # Tentativo A: Weasyprint
    if shutil.which("weasyprint"):
        try:
            log_info("🚀 Rilevato Weasyprint. Compilazione in corso...")
            subprocess.run(
                ["weasyprint", str(final_html_path), str(final_pdf_path)],
                check=True,
                capture_output=True
            )
            pdf_generated = True
            pdf_method = "Weasyprint"
        except subprocess.SubprocessError as e:
            log_warning(f"⚠️ Errore durante la compilazione con Weasyprint: {e}")

    # Tentativo B: Google Chrome / Chromium (Altamente consigliato su Mac/PC per il rendering perfetto di font/JS)
    if not pdf_generated:
        chrome_path = None
        mac_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(mac_chrome):
            chrome_path = mac_chrome
        elif shutil.which("google-chrome"):
            chrome_path = shutil.which("google-chrome")
        elif shutil.which("chromium"):
            chrome_path = shutil.which("chromium")

        if chrome_path:
            try:
                log_info("🚀 Rilevato Google Chrome. Compilazione in corso...")
                # --virtual-time-budget=5000 permette a MathJax e Mermaid di completare il rendering JavaScript prima della stampa
                subprocess.run([
                    chrome_path,
                    "--headless",
                    "--disable-gpu",
                    f"--print-to-pdf={final_pdf_path}",
                    "--virtual-time-budget=5000",
                    str(final_html_path)
                ], check=True, capture_output=True)
                pdf_generated = True
                pdf_method = "Google Chrome (Headless)"
            except subprocess.SubprocessError as e:
                log_warning(f"⚠️ Errore durante la compilazione con Google Chrome: {e}")

    # Tentativo C: Typst / Pandoc fallbacks
    if not pdf_generated and shutil.which("pandoc"):
        # Controlla se pandoc-pdf-engine è presente (solitamente pdflatex o xelatex)
        try:
            log_info("🚀 Rilevato Pandoc. Tentativo di compilazione PDF tramite LaTeX...")
            subprocess.run(
                ["pandoc", str(final_md_path), "-o", str(final_pdf_path), "--pdf-engine=xelatex"],
                check=True,
                capture_output=True
            )
            pdf_generated = True
            pdf_method = "Pandoc (XeLaTeX)"
        except subprocess.SubprocessError:
            # Riprova con pdflatex standard
            try:
                subprocess.run(
                    ["pandoc", str(final_md_path), "-o", str(final_pdf_path)],
                    check=True,
                    capture_output=True
                )
                pdf_generated = True
                pdf_method = "Pandoc"
            except subprocess.SubprocessError as e:
                log_warning(f"⚠️ Errore durante la compilazione con Pandoc: {e}")

    return {
        "success": True,
        "markdown_path": str(final_md_path),
        "html_path": str(final_html_path),
        "pdf_path": str(final_pdf_path) if pdf_generated else None,
        "pdf_method": pdf_method,
        "msg": "Compilazione completata. Puoi aprire il file HTML nel browser e stamparlo in PDF se il compilatore automatico non è installato." if not pdf_generated else "PDF generato con successo."
    }
