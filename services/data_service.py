import os
import re
import json
import csv
import io
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy import text, inspect
from db.connection import get_engine
from rag.schema_indexer import index_schema
from db.redis_client import get_redis_client


def sanitize_identifier(name: str) -> str:
    """Sanitize table or column name to contain only alphanumeric characters and underscores."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    if not clean or clean[0].isdigit():
        clean = "tbl_" + clean
    return clean


_SAFE_IDENTIFIER_RE = re.compile(r'^[a-z][a-z0-9_]{0,63}$')


def validate_identifier(name: str) -> str:
    """Validate that a sanitized identifier is safe for SQL interpolation. Raises ValueError if not."""
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe SQL identifier rejected: '{name}'")
    return name


def infer_sql_type(values: List[Any]) -> str:
    """Infer SQLite/SQLAlchemy compatible column type from sample values."""
    non_nulls = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_nulls:
        return "TEXT"

    # Check Integer
    is_int = True
    for v in non_nulls:
        try:
            int(str(v).replace(",", ""))
        except (ValueError, TypeError):
            is_int = False
            break
    if is_int:
        return "INTEGER"

    # Check Float
    is_float = True
    for v in non_nulls:
        try:
            float(str(v).replace(",", "").replace("$", ""))
        except (ValueError, TypeError):
            is_float = False
            break
    if is_float:
        return "REAL"

    # Check Date / Timestamp
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$")
    if all(date_pattern.match(str(v).strip()) for v in non_nulls):
        return "TIMESTAMP"

    return "TEXT"


def parse_csv_or_json(content: bytes, filename: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse uploaded file bytes into a list of row dictionaries."""
    text_content = content.decode("utf-8-sig", errors="replace")
    base_name = os.path.splitext(os.path.basename(filename))[0]
    default_table_name = sanitize_identifier(base_name)

    if filename.lower().endswith(".json"):
        data = json.loads(text_content)
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    rows = v
                    break
            else:
                rows = [data]
        else:
            raise ValueError("Unsupported JSON format. Expected list of objects.")
    else:
        reader = csv.DictReader(io.StringIO(text_content))
        rows = [dict(row) for row in reader]

    if not rows:
        raise ValueError("Uploaded file is empty or contains no records.")

    return default_table_name, rows


