"""Respostas legíveis, sem inferir valores ou relações entre documentos.

Cada folha de um registro vira um campo com seu caminho original. Listas usam
índices iniciados em 1 na apresentação; a configuração usa ``*`` nos índices.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FieldValue:
    path: str
    label: str
    text: str
    status: str = "filled"


LABELS = {
    "_id": "Identificador", "name": "Nome", "nome": "Nome",
    "description": "Descrição", "descricao": "Descrição",
    "email": "E-mail", "cpf": "CPF", "cnpj": "CNPJ",
    "razaoSocial": "Razão social", "company": "Empresa",
    "companyId": "Empresa", "employeeId": "Funcionário",
    "productId": "Produto", "pharmacyId": "Farmácia",
    "funcionarioId": "Funcionário", "farmaciaId": "Farmácia",
    "empresaId": "Empresa", "produtoId": "Produto",
    "question": "Pergunta", "questionId": "Pergunta",
    "pergunta": "Pergunta", "perguntaId": "Pergunta",
    "answer": "Resposta", "answers": "Respostas", "response": "Resposta",
    "responses": "Respostas", "resposta": "Resposta", "respostas": "Respostas",
    "item": "Item", "items": "Itens", "itens": "Itens",
    "quantity": "Quantidade", "quantidade": "Quantidade", "qty": "Quantidade",
    "amount": "Valor", "value": "Valor", "valor": "Valor",
    "price": "Preço", "preco": "Preço", "unitPrice": "Preço unitário",
    "total": "Total", "valorTotal": "Valor total", "balance": "Saldo",
    "paid": "Pago", "pago": "Pago", "active": "Ativo", "ativo": "Ativo",
    "status": "Situação", "date": "Data", "data": "Data",
    "createdAt": "Data de cadastro", "updatedAt": "Última atualização",
    "employees": "Funcionários", "funcionarios": "Funcionários",
    "companies": "Empresas", "empresas": "Empresas",
    "pharmacies": "Farmácias", "farmacias": "Farmácias",
    "products": "Produtos", "produtos": "Produtos",
    "purchases": "Compras", "compras": "Compras", "sales": "Vendas",
    "transactions": "Movimentações", "movimentacoes": "Movimentações",
    "observacoes": "Observações", "notes": "Observações",
}

# Correspondência exata depois da normalização. "saltos" e "hashPedido", por
# exemplo, são dados comuns e não devem desaparecer do relatório.
SECRET_KEYS = frozenset({
    "password", "passwordhash", "hashedpassword", "passwd", "pwd",
    "senha", "hashsenha", "senhahash", "hash", "salt", "passwordsalt",
    "token", "tokens", "accesstoken", "refreshtoken", "idtoken",
    "resettoken", "passwordresettoken", "verificationtoken", "authtoken",
    "secret", "secrets", "sessionsecret", "clientsecret", "jwtsecret",
    "apikey", "apikeys", "privatekey", "secretkey", "accesskeysecret",
    "credential", "credentials", "credencial", "credenciais",
    "connectionstring", "mongodburi", "databaseurl", "databaseuri",
    "authorization", "cookie", "cookies", "sessionid", "sessiontoken",
})


def _normalized_key(key: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(key))
    return "".join(ch.lower() for ch in normalized if ch.isascii() and ch.isalnum())


def label(key: str) -> str:
    key = str(key)
    if key in LABELS:
        return LABELS[key]
    spaced = re.sub(r"([a-zá-ú0-9])([A-ZÁ-Ú])", r"\1 \2", key)
    spaced = re.sub(r"[_-]+", " ", spaced).strip()
    return spaced[:1].upper() + spaced[1:] if spaced else "Campo sem nome"


def load_config(path: Path | None) -> dict:
    """Carrega regras explícitas; ausência de arquivo não pressupõe moeda."""
    if path is None:
        return {"currency_fields": {}, "references": {}}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Não foi possível ler a configuração JSON do relatório.") from exc
    return _validate_config(data)


def _validate_config(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("A configuração do relatório deve ser um objeto JSON.")
    unknown = set(data) - {"currency_fields", "references"}
    if unknown:
        raise ValueError("A configuração aceita somente currency_fields e references.")
    result = {"currency_fields": {}, "references": {}}
    for kind in result:
        mapping = data.get(kind, {})
        if not isinstance(mapping, dict):
            raise ValueError(f"{kind} deve conter um objeto de regras por campo.")
        for key, rule in mapping.items():
            if not isinstance(key, str) or "." not in key or any(not p for p in key.split(".")):
                raise ValueError("Identifique cada regra como colecao.campo; use * para listas.")
            if not isinstance(rule, dict):
                raise ValueError(f"A regra de {key} deve ser um objeto JSON.")
            if kind == "currency_fields":
                if set(rule) - {"currency", "unit", "decimal_separator"}:
                    raise ValueError(f"Opção monetária desconhecida em {key}.")
                item = {"currency": "BRL", "unit": "reais", "decimal_separator": ".", **rule}
                if item["currency"] != "BRL" or item["unit"] not in ("reais", "centavos") or item["decimal_separator"] not in (".", ","):
                    raise ValueError(f"Em {key}, use currency BRL, unit reais/centavos e decimal_separator . ou ,.")
            else:
                if set(rule) != {"collection", "key", "label"}:
                    raise ValueError(f"Em {key}, informe collection, key e label para resolver a referência.")
                if any(not isinstance(v, str) or not v.strip() for v in rule.values()):
                    raise ValueError(f"As opções de referência de {key} devem ser textos preenchidos.")
                if any(not part for field in (rule["key"], rule["label"]) for part in field.split(".")):
                    raise ValueError(f"O caminho da referência de {key} está inválido.")
                # A configuração também não pode transformar uma credencial em
                # título ou ID visível por meio da resolução de referência.
                if any(_normalized_key(part) in SECRET_KEYS for field in (rule["key"], rule["label"]) for part in field.split(".")):
                    raise ValueError(f"A referência de {key} aponta para um campo de acesso protegido.")
                item = dict(rule)
            if key in result["currency_fields"] or key in result["references"]:
                raise ValueError(f"O campo {key} possui regras conflitantes de moeda e referência.")
            result[kind][key] = item
    return result


def _is_decimal128(value: Any) -> bool:
    return type(value).__name__ == "Decimal128" and callable(getattr(value, "to_decimal", None))


def _is_objectid(value: Any) -> bool:
    return type(value).__name__ == "ObjectId" and bool(re.fullmatch(r"[0-9a-fA-F]{24}", str(value)))


def _unwrap(value: Any) -> Any:
    if _is_decimal128(value):
        return value.to_decimal()
    if _is_objectid(value):
        return str(value)
    if not isinstance(value, dict) or len(value) != 1:
        return value
    key, raw = next(iter(value.items()))
    if key == "$oid" and isinstance(raw, str):
        return raw
    if key in ("$numberInt", "$numberLong") and isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return raw
    if key in ("$numberDouble", "$numberDecimal") and isinstance(raw, str):
        try:
            return Decimal(raw)
        except InvalidOperation:
            return raw
    if key == "$date":
        try:
            if isinstance(raw, dict) and set(raw) == {"$numberLong"}:
                milliseconds = Decimal(str(raw["$numberLong"]))
                if not milliseconds.is_finite() or milliseconds != milliseconds.to_integral_value():
                    return raw["$numberLong"]
                return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(milliseconds))
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=raw)
            if isinstance(raw, str):
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except (ValueError, TypeError, OverflowError, InvalidOperation):
            return str(raw)
    return value


def _scalar_text(value: Any) -> str:
    value = _unwrap(value)
    if value is None:
        return "Não informado na origem"
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, bytes):
        return "Binário (hexadecimal): " + value.hex()
    return str(value)


def _decimal_value(value: Any, separator: str) -> Decimal:
    value = _unwrap(value)
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Tipo não monetário")
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("R$"):
            raw = raw[2:].strip()
        if separator == ",":
            pattern = r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?(?:[eE][+-]?\d+)?"
            if not re.fullmatch(pattern, raw):
                raise ValueError("Separador monetário inválido")
            raw = raw.replace(".", "").replace(",", ".")
        else:
            pattern = r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?(?:[eE][+-]?\d+)?"
            if not re.fullmatch(pattern, raw):
                raise ValueError("Separador monetário inválido")
            raw = raw.replace(",", "")
        number = Decimal(raw)
    else:
        number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Valor não finito")
    return number


def _currency(value: Any, rule: dict) -> str:
    number = _decimal_value(value, rule.get("decimal_separator", "."))
    # Números extremos permanecem legíveis no valor bruto; nunca alocar uma
    # string financeira com milhões de casas por causa de uma entrada inválida.
    if abs(number.adjusted()) > 10000:
        raise ValueError("Valor fora do intervalo de formatação")
    with localcontext() as context:
        context.prec = max(32, len(number.as_tuple().digits) + abs(number.as_tuple().exponent) + 8)
        if rule.get("unit", "reais") == "centavos":
            number /= 100
        rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rendered = format(rounded, ",.2f").replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return "R$ " + rendered


_ABSENT = object()


def _lookup(record: Any, path: str) -> Any:
    current = record
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _ABSENT
        current = current[part]
    return current


def _id_key(value: Any) -> tuple:
    value = _unwrap(value)
    # Python considera True == 1; o identificador original deve conservar o tipo.
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, str):
        return ("text", value)
    if isinstance(value, (int, Decimal)):
        return ("number", str(value))
    if isinstance(value, float):
        return ("float", repr(value))
    return (type(value).__name__, repr(value))


def _reference(value: Any, rule: dict, group: Any, dataset: Any) -> tuple[str, str]:
    identifier = _scalar_text(value)
    matches = []
    for target_group in dataset.groups:
        if target_group.database != group.database or target_group.name != rule["collection"]:
            continue
        for candidate in target_group.records:
            target_id = _lookup(candidate, rule["key"])
            if target_id is not _ABSENT and _id_key(target_id) == _id_key(value):
                matches.append(candidate)
    if not matches:
        return f"Referência não localizada (ID: {identifier})", "unresolved"
    if len(matches) > 1:
        return f"Referência ambígua: {len(matches)} registros (ID: {identifier})", "unresolved"
    title = _lookup(matches[0], rule["label"])
    if title is _ABSENT or title is None or (isinstance(title, str) and not title.strip()):
        return f"Referência sem nome preenchido (ID: {identifier})", "unresolved"
    title = _unwrap(title)
    if isinstance(title, (dict, list)):
        return f"Referência com nome não escalar (ID: {identifier})", "unresolved"
    return f"{_scalar_text(title)} (ID: {identifier})", "filled"


def record_title(record: dict, number: int) -> str:
    for key in ("nome", "name", "razaoSocial", "description", "descricao", "pergunta", "question"):
        if key not in record:
            continue
        value = _unwrap(record[key])
        if value is None or isinstance(value, (dict, list)) or (isinstance(value, str) and not value.strip()):
            continue
        text = _scalar_text(value)
        return text if len(text) <= 120 else text[:117] + "..."
    return f"Registro {number}"


def record_fields(record: dict, group: Any, dataset: Any, config: dict) -> list[FieldValue]:
    """Expande todas as folhas sem alterar o registro nem o conjunto de origem."""
    config = _validate_config(config or {})
    fields: list[FieldValue] = []

    def append(path: str, labels: list[str], text: str, status: str = "filled") -> None:
        fields.append(FieldValue(path or "(registro)", " > ".join(labels) or "Registro", text, status))

    def walk(value: Any, path: str, schema_path: str, parts: list[str]) -> None:
        value = _unwrap(value)
        if value is None:
            append(path, parts, "Não informado na origem", "missing")
            return
        if isinstance(value, str) and not value.strip():
            append(path, parts, "Em branco na origem", "blank")
            return
        if isinstance(value, dict):
            if not value:
                append(path, parts, "Nenhum item registrado", "empty")
                return
            added_before = len(fields)
            for key, child in value.items():
                key = str(key)
                if key == "__v":
                    continue
                child_path = f"{path}.{key}" if path else key
                child_schema = f"{schema_path}.{key}" if schema_path else key
                child_parts = parts + [label(key)]
                if _normalized_key(key) in SECRET_KEYS:
                    append(child_path, child_parts, "Conteúdo de acesso omitido", "omitted")
                else:
                    walk(child, child_path, child_schema, child_parts)
            if len(fields) == added_before:
                append(path, parts, "Sem campos de consulta", "empty")
            return
        if isinstance(value, list):
            if not value:
                append(path, parts, "Nenhum item registrado", "empty")
            for index, item in enumerate(value, start=1):
                walk(item, f"{path}[{index}]", f"{schema_path}.*" if schema_path else "*", parts + [f"Item {index}"])
            return
        rule_key = f"{group.name}.{schema_path}"
        if rule_key in config["currency_fields"]:
            try:
                append(path, parts, _currency(value, config["currency_fields"][rule_key]))
            except (ValueError, InvalidOperation, OverflowError):
                append(path, parts, _scalar_text(value) + " (valor original; formatação monetária não aplicada)", "invalid")
        elif rule_key in config["references"]:
            rendered, status = _reference(value, config["references"][rule_key], group, dataset)
            append(path, parts, rendered, status)
        else:
            append(path, parts, _scalar_text(value))

    walk(record, "", "", [])
    return fields
