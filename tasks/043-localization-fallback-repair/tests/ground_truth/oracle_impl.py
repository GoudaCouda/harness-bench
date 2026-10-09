def render_message(catalogs, parent_locales, locale, key, variables, count):
    def canonical(value):
        if type(value) is not str or not value:
            raise ValueError("locale")
        if value.casefold() == "root":
            return "root"
        parts = value.replace("_", "-").split("-")
        if (
            any(
                not part or not part.isalnum() or any(ord(ch) > 127 for ch in part)
                for part in parts
            )
            or not parts[0].isalpha()
        ):
            raise ValueError("locale")
        result = [parts[0].lower()]
        for part in parts[1:]:
            if len(part) == 4 and part.isalpha():
                result.append(part[0].upper() + part[1:].lower())
            elif len(part) == 2 and part.isalpha():
                result.append(part.upper())
            else:
                result.append(part.lower())
        return "-".join(result)

    def render(pattern):
        if type(pattern) is not str:
            raise ValueError("pattern")
        output = ""
        index = 0
        while index < len(pattern):
            if pattern[index] == "}":
                raise ValueError("brace")
            if pattern[index] != "{":
                output += pattern[index]
                index += 1
                continue
            end = index + 1
            while end < len(pattern) and pattern[end] != "}":
                if pattern[end] == "{":
                    raise ValueError("nested")
                end += 1
            if end == len(pattern):
                raise ValueError("brace")
            name = pattern[index + 1 : end]
            if (
                not name
                or name[0].isdigit()
                or any(not (ch.isalnum() or ch == "_") for ch in name)
            ):
                raise ValueError("placeholder")
            if name == "count" and count is not None:
                value = count
            elif name in variables:
                value = variables[name]
            else:
                raise ValueError("missing variable")
            if value is not None and type(value) not in (str, int, float, bool):
                raise ValueError("variable")
            output += str(value)
            index = end + 1
        return output

    if (
        type(catalogs) is not dict
        or type(parent_locales) is not dict
        or type(key) is not str
        or not key
        or type(variables) is not dict
        or any(type(k) is not str for k in variables)
    ):
        raise ValueError("root")
    normalized = {}
    for raw_locale, catalog in catalogs.items():
        name = canonical(raw_locale)
        if (
            name in normalized
            or type(catalog) is not dict
            or any(type(k) is not str or not k for k in catalog)
        ):
            raise ValueError("catalog")
        normalized[name] = catalog
    parents = {}
    for child, parent in parent_locales.items():
        child_name = canonical(child)
        parent_name = canonical(parent)
        if child_name in parents:
            raise ValueError("parent collision")
        parents[child_name] = parent_name
    requested = canonical(locale)
    chain = []
    seen = set()
    current = requested
    message = None
    used = None
    while True:
        if current in seen:
            raise ValueError("parent cycle")
        seen.add(current)
        chain.append(current)
        catalog = normalized.get(current, {})
        if key in catalog:
            message = catalog[key]
            used = current
            break
        if current == "root":
            break
        if current in parents:
            current = parents[current]
        elif "-" in current:
            current = "-".join(current.split("-")[:-1])
        else:
            current = "root"
    if used is None:
        raise ValueError("missing key")
    category = None
    if type(message) is dict:
        if (
            not message
            or "other" not in message
            or count is None
            or type(count) not in (int, float)
            or type(count) is bool
        ):
            raise ValueError("plural")
        for selector, pattern in message.items():
            if type(selector) is not str or type(pattern) is not str:
                raise ValueError("plural")
            if selector.startswith("="):
                number = selector[1:]
                if (
                    not number
                    or (
                        number[0] == "-"
                        and (len(number) == 1 or not number[1:].isdigit())
                    )
                    or (number[0] != "-" and not number.isdigit())
                ):
                    raise ValueError("selector")
            elif selector not in ("zero", "one", "two", "few", "many", "other"):
                raise ValueError("selector")
        integer = type(count) is int or (type(count) is float and count == int(count))
        exact = "=" + str(int(count)) if integer else None
        language = requested.split("-")[0]
        if exact in message:
            category = exact
        elif language == "en" and integer and count == 1:
            category = "one"
        elif language == "fr" and integer and count in (0, 1):
            category = "one"
        elif language == "ru" and integer:
            last = int(count) % 10
            last_two = int(count) % 100
            if last == 1 and last_two != 11:
                category = "one"
            elif last in (2, 3, 4) and last_two not in (12, 13, 14):
                category = "few"
            elif last == 0 or last in (5, 6, 7, 8, 9) or last_two in (11, 12, 13, 14):
                category = "many"
            else:
                category = "other"
        else:
            category = "other"
        message = message.get(category, message["other"])
    elif type(message) is not str:
        raise ValueError("message")
    return {
        "text": render(message),
        "locale_used": used,
        "plural_category": category,
        "fallback_chain": chain,
    }
