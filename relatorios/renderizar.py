"""Gera PDF e HTML a partir dos mesmos campos, sem criar respostas."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from base64 import b64encode
from xml.sax.saxutils import escape as xml_escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .campos import FieldValue, label, record_fields, record_title


BURGUNDY = "#750207"
INK = "#252525"
MUTED = "#60676D"
PALE = "#FAF4F4"
STATUS_LABELS = {
    "filled": "Preenchido", "missing": "Não informado", "blank": "Em branco",
    "empty": "Sem itens", "omitted": "Acesso protegido", "invalid": "Conferir formato",
    "unresolved": "Conferir referência",
}


@dataclass
class PreparedRecord:
    number: int
    title: str
    fields: list[FieldValue]


@dataclass
class PreparedGroup:
    database: str
    name: str
    state: str
    error: str
    records: list[PreparedRecord] = field(default_factory=list)


@dataclass
class PreparedReport:
    source: str
    generated_at: str
    groups: list[PreparedGroup]
    warnings: list[str]
    statuses: Counter
    configured: bool

    @property
    def count(self):
        return sum(len(group.records) for group in self.groups)

    @property
    def partial(self):
        return any(group.state != "complete" for group in self.groups)


def prepare_report(dataset, config: dict) -> PreparedReport:
    try:
        tz = ZoneInfo("America/Sao_Paulo")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=-3))
    groups, statuses = [], Counter()
    for source_group in dataset.groups:
        group = PreparedGroup(source_group.database, source_group.name,
                              source_group.state, source_group.error)
        for number, raw in enumerate(source_group.records, start=1):
            fields = record_fields(raw, source_group, dataset, config)
            group.records.append(PreparedRecord(number, record_title(raw, number), fields))
            statuses.update(f.status for f in fields)
        groups.append(group)
    return PreparedReport(dataset.source_label,
                          datetime.now(tz).strftime("%d/%m/%Y às %H:%M (Brasília)"),
                          groups, list(dataset.warnings), statuses, bool(config))


def report_notes(report: PreparedReport) -> list[str]:
    notes = [
        "Cada resposta abaixo foi lida da fonte indicada. Zero e Não são respostas válidas; "
        "não foram substituídos por campos vazios.",
        "Não informado, Em branco e Sem itens descrevem o conteúdo encontrado na origem. "
        "Essas marcações não são respostas preenchidas pelo sistema.",
        "Os valores são apresentados conforme a origem. Moeda, unidade e referências só são "
        "convertidas quando há um mapeamento explícito. Não há total financeiro calculado automaticamente.",
    ]
    if report.statuses["omitted"]:
        notes.append("Conteúdos de acesso, como senhas e tokens reconhecidos, foram omitidos. "
                     "O relatório mantém os demais campos para conferência.")
    return notes + report.warnings


HTML_STYLE = """
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#F5F6F8;color:#252525;font:15px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
.top{border-top:7px solid #750207;background:white;border-bottom:1px solid #E5E7EB}.top-inner{max-width:1180px;margin:auto;padding:22px 28px;display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{font-size:25px;font-weight:800;letter-spacing:1px;color:#750207}.brand small{display:block;font-size:10px;letter-spacing:2.1px;color:#67676D;font-weight:600}.pill{font-size:12px;background:#FAF0F0;color:#750207;padding:6px 12px;border-radius:30px}
main{max-width:1180px;margin:auto;padding:32px 28px 48px}.eyebrow{font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#750207}h1{font-size:34px;line-height:1.2;letter-spacing:-1px;margin:8px 0 14px}h2{font-size:22px;margin:0 0 4px}h3{font-size:16px;line-height:1.45;margin:0}p{margin:8px 0;color:#60676D}.intro{max-width:780px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}.metric{background:white;border:1px solid #E6E7EB;border-radius:12px;padding:18px}.metric span{font-size:12px;color:#60676D}.metric strong{display:block;color:#750207;font-size:27px;line-height:1.4;margin-top:6px}.panel{background:white;border:1px solid #E6E7EB;border-radius:14px;padding:22px;margin:22px 0}.note{background:#FFF8EE;border-left:4px solid #B36E15;border-radius:8px;padding:16px 20px;margin:20px 0}.note strong{color:#874D08}.note p{color:#5E4D34}.tools{display:flex;gap:10px;align-items:end;flex-wrap:wrap}.tools label{display:grid;gap:5px;color:#60676D;font-size:12px;flex:1;min-width:160px}input,select,button{font:inherit;border:1px solid #DADDE2;border-radius:8px;padding:10px 12px;background:white;color:#252525}button{cursor:pointer}.primary{background:#750207;color:white;border-color:#750207}.small{font-size:12px;color:#60676D}.index{list-style:none;padding:0;display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.index a{color:#750207;text-decoration:none;display:flex;justify-content:space-between;border:1px solid #E9E1E1;border-radius:8px;padding:12px;gap:12px}.index a:hover{background:#FAF4F4}.index span{color:#60676D;font-size:12px}.group{margin-top:34px;scroll-margin-top:20px}.group-head{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:14px}.record{border:1px solid #E2E5E8;border-radius:12px;background:white;overflow:hidden;margin:14px 0}.record-head{background:#FAF4F4;border-bottom:1px solid #E9DEDE;padding:16px 20px;display:flex;gap:16px;align-items:start}.record-no{color:#750207;font-size:12px;min-width:35px;font-weight:700}.tablewrap{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left}th{font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:#61666E;background:#FCFCFD}th,td{padding:12px 20px;border-bottom:1px solid #EEEFF1;vertical-align:top}th:first-child,td:first-child{width:34%}td{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}td.answer{color:#252525}tr:last-child td{border-bottom:0}.path{display:block;color:#84868D;font-size:10px;margin-top:4px;font-family:ui-monospace,monospace}.state{display:inline-block;font-size:10px;border-radius:4px;color:#8A590F;background:#FFF5E6;padding:2px 6px;margin-top:6px;white-space:normal}.state.omitted{background:#F0F1F4;color:#5A6070}.empty-result{padding:24px;background:white;border:1px dashed #DADDE2;border-radius:12px}.pagefoot{font-size:11px;color:#787D84;border-top:1px solid #DADDE2;margin-top:32px;padding-top:16px}.notes{padding-left:20px;font-size:12px;color:#60676D}.notes li{margin:8px 0}[hidden]{display:none!important}:focus-visible{outline:3px solid #B57277;outline-offset:3px}
@media(max-width:700px){main{padding:22px 14px}.top-inner{padding:18px 14px}.metrics{grid-template-columns:repeat(2,1fr)}h1{font-size:27px}.index{grid-template-columns:1fr}.group-head{align-items:flex-start;flex-direction:column}th,td{padding:10px}th:first-child,td:first-child{width:40%}.record-head{padding:14px}}
@media print{@page{size:A4;margin:15mm}body{background:white;font-size:10pt}.top{border-top:4px solid #750207}.top-inner{padding:10px 0}main{padding:12px 0}.screen-only{display:none!important}.metrics{grid-template-columns:repeat(4,1fr)}.metric{padding:10px}.metric strong{font-size:19px}.panel{padding:14px}.group{break-before:page;margin-top:0}.record{border-radius:0;overflow:visible}.record-head{break-after:avoid}table{table-layout:fixed}thead{display:table-header-group}tr{break-inside:auto}td{font-size:8pt}.tablewrap{overflow:visible}h1{font-size:24pt}.path{font-size:7pt}a{color:inherit;text-decoration:none}.pagefoot{margin-top:20px}}
"""

HTML_SCRIPT = """
(()=>{'use strict';const q=document.getElementById('search'),category=document.getElementById('category');
const records=[...document.querySelectorAll('.record')],groups=[...document.querySelectorAll('.group')];
const norm=v=>v.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLocaleLowerCase('pt-BR');
const cache=new Map(records.map(el=>[el,norm(el.textContent)]));
function apply(){const term=norm(q.value.trim()),cat=category.value;let visible=0;
for(const el of records){el.hidden=(cat!=='all'&&el.dataset.group!==cat)||(term&&!cache.get(el).includes(term));if(!el.hidden)visible++;}
for(const el of groups)el.hidden=(cat!=='all'&&el.id!==cat)||(![...el.querySelectorAll('.record')].some(r=>!r.hidden)&&Boolean(term));
document.getElementById('resultCount').textContent=visible+' de '+records.length+' registros exibidos';
document.getElementById('empty').hidden=visible>0;
document.getElementById('filterNote').textContent=(term||cat!=='all')?'Visualização filtrada. A impressão inclui os registros visíveis.':'Todos os registros importados estão visíveis.';
}q.addEventListener('input',apply);category.addEventListener('change',apply);
document.getElementById('clear').addEventListener('click',()=>{q.value='';category.value='all';apply()});
document.getElementById('print').addEventListener('click',()=>window.print());apply();})();
"""


def write_html(report: PreparedReport, path: Path):
    script_hash = b64encode(sha256(HTML_SCRIPT.encode("utf-8")).digest()).decode("ascii")
    csp = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-" + script_hash
           + "'; base-uri 'none'; form-action 'none'; img-src 'none'")
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        def w(text): stream.write(text)
        w('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
          '<meta name="viewport" content="width=device-width,initial-scale=1">'
          '<meta http-equiv="Content-Security-Policy" content="' + escape(csp, quote=True) + '">'
          '<title>Maximum | Respostas e valores por item</title><style>' + HTML_STYLE + '</style></head><body>')
        w('<header class="top"><div class="top-inner"><div class="brand">MAXIMUM'
          '<small>ASSESSORIA CONTÁBIL · FARMÁCIA</small></div><span class="pill">Consulta dos registros</span></div></header>')
        w('<main><div class="intro"><span class="eyebrow">Relatório de conferência</span>'
          '<h1>Respostas e valores<br>de cada item</h1><p>Informações organizadas por categoria e registro, '
          'com todos os campos disponíveis para conferência.</p><p class="small">Origem: '
          + escape(report.source) + '<br>Gerado em ' + escape(report.generated_at) + '</p></div>')
        metrics = [("Registros", report.count), ("Categorias", len(report.groups)),
                   ("Campos preenchidos", report.statuses["filled"]),
                   ("Sem preenchimento", sum(report.statuses[s] for s in ["missing", "blank", "empty"]))]
        w('<div class="metrics">' + ''.join('<div class="metric"><span>' + escape(k)
          + '</span><strong>' + str(v) + '</strong></div>' for k, v in metrics) + '</div>')
        if report.partial:
            w('<aside class="note"><strong>Leitura parcial</strong><p>Uma parte da fonte não pôde ser lida '
              'por completo. Consulte as categorias sinalizadas antes de utilizar o relatório.</p></aside>')
        w('<section class="panel screen-only"><div class="tools"><label>Pesquisar nos registros'
          '<input id="search" type="search" placeholder="Nome, item ou resposta"></label><label>Categoria'
          '<select id="category"><option value="all">Todas as categorias</option>')
        for i, group in enumerate(report.groups):
            w('<option value="g' + str(i) + '">' + escape(label(group.name)) + ' · '
              + escape(group.database) + '</option>')
        w('</select></label><button id="clear">Limpar</button><button id="print" class="primary">'
          'Imprimir / Salvar PDF</button></div><p id="resultCount" class="small"></p></section>'
          '<p id="filterNote" class="small">Todos os registros importados estão visíveis.</p>')
        w('<nav class="panel screen-only" aria-label="Categorias"><h2>Índice do relatório</h2><ul class="index">')
        for i, group in enumerate(report.groups):
            w('<li><a href="#g' + str(i) + '"><strong>' + escape(label(group.name)) + '</strong><span>'
              + str(len(group.records)) + ' registros' + (' · Parcial' if group.state != "complete" else '') + '</span></a></li>')
        w('</ul></nav><p id="empty" class="empty-result" hidden>Nenhum registro corresponde à pesquisa.</p>')
        for i, group in enumerate(report.groups):
            w('<section class="group" id="g' + str(i) + '"><div class="group-head"><div><span class="eyebrow">'
              + escape(group.database) + '</span><h2>' + escape(label(group.name)) + '</h2></div><span class="small">'
              + str(len(group.records)) + ' registros</span></div>')
            if group.state != "complete":
                w('<div class="note"><strong>Categoria com leitura parcial</strong><p>' + escape(group.error or "Confira a origem dos registros.") + '</p></div>')
            if not group.records:
                w('<p>Nenhum registro disponível nesta categoria.</p>')
            for record in group.records:
                w('<article class="record" data-group="g' + str(i) + '"><header class="record-head">'
                  '<span class="record-no">' + str(record.number).zfill(2) + '</span><div><h3>'
                  + escape(record.title) + '</h3><span class="small">' + str(len(record.fields))
                  + ' campos apresentados</span></div></header><div class="tablewrap"><table><thead><tr>'
                  '<th>Item / informação</th><th>Resposta ou valor registrado</th></tr></thead><tbody>')
                for item in record.fields:
                    w('<tr><td>' + escape(item.label) + '<span class="path">' + escape(item.path) + '</span></td>'
                      '<td class="answer">' + escape(item.text))
                    if item.status != "filled":
                        w('<br><span class="state ' + escape(item.status, quote=True) + '">'
                          + escape(STATUS_LABELS.get(item.status, item.status)) + '</span>')
                    w('</td></tr>')
                w('</tbody></table></div></article>')
            w('</section>')
        w('<section class="panel"><h2>Como interpretar</h2><ul class="notes">' + ''.join('<li>'
          + escape(note) + '</li>' for note in report_notes(report)) + '</ul></section>'
          '<footer class="pagefoot">Maximum Assessoria Contábil · Uso restrito · Cópia para conferência</footer>'
          '</main><script>' + HTML_SCRIPT + '</script></body></html>')


def write_pdf(report: PreparedReport, path: Path):
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, LongTable,
                                   TableStyle, PageBreak, CondPageBreak)

    fontdir = Path(reportlab.__file__).parent / "fonts"
    for name, file in [("Maximum", "Vera.ttf"), ("MaximumBold", "VeraBd.ttf")]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fontdir / file)))
    pdfmetrics.registerFontFamily("Maximum", normal="Maximum", bold="MaximumBold")
    glyphs = pdfmetrics.getFont("Maximum").face.charToGlyph
    unsupported = set()

    def readable(text):
        output = []
        for char in str(text):
            if char == "\n" or char in "\t\r":
                output.append("\n" if char != "\t" else "    ")
            elif ord(char) >= 32 and ord(char) in glyphs:
                output.append(char)
            else:
                unsupported.add(ord(char))
                output.append("[U+" + format(ord(char), "04X") + "]")
        return "".join(output)

    styles = {
        "body": ParagraphStyle("body", fontName="Maximum", fontSize=8.8, leading=13, textColor=colors.HexColor(INK), splitLongWords=True),
        "small": ParagraphStyle("small", fontName="Maximum", fontSize=7.3, leading=10.6, textColor=colors.HexColor(MUTED), splitLongWords=True),
        "title": ParagraphStyle("title", fontName="MaximumBold", fontSize=25, leading=31, textColor=colors.HexColor(BURGUNDY), spaceAfter=12),
        "section": ParagraphStyle("section", fontName="MaximumBold", fontSize=17, leading=22, textColor=colors.HexColor(BURGUNDY), spaceAfter=10, keepWithNext=True),
        "record": ParagraphStyle("record", fontName="MaximumBold", fontSize=10.5, leading=15, textColor=colors.HexColor(INK), spaceBefore=10, spaceAfter=6),
        "thead": ParagraphStyle("thead", fontName="MaximumBold", fontSize=8, leading=12, textColor=colors.white, splitLongWords=True),
        "metric": ParagraphStyle("metric", fontName="MaximumBold", fontSize=22, leading=28, textColor=colors.HexColor(BURGUNDY)),
    }

    def p(text, style="body"):
        return Paragraph(xml_escape(readable(text)).replace("\n", "<br/>"), styles[style])

    width = A4[0] - 80

    def make_table(rows, widths):
        table = LongTable(rows, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=0, splitInRow=30)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BURGUNDY)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(PALE)]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E7DEDE")),
        ]))
        return table

    def header(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(colors.HexColor(BURGUNDY))
        canvas.rect(0, h - 8, w, 8, fill=1, stroke=0)
        canvas.setFont("MaximumBold", 17)
        canvas.drawString(40, h - 37, "MAXIMUM")
        canvas.setFont("Maximum", 7)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(40, h - 50, "ASSESSORIA CONTÁBIL  |  FARMÁCIA")
        canvas.setStrokeColor(colors.HexColor("#E7DEDE"))
        canvas.line(40, h - 62, w - 40, h - 62)
        canvas.setFont("Maximum", 7)
        canvas.drawString(40, 24, "Maximum · Conferência de registros · Uso restrito")
        canvas.drawRightString(w - 40, 24, "Página " + str(doc.page))
        canvas.restoreState()

    story = [p("Respostas e valores\nde cada item", "title"),
             p("Relatório de conferência com os campos disponíveis na fonte."),
             Spacer(1, 10), p("Origem: " + report.source, "small"),
             p("Gerado em " + report.generated_at, "small"), Spacer(1, 20)]
    metrics = [("Registros", report.count), ("Categorias", len(report.groups)),
               ("Campos preenchidos", report.statuses["filled"]),
               ("Sem preenchimento", sum(report.statuses[s] for s in ["missing", "blank", "empty"]))]
    cards = Table([[ [p(title, "small"), p(str(value), "metric")] for title, value in metrics]],
                  colWidths=[width / 4] * 4)
    cards.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALE)),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#E7DEDE")),
                              ("TOPPADDING", (0, 0), (-1, -1), 12),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story.extend([cards, Spacer(1, 18)])
    if report.partial:
        story.extend([p("LEITURA PARCIAL", "record"), p("Uma parte da fonte não pôde ser lida por completo. "
                      "As categorias afetadas estão sinalizadas. Confira antes de utilizar o relatório."), Spacer(1, 12)])
    story.append(p("Categorias incluídas", "section"))
    rows = [[p("Categoria / base", "thead"), p("Registros", "thead"), p("Leitura", "thead")]]
    for group in report.groups:
        rows.append([p(label(group.name) + "\n" + group.database), p(str(len(group.records))),
                     p("Concluída" if group.state == "complete" else "Parcial")])
    story.extend([make_table(rows, [width - 158, 72, 86]), Spacer(1, 14),
                  p("Como interpretar", "record")])
    for note in report_notes(report):
        story.extend([p(note, "small"), Spacer(1, 5)])
    for group in report.groups:
        story.extend([PageBreak(), p(label(group.name), "section"),
                      p("Base: " + group.database + " | " + str(len(group.records)) + " registros", "small"), Spacer(1, 10)])
        if group.state != "complete":
            story.extend([p("Categoria com leitura parcial", "record"), p(group.error or "Confira a origem."), Spacer(1, 8)])
        if not group.records:
            story.append(p("Nenhum registro disponível nesta categoria."))
        for record in group.records:
            story.append(CondPageBreak(125))
            story.append(p(str(record.number).zfill(2) + ". " + record.title, "record"))
            rows = [[p("Item / informação", "thead"), p("Resposta ou valor registrado", "thead")]]
            for item in record.fields:
                label_cell = [p(item.label), p(item.path, "small")]
                value_cell = [p(item.text)]
                if item.status != "filled":
                    value_cell.append(p(STATUS_LABELS.get(item.status, item.status), "small"))
                rows.append([label_cell, value_cell])
            if len(rows) == 1:
                rows.append([p("Campos disponíveis"), p("Nenhum campo disponível após remover dados de acesso.")])
            story.extend([make_table(rows, [175, width - 175]), Spacer(1, 12)])
    if unsupported:
        story.extend([Spacer(1, 12), p("Caracteres especiais", "record"),
                      p("Alguns caracteres foram representados pelo código [U+....] porque a fonte do PDF "
                        "não possui esses símbolos. O HTML preserva o texto original.", "small")])
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=40, rightMargin=40,
                            topMargin=82, bottomMargin=44,
                            title="Maximum - Respostas e valores de cada item",
                            author="Maximum Assessoria Contábil")
    doc.build(story, onFirstPage=header, onLaterPages=header)
