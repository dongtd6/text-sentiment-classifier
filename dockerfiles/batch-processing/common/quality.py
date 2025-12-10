def check_not_null(df, cols):
    for c in cols:
        if df.filter(col(c).isNull()).count() > 0:
            raise ValueError(f"Null values found in column {c}")
    logger.info("✅ No null values found.")
