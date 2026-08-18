import os
import json
import time
import uuid
import sys
import threading
from typing import Any, Dict, Iterator, List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel


APP_TITLE = "Admissions Assistant API"
APP_VERSION = "1.0.0"
MODEL_ID = "admissions-rag"
UI_TITLE = "Admissions Assistant"
BASELINE_UNIVERSITY = "University of Liverpool"
BASELINE_PROGRAMME = "Computer Science BSc"


def _force_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


_force_utf8_stdio()


def _load_summary_metrics() -> Dict[str, Any]:
        summary_path = os.getenv("EVALUATION_SUMMARY_PATH", "evaluation_summary.csv")
        if not os.path.exists(summary_path):
                return {
                        "available": False,
                        "source": summary_path,
                }

        try:
                with open(summary_path, "r", encoding="utf-8") as handle:
                        lines = [line.strip() for line in handle.readlines() if line.strip()]
                if len(lines) < 2:
                        return {"available": False, "source": summary_path}

                headers = lines[0].split(",")
                values = lines[1].split(",")
                metrics = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
                metrics["available"] = True
                metrics["source"] = summary_path
                return metrics
        except Exception as exc:
                return {
                        "available": False,
                        "source": summary_path,
                        "error": str(exc),
                }


def _render_ui_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{UI_TITLE}</title>
    <style>
        :root {{
            --paper: #d8dfdc;
            --paper-deep: #c3ccc8;
            --ink: #1d2628;
            --soft: #f3f5f3;
            --rule: rgba(29, 38, 40, 0.74);
            --muted: rgba(29, 38, 40, 0.58);
            --shadow: rgba(9, 14, 16, 0.22);
            --accent: #4a6257;
            --accent-strong: #34473f;
            --accent-soft: #cfd8d3;
            --highlight: #87988b;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: "Palatino Linotype", "Book Antiqua", Georgia, serif;
            background:
                radial-gradient(circle at top left, rgba(255,255,255,0.58), transparent 22%),
                radial-gradient(circle at right 20%, rgba(74,98,87,0.06), transparent 22%),
                linear-gradient(180deg, #dde3e0 0%, #c5ceca 100%);
            color: var(--ink);
            min-height: 100vh;
            line-height: 1.45;
        }}
        .frame {{
            max-width: 1340px;
            margin: 26px auto;
            padding: 12px;
        }}
        .board {{
            position: relative;
            border: 3px solid var(--rule);
            border-radius: 18px;
            background:
                linear-gradient(135deg, rgba(74,98,87,0.05), transparent 34%),
                linear-gradient(180deg, #f6f8f5 0%, #e8edea 100%);
            box-shadow: 0 28px 70px var(--shadow);
            padding: 18px;
        }}
        .board::before, .board::after {{
            content: "";
            position: absolute;
            inset: 7px;
            border: 1px solid rgba(74, 98, 87, 0.12);
            border-radius: 13px;
            pointer-events: none;
        }}
        .title-row {{
            display: grid;
            grid-template-columns: 1.1fr 2.1fr 0.9fr;
            gap: 18px;
            margin-bottom: 20px;
            align-items: end;
            padding: 6px 6px 18px;
            border-bottom: 1px solid rgba(74, 98, 87, 0.12);
        }}
        .title {{
            text-align: left;
            font-size: 28px;
            letter-spacing: 0.04em;
            font-weight: 700;
            margin: 0 0 4px;
            color: #2a3537;
            text-transform: uppercase;
        }}
        .subtitle {{
            margin: 0;
            color: var(--muted);
            font-size: 13px;
        }}
        .layout {{
            display: grid;
            grid-template-columns: 0.95fr 1.65fr 0.8fr;
            gap: 20px;
            min-height: 72vh;
        }}
        .pane {{
            position: relative;
            border: 2.5px solid var(--rule);
            border-radius: 18px;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.84), rgba(243,245,243,0.94)),
                var(--soft);
            padding: 20px 18px;
            overflow: hidden;
        }}
        .pane::after {{
            content: "";
            position: absolute;
            inset: 6px;
            border: 1px solid rgba(74, 98, 87, 0.10);
            border-radius: 10px;
            pointer-events: none;
        }}
        .section-title {{
            margin: 0 0 18px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(74, 98, 87, 0.12);
            font-size: 18px;
            font-weight: 700;
            color: #2a3537;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}
        .label {{
            display: block;
            font-size: 12px;
            margin-bottom: 9px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
        }}
        .field, .textarea, .select {{
            width: 100%;
            border: 2px solid var(--rule);
            border-radius: 10px;
            background: #fffefc;
            color: var(--ink);
            padding: 10px 12px;
            font: inherit;
            outline: none;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.9);
        }}
        .field:focus, .textarea:focus, .select:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px rgba(74,98,87,0.10); }}
        .field, .select {{ height: 43px; }}
        .textarea {{ min-height: 170px; resize: vertical; line-height: 1.65; }}
        .stack {{ display: grid; gap: 18px; }}
        .control-group {{ margin-bottom: 22px; }}
        .checkboxes {{ display: grid; gap: 10px; margin-top: 8px; }}
        .checkboxes label {{ display: flex; align-items: center; gap: 10px; font-size: 14px; line-height: 1.4; }}
        .checkboxes input {{ width: 17px; height: 17px; accent-color: var(--accent); }}
        .dropdown-arrow {{
            position: relative;
        }}
        .dropdown-arrow::after {{
            content: "▼";
            position: absolute;
            right: 14px;
            top: 38px;
            font-size: 10px;
            pointer-events: none;
        }}
        .button-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; }}
        .button {{
            border: 2px solid var(--rule);
            border-radius: 999px;
            background: linear-gradient(180deg, #f8faf7 0%, #e4eae7 100%);
            color: var(--ink);
            padding: 11px 18px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            font-size: 12px;
            cursor: pointer;
            box-shadow: 0 6px 16px rgba(10, 26, 34, 0.08);
        }}
        .button.primary {{ background: linear-gradient(180deg, var(--accent) 0%, var(--accent-strong) 100%); color: #f6fffb; border-color: var(--accent-strong); }}
        .button:hover {{ transform: translateY(-1px); filter: brightness(1.01); }}
        .summary-box {{
            border: 2px solid var(--rule);
            border-radius: 16px;
            background: linear-gradient(180deg, #f8faf8 0%, #eaefec 100%);
            padding: 18px 18px 16px;
            box-shadow: inset 0 0 0 1px rgba(74, 98, 87, 0.06);
            min-height: 142px;
        }}
        .summary-box h3 {{ margin: 0 0 14px; font-size: 15px; color: #2a3537; letter-spacing: 0.06em; text-transform: uppercase; }}
        .summary-list {{ margin: 0; padding-left: 22px; display: grid; gap: 9px; }}
        .summary-list li {{ line-height: 1.45; }}
        .chat-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; font-size: 13px; color: var(--muted); }}
        .tag {{
            border: 1px solid rgba(31, 26, 22, 0.22);
            border-radius: 999px;
            padding: 6px 10px;
            background: rgba(255,255,255,0.55);
        }}
        .conversation {{
            min-height: 320px;
            padding: 0;
            background: transparent;
            border: 0;
        }}
        .answer-card {{
            border: 2px solid var(--rule);
            border-radius: 16px;
            background: linear-gradient(180deg, #f8faf8 0%, #e8eeea 100%);
            padding: 18px;
            min-height: 210px;
            white-space: pre-wrap;
            line-height: 1.72;
            font-size: 15px;
        }}
        .answer-card .muted {{ color: var(--muted); }}
        .summary-content {{ display: grid; gap: 12px; }}
        .summary-intro {{ margin: 0 0 2px; font-weight: 700; color: var(--accent-strong); }}
        .priority-section {{
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            background: rgba(255,255,255,0.72);
            padding: 12px 14px;
        }}
        .priority-heading {{ margin: 0 0 6px; font-size: 16px; color: var(--accent-strong); }}
        .priority-detail {{ margin: 0; white-space: normal; }}
        .priority-winner {{ margin: 8px 0 0; font-weight: 700; color: var(--ink); }}
        .priority-reason {{ margin: 4px 0 0; color: var(--muted); font-size: 14px; }}
        .recommendation {{
            border: 2px solid var(--accent);
            border-radius: 10px;
            background: var(--accent-soft);
            padding: 14px;
            font-weight: 700;
        }}
        .recommendation-heading {{ margin: 0 0 4px; font-size: 16px; color: var(--accent-strong); }}
        .citations {{ display: grid; gap: 10px; margin-top: 10px; }}
        .citation {{
            padding: 12px 0;
            border-bottom: 1px solid rgba(22, 122, 90, 0.16);
            font-size: 14px;
        }}
        .citation a {{ color: var(--accent-strong); font-weight: 700; text-decoration: underline; }}
        .citation button {{
            border: 0;
            background: transparent;
            color: var(--accent-strong);
            font: inherit;
            font-weight: 700;
            text-decoration: underline;
            padding: 0;
            cursor: pointer;
        }}
        .summary-link {{ color: var(--accent-strong); font-weight: 700; text-decoration: underline; }}
        .citation strong {{ display: inline-block; min-width: 34px; }}
        .modal-backdrop {{
            position: fixed;
            inset: 0;
            background: rgba(16, 24, 28, 0.62);
            display: none;
            align-items: center;
            justify-content: center;
            padding: 24px;
            z-index: 40;
        }}
        .modal-backdrop.open {{ display: flex; }}
        .modal-card {{
            width: min(860px, 100%);
            max-height: 80vh;
            overflow: auto;
            border: 2px solid var(--rule);
            border-radius: 18px;
            background: linear-gradient(180deg, #fffefb 0%, #eef4f1 100%);
            padding: 20px;
            box-shadow: 0 20px 50px var(--shadow);
        }}
        .modal-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 12px; }}
        .modal-title {{ margin: 0; font-size: 18px; font-weight: 700; }}
        .modal-close {{
            border: 2px solid var(--rule);
            border-radius: 999px;
            background: linear-gradient(180deg, #fffefb 0%, #eef5f2 100%);
            color: var(--ink);
            padding: 6px 12px;
            cursor: pointer;
            font-weight: 700;
        }}
        .modal-meta {{ font-size: 13px; color: var(--muted); margin-bottom: 12px; }}
        .modal-content {{
            border: 1px solid rgba(22, 122, 90, 0.16);
            border-radius: 10px;
            background: #fffefc;
            padding: 16px;
            white-space: pre-wrap;
            line-height: 1.65;
            font-size: 14px;
        }}
        .verify {{
            margin-top: 18px;
            font-style: italic;
            font-size: 14px;
            color: var(--muted);
        }}
        .status-line {{ margin-top: 14px; font-size: 13px; color: var(--muted); }}
        .board-footer {{ text-align: center; margin-top: 10px; font-size: 13px; color: var(--muted); }}
        @media (max-width: 1100px) {{
            .title-row, .layout {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="frame">
        <div class="board">
            <div class="title-row">
                <div></div>
                <div>
                    <h1 class="title">Admissions Tutor Dashboard</h1>
                </div>
                <div></div>
            </div>

            <div class="layout">
                <section class="pane">
                    <h2 class="section-title">Admissions Tutor Input</h2>
                    <div class="control-group">
                        <label class="label" for="targetProgramme">Target Programme:</label>
                        <input id="targetProgramme" class="field" type="text" value="Computer Science BSc - University of Liverpool" readonly />
                    </div>

                    <div class="control-group dropdown-arrow">
                        <label class="label" for="competitorUniversity">Competitor University:</label>
                        <select id="competitorUniversity" class="select">
                            <option>University of Leeds</option>
                            <option>University of Sheffield</option>
                            <option>University of Manchester</option>
                            <option>Lancaster University</option>
                            <option>University of Nottingham</option>
                            <option>University of Birmingham</option>
                            <option>Newcastle University</option>
                            <option>Liverpool John Moores University</option>
                            <option>Manchester Metropolitan University</option>
                            <option>Queen Mary University London</option>
                        </select>
                    </div>

                    <div class="control-group">
                        <label class="label">Student Priorities:</label>
                        <div class="checkboxes">
                            <label><input id="priorityEntryRequirements" type="checkbox" checked /> Entry Requirements</label>
                            <label><input id="priorityCurriculumAccreditation" type="checkbox" checked /> Curriculum &amp; Accreditation</label>
                            <label><input id="priorityGraduateOutcomes" type="checkbox" checked /> Graduate Outcomes &amp; Salary</label>
                            <label><input id="priorityFeesAndCost" type="checkbox" /> Fees &amp; Cost</label>
                            <label><input id="priorityTeachingQuality" type="checkbox" /> Teaching Quality &amp; NSS</label>
                            <label><input id="priorityRankings" type="checkbox" /> University Rankings</label>
                        </div>
                    </div>

                    <div class="control-group">
                        <label class="label" for="question">Tutor prompt:</label>
                        <textarea id="question" class="textarea">Compare the target programme against the selected competitor university using the selected priorities and return a short decision summary.</textarea>
                    </div>

                    <div class="button-row">
                        <button class="button primary" onclick="submitQuery()">Compare</button>
                        <button class="button" onclick="loadDefaults()">Reset</button>
                    </div>
                </section>

                <section class="pane">
                    <h2 class="section-title">Comparison Summary</h2>
                    <div class="summary-box">
                        <h3>Comparison Summary:</h3>
                        <div class="answer-card conversation" id="response">
                            <div class="muted">Your verified comparison will appear here.</div>
                        </div>
                    </div>
                </section>

                <section class="pane">
                    <h2 class="section-title">Citations</h2>
                    <div class="citations" id="sources">
                        <div class="citation"><strong>[1]</strong> Prospectus 2024</div>
                        <div class="citation"><strong>[2]</strong> UCAS Data</div>
                        <div class="citation"><strong>[3]</strong> Vector DB Doc #42</div>
                    </div>
                    <div class="verify">Click to verify →</div>
                </section>
            </div>
        </div>
    </div>

    <div class="modal-backdrop" id="citationModal" onclick="closeCitationModal(event)">
        <div class="modal-card" onclick="event.stopPropagation()">
            <div class="modal-head">
                <div>
                    <h3 class="modal-title" id="citationModalTitle">Citation evidence</h3>
                    <div class="modal-meta" id="citationModalMeta"></div>
                </div>
                <button class="modal-close" onclick="closeCitationModal()">Close</button>
            </div>
            <div class="modal-content" id="citationModalContent"></div>
        </div>
    </div>

    <script>
        const defaultApiKey = 'openwebui-local-key';
        const state = {{ summary: null, citations: [] }};

        function authHeaders() {{
            const key = defaultApiKey;
            return {{ 'Authorization': `Bearer ${{key}}`, 'Content-Type': 'application/json' }};
        }}

        function loadDefaults() {{
            document.getElementById('targetProgramme').value = 'Computer Science BSc - University of Liverpool';
            document.getElementById('competitorUniversity').value = 'University of Leeds';
            document.getElementById('priorityEntryRequirements').checked = true;
            document.getElementById('priorityCurriculumAccreditation').checked = true;
            document.getElementById('priorityGraduateOutcomes').checked = true;
            document.getElementById('priorityFeesAndCost').checked = false;
            document.getElementById('priorityTeachingQuality').checked = false;
            document.getElementById('priorityRankings').checked = false;
            document.getElementById('question').value = 'Compare the target programme against the selected competitor university using the selected priorities and return a short decision summary.';
        }}

        function escapeHtml(text) {{
            return String(text || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }}

        function citationLabel(source, index, providedLabel) {{
            const fallback = `Source ${{index + 1}}`;
            if (providedLabel) return providedLabel;
            if (!source) return fallback;
            if (source.startsWith('SQLite:')) return 'Structured admissions database';
            if (source.includes('knowledge_base')) return 'Vector DB Doc #42';
            return source.replace(/^https?:\/\//, '').replace(/\/.*$/, '') || fallback;
        }}

        function linkSummaryCitations(answer) {{
            const escaped = escapeHtml(answer || '');
            return escaped.replace(/\[(\d+)\]/g, (_, n) => `<a class="summary-link" href="#" onclick="openCitationByNumber(${{Number(n)}}); return false;">[${{n}}]</a>`);
        }}

        function formatComparisonSummary(answer) {{
            const raw = String(answer || '').replace(/\\r?\\n/g, ' ').trim();
            if (!raw) return '<div class="muted">No answer returned.</div>';

            let body = raw.replace(/^Decision summary:\s*/i, '');
            let recommendation = '';
            const recommendationMatch = body.match(/Overall recommendation:\s*(.*?)(?=\s*\[\d+\]|$)/i);
            if (recommendationMatch) {{
                recommendation = recommendationMatch[1].trim().replace(/[.]+$/, '');
                body = body.slice(0, recommendationMatch.index).replace(/[|\s]+$/, '').trim();
            }}

            const sections = body.split(/\s*\|\s*/).filter(Boolean);
            const rendered = sections.map((section) => {{
                const match = section.match(/^([^:]+):\s*(.*)$/);
                if (!match) return `<p class="priority-detail">${{linkSummaryCitations(section)}}</p>`;

                const heading = match[1].trim();
                let detail = match[2].trim();
                let winner = '';
                let reason = '';
                const winnerMatch = detail.match(/\s*Winner:\s*(.*?)(?=\.\s*(?:Higher|Lower|Both|A-level|The current|$))/i);
                if (winnerMatch) {{
                    winner = winnerMatch[1].trim();
                    detail = detail.slice(0, winnerMatch.index).trim();
                    const remainder = match[2].slice(winnerMatch.index + winnerMatch[0].length).trim();
                    reason = remainder.replace(/^\.\s*/, '').trim();
                }}

                return `<section class="priority-section">
                    <h4 class="priority-heading">${{escapeHtml(heading)}}</h4>
                    <p class="priority-detail">${{linkSummaryCitations(detail)}}</p>
                    ${{winner ? `<p class="priority-winner">Winner: ${{linkSummaryCitations(winner)}}</p>` : ''}}
                    ${{reason ? `<p class="priority-reason">${{linkSummaryCitations(reason)}}</p>` : ''}}
                </section>`;
            }}).join('');

            const recommendationHtml = recommendation
                ? `<section class="recommendation"><h4 class="recommendation-heading">Overall Recommendation</h4><div>${{linkSummaryCitations(recommendation)}}</div></section>`
                : '';
            return `<div class="summary-content">${{rendered}}${{recommendationHtml}}</div>`;
        }}

        function openCitationByNumber(number) {{
            const item = (state.citations || [])[number - 1];
            if (!item) return;
            document.getElementById('citationModalTitle').textContent = `[${{number}}] ${{item.label || `Source ${{number}}`}}`;
            const metaParts = [];
            if (item.source) metaParts.push(item.source);
            if (item.url) metaParts.push(item.url);
            document.getElementById('citationModalMeta').textContent = metaParts.join(' | ');
            document.getElementById('citationModalContent').textContent = item.content || item.snippet || 'No evidence text available.';
            document.getElementById('citationModal').classList.add('open');
        }}

        function closeCitationModal(event) {{
            if (event && event.target && event.target.id !== 'citationModal') return;
            document.getElementById('citationModal').classList.remove('open');
        }}

        function renderCitations(result) {{
            const container = document.getElementById('sources');
            const citations = (result.citations || []).filter(Boolean);
            state.citations = citations;

            if (!citations.length) {{
                container.innerHTML = '<div class="citation"><strong>[1]</strong> No citations returned.</div>';
                return;
            }}

            container.innerHTML = citations.map((item, index) => {{
                const source = item.source || '';
                const label = escapeHtml(citationLabel(source, index, item.label || ''));
                const snippet = item.snippet ? escapeHtml(item.snippet.length > 180 ? `${{item.snippet.slice(0, 180)}}...` : item.snippet) : '';
                const external = item.url ? `<div style="margin-top:6px;"><a href="${{escapeHtml(item.url)}}" target="_blank" rel="noreferrer">Open source page</a></div>` : '';
                return `<div class="citation" id="citation-${{index + 1}}"><strong>[${{index + 1}}]</strong> <button onclick="openCitationByNumber(${{index + 1}})">${{label}}</button>${{snippet ? `<div style="margin-top:6px;color:var(--muted);font-size:13px;">${{snippet}}</div>` : ''}}${{external}}</div>`;
            }}).join('');
        }}

        function setSummaryText(result) {{
            const response = document.getElementById('response');
            const answer = result.answer || 'No answer returned.';
            response.innerHTML = formatComparisonSummary(answer);
            renderCitations(result);
        }}

        async function refreshStatus() {{
            return;
        }}

        async function submitQuery() {{
            const targetProgramme = 'Computer Science BSc';
            const baselineUniversity = 'University of Liverpool';
            const competitorUniversity = document.getElementById('competitorUniversity').value.trim();
            const priorities = [
                document.getElementById('priorityEntryRequirements').checked ? 'Entry Requirements (A-level requirement, entry tariff UCAS points, % entrants via A-level, foundation year availability)' : null,
                document.getElementById('priorityCurriculumAccreditation').checked ? 'Curriculum & Accreditation (BCS accreditation, final year project credits, placement year, year abroad)' : null,
                document.getElementById('priorityGraduateOutcomes').checked ? 'Graduate Outcomes & Salary (median salary LEO 3-year, LEO 5-year, graduate outcomes salary, employment rate 15 months, % professional/managerial jobs)' : null,
                document.getElementById('priorityFeesAndCost').checked ? 'Fees & Cost (UK tuition fee, international tuition fee)' : null,
                document.getElementById('priorityTeachingQuality').checked ? 'Teaching Quality & NSS (NSS teaching satisfaction, NSS mental wellbeing, NSS facilities, TEF overall rating, TEF student experience)' : null,
                document.getElementById('priorityRankings').checked ? 'University Rankings (Guardian rank, CUG rank, QS world rank)' : null,
            ].filter(Boolean);
            const additionalInstruction = document.getElementById('question').value.trim();

            const promptParts = [
                `Compare the target programme "${{targetProgramme}}" from "${{baselineUniversity}}" against the selected competitor university "${{competitorUniversity || 'N/A'}}" using the selected priorities (${{priorities.join(', ') || 'none'}}) and return a short decision summary.`
            ];
            if (additionalInstruction) {{
                promptParts.push(`Additional tutor instruction: ${{additionalInstruction}}`);
            }}
            const tutorPrompt = promptParts.join('\\n');

            document.getElementById('response').textContent = 'Generating comparison summary...';

            try {{
                const response = await fetch('/api/chat', {{
                    method: 'POST',
                    headers: authHeaders(),
                    body: JSON.stringify({{
                        question: tutorPrompt,
                        target_programme: targetProgramme,
                        baseline_university: baselineUniversity,
                        competitor_university: competitorUniversity,
                        priorities: priorities,
                        additional_instruction: additionalInstruction,
                    }}),
                }});
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || 'Request failed');
                setSummaryText(result);
            }} catch (error) {{
                document.getElementById('response').textContent = `Request failed: ${{error.message}}`;
            }}
        }}

        refreshStatus();
        setInterval(refreshStatus, 12000);
    </script>
</body>
</html>""".format(UI_TITLE=UI_TITLE)
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_val = item.get("text", "")
                if isinstance(text_val, str):
                    chunks.append(text_val)
        return "\n".join(chunks).strip()

    return ""


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_val = item.get("text", "")
                if isinstance(text_val, str):
                    chunks.append(text_val)
        return "\n".join(chunks).strip()

    return ""


def _get_latest_user_message(messages: List["ChatMessage"]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            text = _extract_text_content(msg.content)
            if text:
                return text
    return ""


def _sanitize_tutor_prompt(text: str) -> str:
    if not text:
        return ""

    sanitized = text
    blocked_phrases = [
        "Compare only these two universities.",
        "Compare only University of Liverpool Computer Science BSc with the selected competitor university.",
    ]
    for phrase in blocked_phrases:
        sanitized = sanitized.replace(phrase, "")

    sanitized = " ".join(sanitized.split())
    return sanitized.strip()


def _check_api_key(auth_header: Optional[str]) -> None:
    expected = os.getenv("API_AUTH_KEY", "openwebui-local-key")

    # Keep auth optional if explicitly disabled for trusted internal networks.
    if os.getenv("DISABLE_API_AUTH", "false").lower() == "true":
        return

    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    provided = auth_header.split(" ", 1)[1].strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str = MODEL_ID
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.0
    stream: Optional[bool] = False
    user: Optional[str] = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: Dict[str, str]
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Dict[str, int]


def _to_chat_completion(
    completion_id: str,
    created: int,
    answer: str,
    query: str,
) -> ChatCompletionResponse:
    prompt_tokens = max(1, len(query.split()))
    completion_tokens = max(1, len(answer.split()))

    return ChatCompletionResponse(
        id=completion_id,
        object="chat.completion",
        created=created,
        model=MODEL_ID,
        choices=[
            ChatCompletionChoice(
                index=0,
                message={"role": "assistant", "content": answer},
                finish_reason="stop",
            )
        ],
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )


def _stream_completion_chunks(completion_id: str, created: int, answer: str) -> Iterator[str]:
    words = answer.split()
    if not words:
        words = [""]

    for i, word in enumerate(words):
        token = f"{word} " if i < len(words) - 1 else word
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": token},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(payload)}\n\n"

    final_payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final_payload)}\n\n"
    yield "data: [DONE]\n\n"


app = FastAPI(title=APP_TITLE, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_rag_instance: Any = None
_rag_lock = threading.Lock()
_rag_prewarm_started = False


def _get_rag() -> Any:
    global _rag_instance
    if _rag_instance is None:
        with _rag_lock:
            if _rag_instance is None:
                from rag_orchestrator import AdmissionsRAGOrchestrator

                _rag_instance = AdmissionsRAGOrchestrator(
                    db_directory=os.getenv("CHROMA_DB_PATH", "./chroma_db"),
                    sql_db_path=os.getenv("SQL_DB_PATH", "./admissions_structured.db"),
                )
    return _rag_instance


def _prewarm_rag() -> None:
    global _rag_prewarm_started
    if _rag_prewarm_started:
        return
    _rag_prewarm_started = True

    def _worker() -> None:
        try:
            _get_rag()
        except Exception:
            pass

    threading.Thread(target=_worker, name="rag-prewarm", daemon=True).start()


@app.get("/")
def root() -> HTMLResponse:
    return HTMLResponse(_render_ui_html())


@app.on_event("startup")
def startup_event() -> None:
    _prewarm_rag()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/summary")
def api_summary() -> Dict[str, Any]:
    return _load_summary_metrics()


@app.post("/api/chat")
def api_chat(
    payload: Dict[str, Any],
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _check_api_key(authorization)

    question = _sanitize_tutor_prompt(str(payload.get("question", "")).strip())
    target_programme = BASELINE_PROGRAMME
    baseline_university = BASELINE_UNIVERSITY
    competitor_university = str(payload.get("competitor_university", "")).strip()
    additional_instruction = _sanitize_tutor_prompt(str(payload.get("additional_instruction", "")).strip())
    priorities = payload.get("priorities", [])
    if not question:
        raise HTTPException(status_code=400, detail="Missing question")

    # Map priority labels to the DB column groups they cover, so the SQL router fires correctly.
    _PRIORITY_COLUMN_HINTS = {
        "Entry Requirements": "entry tariff alevel_requirement UCAS points a-level requirement foundation year",
        "Curriculum & Accreditation": "bcs accredited final year project credits placement year year abroad",
        "Graduate Outcomes & Salary": "median salary employment rate professional managerial LEO 3-year 5-year",
        "Fees & Cost": "tuition fee uk international tuition fee",
        "Teaching Quality & NSS": "nss teaching satisfaction mental wellbeing facilities tef rating",
        "University Rankings": "guardian rank cug rank qs rank league table ranking",
    }

    priority_column_terms = []
    for p in priorities:
        for label, terms in _PRIORITY_COLUMN_HINTS.items():
            if label.lower() in str(p).lower():
                priority_column_terms.append(terms)
                break

    focused_question = question
    if target_programme or competitor_university or priorities:
        priority_text = ", ".join(str(item) for item in priorities) if priorities else "none"
        parts = [
            f'Compare the target programme "{target_programme}" from "{baseline_university}" against the selected competitor university "{competitor_university or "N/A"}" using the selected priorities ({priority_text}) and return a short decision summary.'
        ]
        if priority_column_terms:
            parts.append(f"Focus on: {' | '.join(priority_column_terms)}")
        if question:
            parts.append(f"Provided tutor prompt: {question}")
        if additional_instruction:
            parts.append(f"Additional tutor instruction: {additional_instruction}")
        if target_programme:
            parts.append(f"Target programme: {target_programme}")
        if baseline_university:
            parts.append(f"Baseline university: {baseline_university}")
        if competitor_university:
            parts.append(f"Competitor university: {competitor_university}")
        if priorities:
            parts.append(f"Student priorities: {', '.join(str(item) for item in priorities)}")
        focused_question = "\n".join(parts)

    result = _get_rag().query_pipeline(
        focused_question,
        target_competitor=competitor_university or None,
        target_programme=target_programme or None,
        target_baseline=baseline_university or None,
        priorities=priorities or None,
    )
    return {
        "question": question,
        "answer": result.get("answer", "Insufficient information in the provided context."),
        "engine_used": result.get("engine_used"),
        "routing_layer": result.get("routing_layer"),
        "latency_seconds": result.get("latency_seconds"),
        "confidence_score": result.get("confidence_score"),
        "should_abstain": result.get("should_abstain"),
        "sources": result.get("sources", []),
        "citations": result.get("citations", []),
        "contexts": result.get("contexts", []),
    }


@app.get("/v1/models")
def list_models(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": now,
                "owned_by": "admissions-assistant",
            }
        ],
    }


@app.post("/v1/chat/completions")
def chat_completions(
    payload: ChatCompletionRequest,
    authorization: Optional[str] = Header(default=None),
) -> Any:
    _check_api_key(authorization)

    query = _get_latest_user_message(payload.messages)
    if not query:
        raise HTTPException(status_code=400, detail="No user message found in request")

    result = _get_rag().query_pipeline(query)
    answer = result.get("answer", "Insufficient information in the provided context.")

    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    now = int(time.time())

    if payload.stream:
        return StreamingResponse(
            _stream_completion_chunks(completion_id, now, answer),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    return _to_chat_completion(completion_id, now, answer, query)
