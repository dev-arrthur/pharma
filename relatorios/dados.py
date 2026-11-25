"""Leitura de dados reais para relatórios, sem escrever no banco de origem.

JSON Extended conserva seus marcadores BSON como objetos; o formatador decide
como exibi-los. Assim a importação de arquivos funciona sem instalar PyMongo.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


@dataclass
class Group:
    database: str
    name: str
    records: list[dict]
    state: str = "complete"
    error: str = ""


@dataclass
class Dataset:
    groups: list[Group]
    source_label: str
    warnings: list[str] = field(default_factory=list)


class DataError(ValueError):
    """Falha de entrada com uma mensagem que não expõe credenciais."""


SUPPORTED_SUFFIXES = {".json", ".jsonl", ".ndjson", ".csv"}
SYSTEM_DATABASES = {"admin", "local", "config"}
LOCAL_DATABASE = "Importação local"
AUTH_COLLECTIONS = {
    "session", "sessions", "authsession", "authsessions",
    "token", "tokens", "accesstoken", "accesstokens",
    "refreshtoken", "refreshtokens", "resettoken", "resettokens",
    "credential", "credentials", "password", "passwords",
    "secret", "secrets", "apikey", "apikeys",
    "passwordreset", "passwordresets", "passwordresettoken",
    "passwordresettokens",
}


def _constant_error(_value: str):
    raise ValueError("Constante JSON não finita")


def _decode_json(text: str):
    return json.loads(text, parse_float=Decimal, parse_constant=_constant_error)


def _documents(value, context: str) -> tuple[list[dict], str]:
    if not isinstance(value, list):
        return [], f"{context}: era esperada uma lista de registros."
    records = [record for record in value if isinstance(record, dict)]
    invalid = len(value) - len(records)
    error = (
        f"{context}: {invalid} entrada(s) não são objetos e não puderam ser importadas."
        if invalid else ""
    )
    return records, error


def _group(database: str, name: str, records: list[dict], error: str = "") -> Group:
    return Group(database, name, records, "partial" if error else "complete", error)


def _load_json(path: Path, text: str) -> list[Group]:
    try:
        value = _decode_json(text)
    except (ValueError, RecursionError):
        raise DataError("O arquivo JSON está inválido ou incompleto.") from None
    if isinstance(value, dict) and "database" in value and "collections" in value:
        database = value["database"]
        collections = value["collections"]
        if not isinstance(database, str) or not database.strip():
            raise DataError("O envelope JSON precisa de um nome de base em 'database'.")
        if not isinstance(collections, dict):
            raise DataError("O campo 'collections' precisa conter categorias e listas de registros.")
        groups = []
        for name, rows in collections.items():
            if not isinstance(name, str) or not name.strip():
                groups.append(_group(database, path.stem, [], "Uma categoria está sem nome."))
                continue
            records, error = _documents(rows, f"Categoria {name}")
            groups.append(_group(database, name, records, error))
        return groups
    if isinstance(value, dict) and "rows" in value and "total" in value:
        records, error = _documents(value["rows"], "Exportação de página")
        total = value["total"]
        reasons = [error] if error else []
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            reasons.append("O total informado na exportação de página é inválido.")
        elif total > len(records):
            reasons.append(
                f"Exportação parcial de página: {len(records)} de {total} registros presentes. "
                "Exporte a categoria completa para incluir os demais."
            )
        elif total < len(records):
            reasons.append("O total informado é menor que a quantidade de registros no arquivo.")
        return [_group(LOCAL_DATABASE, path.stem, records, " ".join(reasons))]
    if isinstance(value, list):
        records, error = _documents(value, "Arquivo JSON")
        return [_group(LOCAL_DATABASE, path.stem, records, error)]
    if isinstance(value, dict):
        return [_group(LOCAL_DATABASE, path.stem, [value])]
    raise DataError("O JSON deve conter um objeto, uma lista de objetos ou um envelope de categorias.")


def _load_lines(path: Path, text: str) -> list[Group]:
    records = []
    invalid_lines = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = _decode_json(line)
            if not isinstance(row, dict):
                raise ValueError("Não é um objeto")
        except (ValueError, RecursionError):
            invalid_lines.append(number)
        else:
            records.append(row)
    error = ""
    if invalid_lines:
        first = ", ".join(str(line) for line in invalid_lines[:8])
        suffix = " e outras" if len(invalid_lines) > 8 else ""
        error = (
            f"{len(invalid_lines)} linha(s) inválida(s) no JSONL/NDJSON "
            f"(linhas {first}{suffix}); os registros válidos foram preservados."
        )
    return [_group(LOCAL_DATABASE, path.stem, records, error)]


def _load_csv(path: Path, text: str) -> list[Group]:
    try:
        dialect = csv.Sniffer().sniff(text[:16384], delimiters=",;")
        delimiter = dialect.delimiter
    except csv.Error:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        fields = reader.fieldnames
    except csv.Error:
        raise DataError("O cabeçalho do CSV está inválido.") from None
    if not fields:
        raise DataError("O CSV não contém cabeçalhos.")
    # Só os cabeçalhos são normalizados. Valores, espaços, zeros e códigos ficam intactos.
    fields = [name.strip() for name in fields]
    if any(not name for name in fields) or len(fields) != len(set(fields)):
        raise DataError("O CSV contém cabeçalhos vazios ou repetidos.")
    reader.fieldnames = fields
    legacy = "documento_json" in fields and "_id" in fields
    records = []
    invalid_lines = []
    parse_error = False
    try:
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                invalid_lines.append(reader.line_num)
                continue
            if legacy:
                try:
                    document = _decode_json(row["documento_json"])
                    if not isinstance(document, dict):
                        raise ValueError("Documento não é objeto")
                except (ValueError, RecursionError):
                    invalid_lines.append(reader.line_num)
                    continue
                records.append(document)
            else:
                records.append(dict(row))
    except csv.Error:
        parse_error = True
        invalid_lines.append(reader.line_num)
    error = ""
    if invalid_lines:
        first = ", ".join(str(line) for line in invalid_lines[:8])
        suffix = " e outras" if len(invalid_lines) > 8 else ""
        error = (
            f"{len(invalid_lines)} linha(s) inválida(s) no CSV (linhas {first}{suffix}). "
            "Os registros válidos foram preservados."
        )
        if parse_error:
            error += " A leitura parou no erro de estrutura; o arquivo pode conter registros adicionais."
    return [_group(LOCAL_DATABASE, path.stem, records, error)]


def _ignored_file(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".metadata.json") or name in {
        "config-relatorio.json", "config-relatorio.example.json",
    }


def _read_file(path: Path) -> list[Group]:
    try:
        raw = path.read_bytes()
    except OSError:
        raise DataError("Não foi possível abrir o arquivo. Confira a permissão de leitura.") from None
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        if path.suffix.lower() != ".csv":
            raise DataError("O arquivo JSON precisa estar salvo em UTF-8.") from None
        try:
            text = raw.decode("cp1252")
        except UnicodeDecodeError:
            raise DataError("O CSV precisa estar salvo em UTF-8 ou Windows-1252.") from None
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _load_csv(path, text)
    if suffix in {".jsonl", ".ndjson"}:
        return _load_lines(path, text)
    return _load_json(path, text)


def load_files(path: Path) -> Dataset:
    """Importa um arquivo ou os arquivos suportados diretamente dentro de uma pasta."""
    path = Path(path)
    try:
        if path.is_dir():
            files = sorted(
                (item for item in path.iterdir()
                 if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES
                 and not _ignored_file(item)),
                key=lambda item: item.name.casefold(),
            )
            source = f"Pasta local: {path.name}"
        elif path.is_file():
            if path.suffix.lower() not in SUPPORTED_SUFFIXES or _ignored_file(path):
                raise DataError("Selecione JSON, JSONL, NDJSON ou CSV contendo registros, não metadados ou configuração.")
            files = [path]
            source = f"Arquivo local: {path.name}"
        else:
            raise DataError("Arquivo ou pasta não encontrado. Confira o caminho selecionado.")
    except OSError:
        raise DataError("Não foi possível ler a pasta selecionada. Confira as permissões.") from None
    if not files:
        raise DataError("A pasta não contém arquivos JSON, JSONL, NDJSON ou CSV para importar.")
    groups = []
    warnings = []
    for file_path in files:
        try:
            file_groups = _read_file(file_path)
        except DataError as exc:
            file_groups = [_group(LOCAL_DATABASE, file_path.stem, [], str(exc))]
        for group in file_groups:
            groups.append(group)
            if group.error:
                warnings.append(f"{file_path.name} / {group.name}: {group.error}")
    if not any(group.records for group in groups):
        message = "Nenhum registro válido foi encontrado nos arquivos selecionados."
        if warnings:
            message += " " + warnings[0]
        raise DataError(message)
    return Dataset(groups, source, warnings)


def _auth_collection(name: str) -> bool:
    normalized = name.casefold().replace("_", "").replace("-", "")
    return name.casefold().startswith("system.") or normalized in AUTH_COLLECTIONS


def _mongo_error(exc: Exception) -> str:
    """Não usa str(exc), que pode incluir URI, servidores ou credenciais."""
    name = type(exc).__name__
    code = getattr(exc, "code", None)
    if code == 18:
        return "Não foi possível autenticar no MongoDB. Confira a credencial configurada."
    if code == 13:
        return "A credencial não tem permissão para ler esta base ou categoria."
    if name in {"InvalidURI", "ConfigurationError", "InvalidName"}:
        return "A configuração de conexão ou o nome da base é inválido."
    if "Timeout" in name or code == 50:
        return "O tempo de consulta foi excedido. Confira a conexão e os IPs autorizados."
    if name in {"AutoReconnect", "ConnectionFailure"}:
        return "A conexão com o MongoDB foi interrompida durante a leitura."
    return "Não foi possível concluir a leitura. Confira a conexão e as permissões da credencial."


def load_mongo(uri: str, db_name: str | None) -> Dataset:
    """Lê bancos autorizados ou uma base explícita, com limites de tempo e sem gravações."""
    if not isinstance(uri, str) or not uri.strip():
        raise DataError("Informe a conexão MongoDB na configuração local.")
    if db_name is not None and (not isinstance(db_name, str) or not db_name.strip()):
        db_name = None
    if db_name and db_name.casefold() in SYSTEM_DATABASES:
        raise DataError("Selecione uma base de dados da aplicação; bases internas não são exportadas.")
    try:
        from pymongo import MongoClient
    except ImportError:
        raise DataError("Instale as dependências do gerador para consultar o MongoDB (requirements.txt).") from None
    groups = []
    warnings = [
        "A consulta não é um snapshot transacional: os registros podem mudar durante a leitura."
    ]
    try:
        with MongoClient(
            uri.strip(), serverSelectionTimeoutMS=12000, connectTimeoutMS=10000,
            socketTimeoutMS=60000, appname="MaximumRelatoriosLeitura",
        ) as client:
            client.admin.command("ping")
            if db_name:
                names = [db_name]
            else:
                available = client.admin.command(
                    "listDatabases", nameOnly=True, authorizedDatabases=True, maxTimeMS=15000,
                )
                names = sorted(
                    item["name"] for item in available.get("databases", [])
                    if isinstance(item.get("name"), str)
                    and item["name"].casefold() not in SYSTEM_DATABASES
                )
            for name in names:
                database = client[name]
                try:
                    with database.list_collections(
                        nameOnly=True, authorizedCollections=True, maxTimeMS=15000,
                    ) as cursor:
                        collection_names = sorted(
                            item["name"] for item in cursor
                            if isinstance(item.get("name"), str)
                            and not _auth_collection(item["name"])
                        )
                except Exception as exc:
                    error = _mongo_error(exc)
                    groups.append(_group(name, "Categorias indisponíveis", [], error))
                    warnings.append(f"Base {name}: {error}")
                    continue
                for collection_name in collection_names:
                    records = []
                    error = ""
                    try:
                        with database[collection_name].find({}).sort("_id", 1).batch_size(100).max_time_ms(120000) as cursor:
                            for row in cursor:
                                records.append(row)
                    except Exception as exc:
                        error = _mongo_error(exc)
                        warnings.append(f"{name} / {collection_name}: {error}")
                    groups.append(_group(name, collection_name, records, error))
    except DataError:
        raise
    except Exception as exc:
        raise DataError(_mongo_error(exc)) from None
    if not any(group.records for group in groups):
        raise DataError(
            "Nenhum registro pôde ser exportado. Confira a base selecionada, "
            "as permissões de leitura e se há registros nas categorias consultáveis."
        )
    return Dataset(groups, "MongoDB: " + (db_name or "bases autorizadas"), warnings)
