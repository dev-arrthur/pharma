"""Exportação local, somente leitura. Nenhum valor fictício."""
import os, re, sys
from datetime import datetime, timezone
from decimal import Decimal
from xml.sax.saxutils import escape
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.decimal128 import Decimal128
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT
load_dotenv(Path(__file__).resolve().parent / '.env')
RED=colors.HexColor('#790909')
INK=colors.HexColor('#252525')
PALE=colors.HexColor('#F8F1F1')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Campo',fontName='Helvetica',fontSize=8.5,leading=12,textColor=INK,splitLongWords=True))
styles.add(ParagraphStyle(name='Secao',fontName='Helvetica-Bold',fontSize=19,leading=24,textColor=RED,spaceAfter=12))
styles.add(ParagraphStyle(name='Registro',fontName='Helvetica-Bold',fontSize=11,leading=15,textColor=RED,spaceBefore=10,spaceAfter=5,keepWithNext=True))
styles.add(ParagraphStyle(name='Cab',fontName='Helvetica-Bold',fontSize=9,leading=12,textColor=colors.white))
secret=re.compile(r'password|senha|token|secret|credential|api.?key|salt|hash',re.I)
skip=re.compile(r'^(system\.|sessions?$|tokens?$|credentials?$|passwords?$|secrets?$|auth[_-]?sessions?$|api[_-]?keys?$)',re.I)
labels={'name':'Nome','nome':'Nome','amount':'Valor','value':'Valor','valor':'Valor','total':'Total','price':'Preço','preco':'Preço','cpf':'CPF','cnpj':'CNPJ','date':'Data','createdAt':'Data de cadastro','updatedAt':'Última atualização','status':'Situação','description':'Descrição','employees':'Funcionários','funcionarios':'Funcionários','companies':'Empresas','empresas':'Empresas','pharmacies':'Farmácias','farmacias':'Farmácias','purchases':'Compras','compras':'Compras','sales':'Vendas','transactions':'Movimentações','products':'Produtos','_id':'Identificador'}
money_fields={'amount','value','valor','total','price','preco','valorTotal','totalValue','unitPrice','valorUnitario','saldo','balance'}
def label(k): return labels.get(k,re.sub(r'([a-z])([A-Z])',r'\1 \2',str(k)).replace('_',' ').strip().capitalize())
def clean(v):
    if isinstance(v,dict): return {k:clean(x) for k,x in v.items() if not secret.search(k) and k!='__v'}
    if isinstance(v,list): return [clean(x) for x in v]
    return v
def value(v,k=''):
    if v is None:return 'Não informado'
    if isinstance(v,bool):return 'Sim' if v else 'Não'
    if isinstance(v,datetime):return v.strftime('%d/%m/%Y %H:%M')+' UTC'
    if isinstance(v,Decimal128):v=v.to_decimal()
    if isinstance(v,(int,float,Decimal)):
        if k in money_fields:
            return 'R$ '+format(v,',.2f').replace(',','X').replace('.',',').replace('X','.')
        return str(v)
    if isinstance(v,dict):return '\n'.join(label(a)+': '+value(b,a) for a,b in v.items())
    if isinstance(v,list):return '\n'.join(value(x,k) for x in v)
    return str(v)
def para(v,style='Campo'):
    return Paragraph(escape(str(v)).replace('\n','<br/>'),styles[style])
def table(rows,widths):
    t=LongTable(rows,colWidths=widths,repeatRows=1,hAlign='LEFT',splitInRow=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),RED),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),0.25,colors.HexColor('#E5DADA'))]))
    return t
def header(c,d):
    w,h=A4;c.setFillColor(RED);c.rect(0,h-15,w,15,fill=1,stroke=0)
    c.setFont('Helvetica-Bold',17);c.drawString(40,h-43,'MAXIMUM')
    c.setFont('Helvetica',8);c.drawString(40,h-56,'ASSESSORIA CONTÁBIL  |  FARMÁCIA')
    c.setStrokeColor(RED);c.line(40,h-67,w-40,h-67)
    c.setFont('Helvetica',8);c.setFillColor(INK);c.drawString(40,25,'Uso restrito • Informações do banco de dados');c.drawRightString(w-40,25,f'Página {d.page}')
def run():
    uri=os.getenv('MONGODB_URI')
    if not uri:raise RuntimeError('Configure MONGODB_URI no arquivo .env.')
    output=Path(sys.argv[1] if len(sys.argv)>1 else 'Maximum-Farmacia-Relatorio.pdf')
    story=[para('Relatório geral consolidado','Secao'),para('Extração de registros reais • '+datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')),Spacer(1,10),para('Valores apresentados conforme armazenados. Campos monetários reconhecidos são formatados em reais; não há soma entre campos ou categorias sem validação contábil. Campos de credenciais conhecidos são omitidos. A consulta não altera o banco.'),Spacer(1,15)]
    summary=[]; sections=[]; failures=[]
    with MongoClient(uri,serverSelectionTimeoutMS=12000) as client:
        client.admin.command('ping')
        names=[os.environ['MONGODB_DB']] if os.getenv('MONGODB_DB') else [x for x in client.list_database_names() if x not in ('admin','local','config')]
        for name in names:
            db=client[name]
            try: collections=db.list_collection_names()
            except Exception:failures.append(name);continue
            for col in sorted(collections):
                if skip.search(col):continue
                n=0; block=[PageBreak(),para(label(col),'Secao'),para('Base: '+name),Spacer(1,8)]
                try:
                    with db[col].find({}).sort('_id',1).batch_size(100) as cursor:
                        for raw in cursor:
                            row=clean(raw);n+=1
                            title=next((value(row[k]) for k in ('nome','name','razaoSocial','descricao','description') if row.get(k)),f'Registro {n}')
                            block.append(para(f'{n}. {title}','Registro'))
                            rows=[[para('Informação','Cab'),para('Valor registrado','Cab')]]
                            rows.extend([para(label(k)),para(value(v,k))] for k,v in row.items())
                            block.append(table(rows,[155,360]))
                    state='Concluída'
                except Exception:
                    state='Parcial';failures.append(name+'/'+col);block.append(para('A leitura desta categoria foi interrompida.'))
                block.append(Spacer(1,10));block.append(para(f'{n} registros exportados.'))
                summary.append((name,col,n,state));sections.extend(block)
    story.append(para('Resumo da consulta','Secao'))
    rows=[[para('Base / Categoria','Cab'),para('Registros','Cab'),para('Situação','Cab')]]
    rows.extend([para(a+' / '+label(b)),para(c),para(d)] for a,b,c,d in summary)
    if not summary:rows.append([para('Nenhuma categoria encontrada'),para('0'),para('Verificar acesso')])
    story.append(table(rows,[325,85,105]));story.append(Spacer(1,15))
    story.append(para('Total de registros exportados: '+str(sum(x[2] for x in summary)),'Registro'))
    story.append(para('Exportação parcial: '+', '.join(failures) if failures else 'Nenhuma falha de leitura detectada.'))
    story.extend(sections)
    doc=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=40,rightMargin=40,topMargin=85,bottomMargin=45,title='Maximum Farmácia - Relatório geral')
    doc.build(story,onFirstPage=header,onLaterPages=header)
    print('PDF gerado:',output.resolve())
if __name__=='__main__':
    try:run()
    except Exception as e:
        print('Não foi possível gerar o PDF. Confira a URI, permissões, IP autorizado e configuração do banco. Tipo:',type(e).__name__,file=sys.stderr);sys.exit(1)
