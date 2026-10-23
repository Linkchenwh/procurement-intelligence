"""Fetch official Microsoft PBIR schemas and validate authored definition files."""
import hashlib
import json

import jsonschema
import requests

from src.data_loader import ROOT

BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/"
CACHE = ROOT / "outputs/logs/powerbi_schemas"


class SchemaUnavailable(RuntimeError):
    """The official endpoint could not supply a schema; this is not a pass."""


def validate_project():
    CACHE.mkdir(parents=True, exist_ok=True)
    schemas = {}
    unavailable = {}
    session = requests.Session()
    session.trust_env = False

    def fetch(url):
        if url in schemas:
            return schemas[url]
        if url in unavailable:
            raise SchemaUnavailable(unavailable[url])
        if not url.startswith(BASE):
            raise ValueError(f"Unexpected remote schema: {url}")
        cached = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if cached.exists():
            obj = json.loads(cached.read_text(encoding="utf-8"))
        else:
            try:
                response = session.get(url, timeout=45)
                response.raise_for_status()
            except requests.RequestException as exc:
                unavailable[url] = f"{type(exc).__name__}: {exc}"
                raise SchemaUnavailable(unavailable[url]) from exc
            obj = response.json()
            cached.write_text(json.dumps(obj), encoding="utf-8")
        schemas[url] = obj
        if obj.get("$id", "").startswith(BASE):
            schemas[obj["$id"]] = obj
        return obj

    files = list((ROOT / "dashboard/powerbi/ProcurementIntelligence.Report/definition").rglob("*.json"))
    checked = 0
    skipped = []
    for path in files:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        if "$schema" not in obj:
            continue
        url = obj["$schema"]
        try:
            schema = fetch(url)
        except SchemaUnavailable:
            skipped.append(str(path.relative_to(ROOT)))
            continue
        resolver = jsonschema.RefResolver(base_uri=url, referrer=schema, store=schemas, handlers={"https": fetch})
        jsonschema.Draft7Validator(schema, resolver=resolver).validate(obj)
        checked += 1
    return {"definition_json_files": len(files), "validated_files": checked,
            "official_schemas_used": len(schemas),
            "result": "partial_public_schema_unavailable" if skipped else "passed",
            "unavailable_schemas": unavailable, "unvalidated_files": skipped,
            "note": "Unavailable versions are not downgraded or treated as validated. Native visual acceptance is separate."}


if __name__ == "__main__":
    result = validate_project()
    (ROOT / "dashboard/powerbi/schema_validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
