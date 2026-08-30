"""Authoritative user-facing product identity contract.

Raw ``name`` is receipt evidence, ``normalized_name`` supports search/matching,
and manually persisted ``canonical_name`` is the only grouping override.
"""


def effective_product_identity(raw_name: str, canonical_name: str | None = None) -> str:
    if canonical_name is not None and str(canonical_name).strip():
        return str(canonical_name)
    return str(raw_name or "")


def effective_product_identity_from_row(row) -> str:
    return effective_product_identity(row.get("name"), row.get("canonical_name"))


def effective_product_identity_sql(table: str = "items") -> str:
    prefix = f"{table}." if table else ""
    return (
        f"CASE WHEN {prefix}canonical_name IS NOT NULL "
        f"AND TRIM({prefix}canonical_name) <> '' "
        f"THEN {prefix}canonical_name ELSE {prefix}name END"
    )


def resolve_effective_product_identity(conn, identity_or_alias: str) -> str | None:
    """Resolve an exact identity first, then one unambiguous raw alias."""
    expression = effective_product_identity_sql("items")
    exact = conn.execute(
        f"SELECT {expression} FROM items WHERE {expression} = ? LIMIT 1",
        (identity_or_alias,),
    ).fetchone()
    if exact:
        return exact[0]

    aliases = conn.execute(
        f"SELECT DISTINCT {expression} FROM items WHERE name = ? ORDER BY {expression}",
        (identity_or_alias,),
    ).fetchall()
    return aliases[0][0] if len(aliases) == 1 else None
