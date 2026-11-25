import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from relatorios.campos import load_config, record_fields, record_title


class FieldValuesTests(unittest.TestCase):
    def make(self, row, config=None, others=()):
        group = SimpleNamespace(database="farmacia", name="compras", records=[row])
        dataset = SimpleNamespace(groups=[group, *others])
        return record_fields(row, group, dataset, config or {})

    def test_all_items_answers_and_distinct_empty_states(self):
        row = {"itens": [{"pergunta": "Recebido?", "resposta": False}, {"pergunta": "Quantidade", "resposta": 0}],
               "nulo": None, "texto": " ", "lista": [], "objeto": {}}
        before = copy.deepcopy(row)
        fields = self.make(row)
        lookup = {f.path: f for f in fields}
        self.assertEqual(lookup["itens[1].resposta"].label, "Itens > Item 1 > Resposta")
        self.assertEqual(lookup["itens[1].resposta"].text, "Não")
        self.assertEqual(lookup["itens[2].resposta"].text, "0")
        self.assertEqual(lookup["nulo"].status, "missing")
        self.assertEqual(lookup["texto"].status, "blank")
        self.assertEqual(lookup["lista"].status, "empty")
        self.assertEqual(lookup["objeto"].text, "Nenhum item registrado")
        self.assertEqual(row, before)

    def test_exact_recursive_credential_redaction(self):
        fields = self.make({"password_hash": "NEVER_VISIBLE", "dados": {"api-key": "SECRET", "saltos": 2, "hashPedido": "a3"}, "__v": 1})
        joined = " ".join(f.text for f in fields)
        self.assertNotIn("NEVER_VISIBLE", joined)
        self.assertNotIn("SECRET", joined)
        self.assertIn("a3", joined)
        self.assertEqual(sum(f.status == "omitted" for f in fields), 2)
        self.assertFalse(any(f.path == "__v" for f in fields))

    def test_ejson_precision_epoch_and_dates(self):
        fields = self.make({"longo": {"$numberLong": "9007199254740993"}, "data": {"$date": {"$numberLong": "0"}}, "valor": {"$numberDecimal": "1234.5600"}, "texto": "2026-11-25T12:00:00Z"})
        values = {f.path: f.text for f in fields}
        self.assertEqual(values["longo"], "9007199254740993")
        self.assertEqual(values["data"], "01/01/1970 00:00:00 UTC")
        self.assertEqual(values["valor"], "1234.5600")
        self.assertEqual(values["texto"], "2026-11-25T12:00:00Z")
        self.assertEqual(self.make({"data": datetime(1970, 1, 1, tzinfo=timezone.utc)})[0].text, values["data"])

    def test_native_bson_like_scalars_without_optional_dependency(self):
        class Decimal128:
            def to_decimal(self):
                return Decimal("125.55")

        class ObjectId:
            def __str__(self):
                return "abcdef0123456789abcdef01"

        fields = self.make({"valor": Decimal128(), "pessoa": ObjectId()})
        self.assertEqual(fields[0].text, "125.55")
        self.assertEqual(fields[1].text, "abcdef0123456789abcdef01")

    def test_currency_is_explicit_and_centavos_precise(self):
        row = {"total": 3, "itens": [{"valor": 123456}, {"valor": 0}, {"valor": -1}]}
        config = {"currency_fields": {"compras.itens.*.valor": {"unit": "centavos"}}}
        values = {f.path: f.text for f in self.make(row, config)}
        self.assertEqual(values["total"], "3")
        self.assertEqual(values["itens[1].valor"], "R$ 1.234,56")
        self.assertEqual(values["itens[2].valor"], "R$ 0,00")
        self.assertEqual(values["itens[3].valor"], "R$ -0,01")

    def test_currency_string_locale_and_invalid_raw_preserved(self):
        cfg = {"currency_fields": {"compras.valor": {"decimal_separator": ","}}}
        self.assertEqual(self.make({"valor": "R$ 1.234,56"}, cfg)[0].text, "R$ 1.234,56")
        self.assertEqual(self.make({"valor": Decimal("1234.56")}, cfg)[0].text, "R$ 1.234,56")
        item = self.make({"valor": "1,23"}, {"currency_fields": {"compras.valor": {}}})[0]
        self.assertEqual(item.status, "invalid")
        self.assertTrue(item.text.startswith("1,23"))
        self.assertEqual(self.make({"valor": False}, cfg)[0].status, "invalid")

    def test_explicit_references_only_same_database(self):
        identifier = "abcdef0123456789abcdef01"
        row = {"funcionarioId": {"$oid": identifier}}
        target = SimpleNamespace(database="farmacia", name="funcionarios", records=[{"_id": {"$oid": identifier}, "nome": "Pessoa de teste"}])
        unrelated = SimpleNamespace(database="outra", name="funcionarios", records=[{"_id": identifier, "nome": "Não usar"}])
        cfg = {"references": {"compras.funcionarioId": {"collection": "funcionarios", "key": "_id", "label": "nome"}}}
        self.assertEqual(self.make(row, others=[target])[0].text, identifier)
        resolved = self.make(row, cfg, [target, unrelated])[0]
        self.assertEqual(resolved.text, f"Pessoa de teste (ID: {identifier})")
        self.assertEqual(self.make(row, cfg, [unrelated])[0].status, "unresolved")
        duplicate = SimpleNamespace(database="farmacia", name="funcionarios", records=target.records * 2)
        self.assertIn("ambígua", self.make(row, cfg, [duplicate])[0].text)

    def test_false_id_does_not_match_one_or_zero(self):
        target = SimpleNamespace(database="farmacia", name="funcionarios", records=[{"_id": 0, "nome": "Zero"}])
        cfg = {"references": {"compras.funcionarioId": {"collection": "funcionarios", "key": "_id", "label": "nome"}}}
        self.assertEqual(self.make({"funcionarioId": False}, cfg, [target])[0].status, "unresolved")

    def test_missing_reference_label_and_non_scalar_label(self):
        target = SimpleNamespace(database="farmacia", name="funcionarios", records=[{"_id": "a", "nome": ""}])
        cfg = {"references": {"compras.funcionarioId": {"collection": "funcionarios", "key": "_id", "label": "nome"}}}
        self.assertIn("sem nome", self.make({"funcionarioId": "a"}, cfg, [target])[0].text)
        target.records[0]["nome"] = {"token": "PRIVATE"}
        value = self.make({"funcionarioId": "a"}, cfg, [target])[0]
        self.assertEqual(value.status, "unresolved")
        self.assertNotIn("PRIVATE", value.text)

    def test_title_preserves_false_and_zero_and_fields_not_truncated(self):
        self.assertEqual(record_title({"nome": 0}, 1), "0")
        self.assertEqual(record_title({"nome": False}, 1), "Não")
        long = "Árvore " * 100
        self.assertLessEqual(len(record_title({"nome": long}, 1)), 120)
        self.assertEqual(self.make({"nome": long})[0].text, long)

    def test_load_config_validates_unsafe_or_invalid_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"currency_fields": {"compras.valor": {"unit": "centavos"}}}), encoding="utf-8")
            self.assertEqual(load_config(path)["currency_fields"]["compras.valor"]["currency"], "BRL")
            for bad in [[], {"extra": {}}, {"currency_fields": {"valor": {}}}, {"references": {"compras.id": {"collection": "users", "key": "_id", "label": "passwordHash"}}}]:
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_config(path)
        self.assertEqual(load_config(None), {"currency_fields": {}, "references": {}})


if __name__ == "__main__":
    unittest.main()
