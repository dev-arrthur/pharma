import csv
import io
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from relatorios.dados import DataError, load_files, load_mongo


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, text, encoding="utf-8"):
        path = self.root / name
        path.write_text(text, encoding=encoding)
        return path

    def test_json_values_and_precision_are_preserved(self):
        path = self.write("itens.json", '[{"ativo":false,"zero":0,"nulo":null,"codigo":"0007","valor":12.34567890123456789}]')
        dataset = load_files(path)
        row = dataset.groups[0].records[0]
        self.assertIs(row["ativo"], False)
        self.assertEqual(row["zero"], 0)
        self.assertIsNone(row["nulo"])
        self.assertEqual(row["codigo"], "0007")
        self.assertEqual(row["valor"], Decimal("12.34567890123456789"))
        self.assertEqual(dataset.groups[0].state, "complete")

    def test_simple_object_is_one_document(self):
        dataset = load_files(self.write("resposta.json", '{"resposta":"Confirmado","itens":[]}'))
        self.assertEqual(len(dataset.groups[0].records), 1)
        self.assertEqual(dataset.groups[0].records[0]["itens"], [])

    def test_envelope_preserves_groups_and_empty_collection(self):
        path = self.write("banco.json", '{"database":"farmacia","collections":{"compras":[{"id":1}],"vazia":[]}}')
        groups = load_files(path).groups
        self.assertEqual([(g.database, g.name, len(g.records)) for g in groups], [("farmacia", "compras", 1), ("farmacia", "vazia", 0)])

    def test_api_page_is_marked_partial(self):
        dataset = load_files(self.write("pagina.json", '{"rows":[{"nome":"A"}],"total":85}'))
        self.assertEqual(dataset.groups[0].state, "partial")
        self.assertIn("1 de 85", dataset.groups[0].error)
        self.assertTrue(dataset.warnings)

    def test_ndjson_retains_valid_lines_and_reports_invalid(self):
        dataset = load_files(self.write("respostas.ndjson", '{"resposta":false}\nQUEBRADO\n{"resposta":0}\n'))
        self.assertEqual(dataset.groups[0].records, [{"resposta": False}, {"resposta": 0}])
        self.assertEqual(dataset.groups[0].state, "partial")
        self.assertIn("linhas 2", dataset.warnings[0])

    def test_csv_bom_and_leading_zeros(self):
        path = self.write("compras.csv", 'codigo,nome,valor\n0007,"Nome, exemplo","1.234,56"\n', "utf-8-sig")
        row = load_files(path).groups[0].records[0]
        self.assertEqual(row, {"codigo": "0007", "nome": "Nome, exemplo", "valor": "1.234,56"})

    def test_csv_windows_encoding_and_semicolon(self):
        path = self.write("compras.csv", 'codigo;descrição;valor\n0012;Ação;0,00\n', "cp1252")
        row = load_files(path).groups[0].records[0]
        self.assertEqual(row, {"codigo": "0012", "descrição": "Ação", "valor": "0,00"})

    def test_legacy_csv_decodes_full_ejson_document(self):
        document = {"_id": {"$oid": "012345678901234567890123"}, "valor": {"$numberDecimal": "10.00"}, "resposta": False}
        text = io.StringIO(newline="")
        writer = csv.writer(text)
        writer.writerow(["_id", "documento_json"])
        writer.writerow([json.dumps(document["_id"]), json.dumps(document)])
        row = load_files(self.write("legado.csv", text.getvalue())).groups[0].records[0]
        self.assertEqual(row, document)

    def test_folder_reports_bad_file_and_ignores_metadata(self):
        self.write("bom.json", '[{"nome":"real"}]')
        self.write("ruim.json", '{quebrado')
        self.write("bom.metadata.json", '{quebrado')
        self.write("config-relatorio.json", '{quebrado')
        example_config = self.write("config-relatorio.example.json", '{"money_fields":{}}')
        self.write("nao_importar.txt", '{quebrado')
        dataset = load_files(self.root)
        self.assertEqual(len(dataset.groups), 2)
        self.assertEqual(sum(len(g.records) for g in dataset.groups), 1)
        self.assertEqual(len(dataset.warnings), 1)
        self.assertIn("ruim.json", dataset.warnings[0])
        with self.assertRaisesRegex(DataError, "não metadados ou configuração"):
            load_files(example_config)

    def test_no_valid_records_is_error(self):
        self.write("vazio.json", '[]')
        self.write("ruim.json", '{quebrado')
        with self.assertRaisesRegex(DataError, "Nenhum registro válido"):
            load_files(self.root)

    def test_invalid_record_does_not_drop_other_records_silently(self):
        dataset = load_files(self.write("dados.json", '[{"id":1},false,{"id":2}]'))
        self.assertEqual(dataset.groups[0].records, [{"id": 1}, {"id": 2}])
        self.assertEqual(dataset.groups[0].state, "partial")

    def test_invalid_csv_row_marks_partial(self):
        dataset = load_files(self.write("dados.csv", 'id;nome\n001;A\n002;B;EXTRA\n003;C\n'))
        self.assertEqual(len(dataset.groups[0].records), 2)
        self.assertEqual(dataset.groups[0].state, "partial")


