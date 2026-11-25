"""Gerador local PDF + HTML com as respostas existentes em cada registro.

Uso: python gerar_relatorio.py --entrada entradas/compras.json
Sem --entrada, lê MONGODB_URI e MONGODB_DB do .env local.
Não inclui, simula ou inventa registros da farmácia.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

from relatorios.campos import load_config
from relatorios.dados import DataError, load_files, load_mongo
from relatorios.renderizar import prepare_report, write_html, write_pdf

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "relatorios-gerados" / "Maximum-Farmacia-Relatorio.pdf"

def choose_source(folder=False):
    try:
        import tkinter as tk
        from tkinter import filedialog
        window = tk.Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        try:
            if folder:
                result = filedialog.askdirectory(title="Selecione a pasta com os dados da farmácia", parent=window)
            else:
                result = filedialog.askopenfilename(
                    title="Selecione os dados da farmácia", parent=window,
                    filetypes=[("Dados para o relatório", "*.json *.jsonl *.ndjson *.csv"),
                               ("Todos os arquivos", "*.*")],
                )
        finally:
            window.destroy()
        return Path(result) if result else None
    except ImportError as exc:
        raise DataError("O seletor de arquivos precisa do Tkinter do Python. "
                        "Use --entrada seguido do caminho do arquivo ou da pasta.") from exc
    except Exception as exc:
        raise DataError("Não foi possível abrir o seletor. Use --entrada com o caminho do arquivo ou pasta.") from exc

class ReportArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, "Argumentos inválidos: " + message + "\n")

def parser():
    result = ReportArgumentParser(
        description="Gera PDF e HTML com as respostas e valores reais dos registros fornecidos.",
        epilog="Exemplo: python gerar_relatorio.py --entrada entradas/compras.json",
    )
    result.add_argument("saida", nargs="?", type=Path, default=DEFAULT_OUTPUT, help="Destino PDF (opcional)")
    source = result.add_mutually_exclusive_group()
    source.add_argument("--entrada", type=Path, help="Arquivo JSON, JSONL, NDJSON, CSV ou pasta de arquivos")
    source.add_argument("--escolher-arquivo", action="store_true", help="Abrir seletor de arquivo")
    source.add_argument("--escolher-pasta", action="store_true", help="Abrir seletor de pasta")
    result.add_argument("--config", type=Path, help="Mapeamento explícito de moeda/referências (opcional)")
    return result

def main(argv=None):
    args = parser().parse_args(argv)
    output = args.saida.expanduser().resolve()
    if output.suffix.lower() != ".pdf":
        print("Informe um destino terminado em .pdf. O HTML será salvo ao lado dele.", file=sys.stderr)
        return 1
    try:
        input_path = args.entrada
        if args.escolher_arquivo or args.escolher_pasta:
            input_path = choose_source(folder=args.escolher_pasta)
            if input_path is None:
                print("Seleção cancelada. Nenhum relatório foi criado.")
                return 3
        config = load_config(args.config)
        if input_path is not None:
            dataset = load_files(input_path.expanduser())
        else:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
            uri = os.environ.get("MONGODB_URI", "").strip()
            if not uri or "USUARIO:SENHA@CLUSTER" in uri:
                raise DataError("Nenhum banco foi configurado. Use --entrada com uma exportação JSON/CSV "
                                "ou preencha MONGODB_URI no .env do seu computador.")
            dataset = load_mongo(uri, os.environ.get("MONGODB_DB") or None)
        report = prepare_report(dataset, config)
        if not report.count:
            raise DataError("Nenhum registro foi recebido. O gerador não cria respostas de exemplo automaticamente.")
        output.parent.mkdir(parents=True, exist_ok=True)
        html_output = output.with_suffix(".html")
        # Só substitui os arquivos finais depois que as duas versões são geradas.
        with tempfile.TemporaryDirectory(prefix="maximum-", dir=output.parent) as tmp:
            tmp_pdf = Path(tmp) / "relatorio.pdf"
            tmp_html = Path(tmp) / "relatorio.html"
            write_html(report, tmp_html)
            write_pdf(report, tmp_pdf)
            os.replace(tmp_html, html_output)
            os.replace(tmp_pdf, output)
        print("Relatórios gerados com os registros fornecidos.")
        print("Registros:", report.count, "| Categorias:", len(report.groups))
        print("Campos preenchidos:", report.statuses["filled"])
        print("Campos sem preenchimento:", sum(report.statuses[s] for s in ("missing", "blank", "empty")))
        print("Campos para conferência:", report.statuses["invalid"] + report.statuses["unresolved"])
        print("PDF:", output)
        print("HTML:", html_output)
        if report.partial:
            print("ATENÇÃO: leitura parcial. Confira os avisos no relatório; ele não reúne toda a fonte.")
            return 2
        return 0
    except (DataError, ValueError) as exc:
        print("Não foi possível gerar: " + str(exc), file=sys.stderr)
    except ModuleNotFoundError:
        print("Faltam dependências. Execute: python -m pip install -r requirements.txt", file=sys.stderr)
    except PermissionError:
        print("Não foi possível salvar. Feche o PDF/HTML aberto e confira a permissão da pasta.", file=sys.stderr)
    except Exception as exc:
        # Não expõe URI, credenciais ou valores de registros na saída do terminal.
        print("Falha ao gerar o relatório (" + type(exc).__name__ + "). "
              "Confira os arquivos de entrada e as dependências. Nenhum relatório de sucesso foi anunciado.", file=sys.stderr)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
