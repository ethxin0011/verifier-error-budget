"""Reference normalizers (DeepSeek-Math / MATH lineage)."""

import re


def _fix_fracs(s):
    parts = s.split("\\frac")
    out = parts[0]
    for sub in parts[1:]:
        out += "\\frac"
        if sub.startswith("{"):
            out += sub
        elif len(sub) >= 2:
            a = sub[0]
            b = sub[1]
            rest = sub[2:]
            if b != "{":
                out += "{" + a + "}{" + b + "}" + rest
            else:
                out += "{" + a + "}" + b + rest
        else:
            return s
    return out


def _fix_a_slash_b(s):
    if len(s.split("/")) != 2:
        return s
    a, b = s.split("/")
    try:
        ia = int(a)
        ib = int(b)
    except Exception:
        return s
    if s == "{}/{}".format(ia, ib):
        return "\\frac{" + str(ia) + "}{" + str(ib) + "}"
    return s


def _fix_sqrt(s):
    return re.sub(r"\\sqrt(-?[0-9.a-zA-Z]+)", r"\\sqrt{\1}", s)


def _remove_right_units(s):
    t = re.sub(r"\\text\{.*?\}$", "", s).strip()
    return t if t else s


def strip_string(s):
    s = str(s).strip()
    s = s.replace("\n", "")
    s = s.rstrip(".")
    s = s.replace("\\!", "")
    if s.startswith("\\text{") and s.endswith("}"):
        s = s[6:-1]
    for alias in ("tfrac", "dfrac", "cfrac"):
        s = s.replace(alias, "frac")
    s = s.replace("\\left", "").replace("\\right", "")
    s = _remove_right_units(s)
    s = s.replace("\\$", "").replace("$", "")
    s = s.replace("\\%", "").replace("%", "")
    s = s.replace(" ", "").replace(",", "")
    s = _fix_sqrt(s)
    s = _fix_fracs(s)
    s = _fix_a_slash_b(s)
    if s.startswith("."):
        s = "0" + s
    if s.endswith(".0"):
        s = s[:-2]
    return s


def parse_digits(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        pass
    t = str(s).strip()
    if t.endswith("%"):
        try:
            return float(t[:-1].replace(",", "")) / 100
        except Exception:
            return None
    return None