class FakeCursor:
    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error
        self.closed = False
        self.max_time = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def __iter__(self):
        yield from self.rows
        if self.error:
            raise self.error

    def sort(self, *_args):
        return self

    def batch_size(self, _size):
        return self

    def max_time_ms(self, value):
        self.max_time = value
        return self


class FakeCollection:
    def __init__(self, cursor):
        self.cursor = cursor

    def find(self, query):
        assert query == {}
        return self.cursor


class FakeDatabase:
    def __init__(self, mapping):
        self.mapping = mapping
        self.list_cursor = None

    def list_collections(self, **kwargs):
        assert kwargs["authorizedCollections"] is True
        self.list_cursor = FakeCursor([{"name": name} for name in self.mapping])
        return self.list_cursor

    def __getitem__(self, key):
        return FakeCollection(self.mapping[key])


class FakeClient:
    def __init__(self, mapping):
        self.mapping = mapping
        self.admin = self
        self.commands = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def command(self, name, **kwargs):
        self.commands.append((name, kwargs))
        if name == "listDatabases":
            return {"databases": [{"name": key} for key in ["admin", "local", "config", *self.mapping]]}
        return {"ok": 1}

    def __getitem__(self, key):
        return self.mapping[key]


class MongoTests(unittest.TestCase):
    def test_mongo_is_read_only_scoped_and_closes_resources(self):
        native_date = datetime(2026, 11, 25, tzinfo=timezone.utc)
        good = FakeCursor([{"zero": 0, "flag": False, "data": native_date}])
        excluded = FakeCursor([{"secret": "not-for-report"}])
        db = FakeDatabase({"compras": good, "sessions": excluded, "system.indexes": excluded})
        client = FakeClient({"farmacia": db})
        settings = {}

        def factory(_uri, **kwargs):
            settings.update(kwargs)
            return client

        with patch.dict(sys.modules, {"pymongo": types.SimpleNamespace(MongoClient=factory)}):
            dataset = load_mongo("mongodb://example.invalid", None)
        self.assertEqual([g.name for g in dataset.groups], ["compras"])
        self.assertIs(dataset.groups[0].records[0]["data"], native_date)
        self.assertTrue(client.closed)
        self.assertTrue(good.closed)
        self.assertTrue(db.list_cursor.closed)
        self.assertEqual(good.max_time, 120000)
        self.assertTrue(next(kwargs for name, kwargs in client.commands if name == "listDatabases")["authorizedDatabases"])
        self.assertIn("snapshot", dataset.warnings[0])
        self.assertGreater(settings["socketTimeoutMS"], 0)

    def test_explicit_db_does_not_list_databases_and_partial_retains_rows(self):
        cursor = FakeCursor([{"id": 1}], RuntimeError("mongodb://user:SECRET@host"))
        client = FakeClient({"farmacia": FakeDatabase({"compras": cursor})})
        with patch.dict(sys.modules, {"pymongo": types.SimpleNamespace(MongoClient=lambda *_a, **_k: client)}):
            dataset = load_mongo("mongodb://user:SECRET@host", "farmacia")
        self.assertEqual(dataset.groups[0].records, [{"id": 1}])
        self.assertEqual(dataset.groups[0].state, "partial")
        self.assertNotIn("SECRET", " ".join(dataset.warnings))
        self.assertNotIn("listDatabases", [name for name, _kwargs in client.commands])
        self.assertTrue(cursor.closed)

    def test_connection_error_never_exposes_uri(self):
        def factory(*_args, **_kwargs):
            raise RuntimeError("mongodb://user:SECRET@host")
        with patch.dict(sys.modules, {"pymongo": types.SimpleNamespace(MongoClient=factory)}):
            with self.assertRaises(DataError) as raised:
                load_mongo("mongodb://user:SECRET@host", None)
        self.assertNotIn("SECRET", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