def detect_relationships(tables: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Automatically detect foreign key relationships between tables based on naming conventions.
    E.g. orders.customer_id -> customers.customer_id (or customers.id).
    """
    relationships = []
    table_dict = {}

    for t in tables:
        tname = t["name"]
        cols = t["columns"]
        # Normalize column list to set of strings
        if cols and isinstance(cols[0], dict):
            col_names = {c["name"].lower(): c for c in cols}
        else:
            col_names = {str(c).lower(): {"name": str(c)} for c in cols}
        table_dict[tname.lower()] = {
            "name": tname,
            "columns": col_names
        }

    for from_tname, from_meta in table_dict.items():
        for from_col in from_meta["columns"].keys():
            # Check if column looks like a foreign key (e.g. customer_id, order_id)
            if from_col.endswith("_id") or from_col.endswith("id"):
                prefix = from_col[:-3] if from_col.endswith("_id") else from_col[:-2]
                if not prefix or prefix == from_tname:
                    continue

                # Candidate target table names: singular, plural, with 's' or 'es'
                candidates = [
                    prefix,
                    prefix + "s",
                    prefix + "es",
                    prefix + "_table",
                    "tbl_" + prefix
                ]
                if prefix.endswith("y"):
                    candidates.append(prefix[:-1] + "ies")

                matched_target_meta = None
                for target_candidate in candidates:
                    if target_candidate in table_dict and target_candidate != from_tname:
                        matched_target_meta = table_dict[target_candidate]
                        break
                    # Suffix match for prefixed tables (e.g. test_authors matches authors)
                    for cand_tname, cand_data in table_dict.items():
                        if cand_tname != from_tname and (cand_tname.endswith("_" + target_candidate) or cand_tname == target_candidate):
                            matched_target_meta = cand_data
                            break
                    if matched_target_meta:
                        break

                if matched_target_meta:
                    target_cols = matched_target_meta["columns"]

                    # Check if target table has the same column name or 'id'
                    target_col_matched = None
                    if from_col in target_cols:
                        target_col_matched = target_cols[from_col]["name"]
                    elif "id" in target_cols:
                        target_col_matched = target_cols["id"]["name"]
                    elif (prefix + "_id") in target_cols:
                        target_col_matched = target_cols[prefix + "_id"]["name"]

                    if target_col_matched:
                        rel = {
                            "from_table": from_meta["name"],
                            "from_column": from_meta["columns"][from_col]["name"],
                            "to_table": matched_target_meta["name"],
                            "to_column": target_col_matched
                        }
                        if rel not in relationships:
                            relationships.append(rel)

    return relationships


def get_all_relationships() -> List[Dict[str, str]]:
    """Return all detected relationships across all tables currently in the database."""
    tables = get_all_tables()
    engine = get_engine()
    detected = detect_relationships(tables)

    # Also inspect explicit SQLite/PostgreSQL foreign keys
    with engine.connect():
        inspector = inspect(engine)
        for tname in inspector.get_table_names():
            if tname.startswith("sqlite_") or tname.startswith("_"):
                continue
            try:
                for fk in inspector.get_foreign_keys(tname):
                    referred_table = fk.get("referred_table")
                    constrained_cols = fk.get("constrained_columns", [])
                    referred_cols = fk.get("referred_columns", [])
                    if referred_table and constrained_cols and referred_cols:
                        rel = {
                            "from_table": tname,
                            "from_column": constrained_cols[0],
                            "to_table": referred_table,
                            "to_column": referred_cols[0]
                        }
                        if rel not in detected:
                            detected.append(rel)
            except Exception:
                pass

    return detected


SAMPLE_TEST_TABLES = {
    "customers", "products", "orders", "order_items", "regional_sales",
    "sample_superstore", "test_authors", "test_books", "test_campaigns"
}


def is_sample_or_test_table(table_name: str) -> bool:
    """Check if a table is one of the built-in sample demo or testing tables."""
    t = table_name.lower()
    return t in SAMPLE_TEST_TABLES or t.startswith("test_") or t.startswith("sample_")


def purge_sample_tables(keep_custom: bool = True) -> List[str]:
    """
    Drop demo/testing tables from the database and remove them from schema.json and Redis cache.
    If keep_custom is True, only sample/test tables are dropped, preserving user-uploaded tables.
    If keep_custom is False, all tables are dropped.
    Returns list of dropped table names.
    """
    engine = get_engine()
    tables = get_all_tables()
    dropped = []

    with engine.connect() as conn:
        for t in tables:
            tname = t["name"]
            should_drop = (not keep_custom) or is_sample_or_test_table(tname)
            if should_drop:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {tname};"))
                    dropped.append(tname)
                except Exception as e:
                    print(f"Warning: Could not drop table {tname}: {e}")
        conn.commit()

    # Update schema.json
    schema_file = os.path.join(os.path.dirname(__file__), "..", "schema.json")
    try:
        if os.path.exists(schema_file):
            with open(schema_file, "r") as f:
                schema_data = json.load(f)
            schema_data = [t for t in schema_data if t.get("table") not in dropped]
            with open(schema_file, "w") as f:
                json.dump(schema_data, f, indent=2)

            # Update Redis cache
            redis_client = get_redis_client()
            if redis_client:
                try:
                    redis_client.delete("datavox:schema")
                    if schema_data:
                        index_schema(schema_data, redis_client)
                except Exception:
                    pass
    except Exception as e:
        print(f"Warning: Failed to update schema.json after purge: {e}")

    return dropped


def ingest_dataset(
    table_name: str,
    rows: List[Dict[str, Any]],
    description: Optional[str] = None,
    clear_sample_data: bool = False
) -> Dict[str, Any]:
    """Single table ingestion wrapper calling ingest_multiple_datasets."""
    res = ingest_multiple_datasets([{
        "table_name": table_name,
        "rows": rows,
        "description": description
    }], clear_sample_data=clear_sample_data)
    return res["tables_ingested"][0]


def ingest_multiple_datasets(
    dataset_items: List[Dict[str, Any]],
    clear_sample_data: bool = False
) -> Dict[str, Any]:
    """
    Ingest multiple datasets in a single batch, automatically detect relationships
    between them and existing database tables, and update schema.json with explicit foreign keys.
    If clear_sample_data is True, any pre-existing sample/test tables are removed first.
    """
    if not dataset_items:
        raise ValueError("No datasets provided for ingestion.")

    if clear_sample_data:
        purge_sample_tables(keep_custom=True)

    engine = get_engine()
    existing_tables = get_all_tables()

    # Pre-process all incoming items
    processed_items = []
    for item in dataset_items:
        tname = sanitize_identifier(item["table_name"])
        validate_identifier(tname)
        rows = item["rows"]
        if not rows:
            continue

        raw_keys = list(rows[0].keys())
        col_mapping = {k: sanitize_identifier(k) for k in raw_keys}
        sanitized_columns = list(col_mapping.values())
        for col_name in sanitized_columns:
            validate_identifier(col_name)

        # Infer column types
        col_types = {}
        for raw_k, clean_k in col_mapping.items():
            sample_vals = [r.get(raw_k) for r in rows[:100]]
            col_types[clean_k] = infer_sql_type(sample_vals)

        processed_items.append({
            "table_name": tname,
            "rows": rows,
            "description": item.get("description"),
            "col_mapping": col_mapping,
            "columns": sanitized_columns,
            "col_types": col_types
        })

    # Combine existing + incoming tables to detect all relationships
    combined_meta = []
    for et in existing_tables:
        combined_meta.append({
            "name": et["name"],
            "columns": [c["name"] for c in et["columns"]]
        })
    for pi in processed_items:
        # Check if updating existing table
        combined_meta = [m for m in combined_meta if m["name"] != pi["table_name"]]
        combined_meta.append({
            "name": pi["table_name"],
            "columns": pi["columns"]
        })

    all_relationships = detect_relationships(combined_meta)

    # Ingest each table into the database
    tables_ingested = []
    for pi in processed_items:
        tname = pi["table_name"]
        rows = pi["rows"]
        col_mapping = pi["col_mapping"]
        sanitized_columns = pi["columns"]
        col_types = pi["col_types"]

        col_defs = [f"{col} {col_types[col]}" for col in sanitized_columns]
        create_sql = f"CREATE TABLE IF NOT EXISTS {tname} (\n  id INTEGER PRIMARY KEY AUTOINCREMENT,\n  "
        create_sql += ",\n  ".join(col_defs) + "\n);"

        with engine.connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {tname};"))
            conn.execute(text(create_sql))

            insert_cols = ", ".join(sanitized_columns)
            placeholders = ", ".join([f":{col}" for col in sanitized_columns])
            insert_sql = text(f"INSERT INTO {tname} ({insert_cols}) VALUES ({placeholders})")

            prepared_rows = []
            for r in rows:
                clean_row = {}
                for raw_k, clean_k in col_mapping.items():
                    val = r.get(raw_k)
                    if val is not None and str(val).strip() != "":
                        target_type = col_types[clean_k]
                        if target_type == "INTEGER":
                            try:
                                clean_row[clean_k] = int(str(val).replace(",", ""))
                            except Exception:
                                clean_row[clean_k] = val
                        elif target_type == "REAL":
                            try:
                                clean_row[clean_k] = float(str(val).replace(",", "").replace("$", ""))
                            except Exception:
                                clean_row[clean_k] = val
                        else:
                            clean_row[clean_k] = str(val).strip()
                    else:
                        clean_row[clean_k] = None
                prepared_rows.append(clean_row)

            conn.execute(insert_sql, prepared_rows)
            conn.commit()

        tables_ingested.append({
            "table_name": tname,
            "rows_inserted": len(rows),
            "columns": sanitized_columns,
            "column_types": col_types
        })

    # Update schema.json with explicit relationship documentation
    schema_file = os.path.join(os.path.dirname(__file__), "..", "schema.json")
    try:
        if os.path.exists(schema_file):
            with open(schema_file, "r") as f:
                schema_data = json.load(f)
        else:
            schema_data = []

        for pi in processed_items:
            tname = pi["table_name"]
            sanitized_columns = pi["columns"]
            col_types = pi["col_types"]

            # Filter relationships involving this table
            outgoing_rels = [r for r in all_relationships if r["from_table"] == tname]
            incoming_rels = [r for r in all_relationships if r["to_table"] == tname]

            # Build column summary with foreign key notations
            col_descriptors = []
            for col in sanitized_columns:
                rel_match = next((r for r in outgoing_rels if r["from_column"] == col), None)
                if rel_match:
                    col_descriptors.append(f"{col} ({col_types[col]}, FK -> {rel_match['to_table']}.{rel_match['to_column']})")
                else:
                    col_descriptors.append(f"{col} ({col_types[col]})")

            columns_summary = "id (INTEGER PK), " + ", ".join(col_descriptors)

            # Build description with relationships
            desc_parts = [pi.get("description") or f"Dataset '{tname}' with {len(pi['rows'])} records."]
            if outgoing_rels:
                rel_str = ", ".join([f"{r['from_column']} -> {r['to_table']}({r['to_column']})" for r in outgoing_rels])
                desc_parts.append(f"Relationships: [{rel_str}].")
            if incoming_rels:
                ref_str = ", ".join([f"{r['from_table']}({r['from_column']})" for r in incoming_rels])
                desc_parts.append(f"Referenced by: [{ref_str}].")

            full_desc = " ".join(desc_parts)

            # Remove previous entry if updating
            schema_data = [t for t in schema_data if t.get("table") != tname]
            schema_data.append({
                "table": tname,
                "description": full_desc,
                "columns": columns_summary
            })

        with open(schema_file, "w") as f:
            json.dump(schema_data, f, indent=2)

        # Update Redis if connected
        redis_client = get_redis_client()
        if redis_client:
            try:
                index_schema(schema_data, redis_client)
            except Exception:
                pass

    except Exception as e:
        print(f"Warning: Failed to update schema.json: {e}")

    return {
        "tables_ingested": tables_ingested,
        "detected_relationships": all_relationships
    }


def get_all_tables() -> List[Dict[str, Any]]:
    """Return all non-system tables with row counts and column schemas."""
    engine = get_engine()
    tables_info = []

    with engine.connect() as conn:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        for tname in table_names:
            if tname.startswith("sqlite_") or tname.startswith("_"):
                continue

            try:
                count_res = conn.execute(text(f"SELECT COUNT(*) FROM {tname};"))
                row_count = count_res.scalar() or 0
            except Exception:
                row_count = 0

            columns = []
            for col in inspector.get_columns(tname):
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "primary_key": bool(col.get("primary_key", False))
                })

            tables_info.append({
                "name": tname,
                "row_count": row_count,
                "columns": columns
            })

    return tables_info


def get_table_data(table_name: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Return paginated rows and columns for a given table."""
    table_name = sanitize_identifier(table_name)
    validate_identifier(table_name)
    engine = get_engine()

    with engine.connect() as conn:
        count_res = conn.execute(text(f"SELECT COUNT(*) FROM {table_name};"))
        total_rows = count_res.scalar() or 0

        res = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit} OFFSET {offset};"))
        columns = list(res.keys())
        rows = [dict(row) for row in res.mappings().all()]

    return {
        "table_name": table_name,
        "total_rows": total_rows,
        "limit": limit,
        "offset": offset,
        "columns": columns,
        "rows": rows
    }
