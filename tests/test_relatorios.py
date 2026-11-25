"""Casos sintéticos de conferência; não são registros da farmácia."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


class ReportIntegration(unittest.TestCase):
    def generate(self, folder, data, config=None):
        source = Path(folder) / 'dados.json'
        source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        output = Path(folder) / 'conferencia.pdf'
        cmd = [sys.executable, str(ROOT / 'gerar_relatorio.py'), str(output), '--entrada', str(source)]
        if config is not None:
            cp = Path(folder) / 'config.json'
            cp.write_text(json.dumps(config), encoding='utf-8')
            cmd += ['--config', str(cp)]
        result = subprocess.run(cmd, text=True, capture_output=True, cwd=ROOT, timeout=60)
        return output, result

    def test_all_items_values_visible_in_both_formats(self):
        data = {'database': 'TESTE SINTÉTICO', 'collections': {
            'funcionarios': [{'_id': {'$oid': '0123456789abcdef01234567'}, 'nome': 'Pessoa fictícia do teste'}],
            'compras': [{'_id': 'PEDIDO-TESTE', 'funcionarioId': {'$oid': '0123456789abcdef01234567'},
                        'itens': [{'pergunta': 'Recebido?', 'resposta': False, 'quantidade': 0, 'valorUnitario': {'$numberDecimal': '15.40'}},
                                  {'pergunta': 'Observação', 'resposta': 'Conferência de teste <img src=x onerror=alert(1)>', 'valorUnitario': 0}],
                        'vazio': '', 'nulo': None, 'semItens': [], 'password': 'SEGREDO-QUE-NAO-PODE-VAZAR'}]}}
        config = {'currency_fields': {'compras.itens.*.valorUnitario': {'currency': 'BRL', 'unit': 'reais', 'decimal_separator': '.'}},
                  'references': {'compras.funcionarioId': {'collection': 'funcionarios', 'key': '_id', 'label': 'nome'}}}
        with tempfile.TemporaryDirectory() as folder:
            output, result = self.generate(folder, data, config)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = output.with_suffix('.html').read_text(encoding='utf-8')
            pdf = '\n'.join(page.extract_text() for page in PdfReader(output).pages)
            for expected in ['Pessoa fictícia do teste', 'Recebido?', 'Não', 'R$ 15,40', 'R$ 0,00', 'itens[1].resposta', 'itens[2].resposta',
                             'Não informado na origem', 'Em branco na origem', 'Nenhum item registrado']:
                self.assertIn(expected, html)
                self.assertIn(expected, pdf)
            for text in (html, pdf, result.stdout, result.stderr):
                self.assertNotIn('SEGREDO-QUE-NAO-PODE-VAZAR', text)
            self.assertNotIn('<img src=x', html)
            self.assertIn('&lt;img src=x', html)
            self.assertIn('Content-Security-Policy', html)

    def test_page_export_is_marked_partial_and_exit_two(self):
        with tempfile.TemporaryDirectory() as folder:
            output, result = self.generate(folder, {'rows': [{'nome': 'Caso parcial'}], 'total': 84})
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertTrue(output.is_file())
            self.assertIn('Leitura parcial', output.with_suffix('.html').read_text())
            self.assertIn('84 registros', output.with_suffix('.html').read_text())

    def test_no_source_data_does_not_generate_filled_report(self):
        with tempfile.TemporaryDirectory() as folder:
            output, result = self.generate(folder, [])
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix('.html').exists())

    def test_long_response_spans_pages_without_truncation(self):
        long_value = ('Resposta extensa de teste com acentuação. ' * 600) + 'FIM-DA-RESPOSTA-COMPLETA'
        with tempfile.TemporaryDirectory() as folder:
            output, result = self.generate(folder, [{'nome': 'Caso longo', 'respostas': [{'item': 'Único', 'resposta': long_value}]}])
            self.assertEqual(result.returncode, 0, result.stderr)
            pages = PdfReader(output).pages
            self.assertGreater(len(pages), 2)
            text = '\n'.join(page.extract_text() for page in pages)
            self.assertIn('FIM-DA-RESPOSTA-COMPLETA', text)
            self.assertIn(long_value, output.with_suffix('.html').read_text())


if __name__ == '__main__':
    unittest.main()
