def render_message(catalogs, parent_locales, locale, key, variables, count):
    """Broken truthy English-only resolver; repair from the contract."""
    chain = [locale]
    if "-" in locale:
        chain.append(locale.split("-")[0])
    chain.append("root")
    value = None
    used = None
    for item in chain:
        candidate = catalogs.get(item, {}).get(key)
        if candidate:
            value, used = candidate, item
            break
    if isinstance(value, dict):
        category = "one" if count == 1 else "other"
        value = value.get(category, value.get("other"))
    else:
        category = None
    for name, replacement in variables.items():
        value = value.replace("{" + name + "}", str(replacement))
    return {"text": value, "locale_used": used, "plural_category": category, "fallback_chain": chain}
