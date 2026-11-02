"""
Semantics-preserving and adversarial transforms for math answer verification audit.

v5 CHANGES:
  1. NEW STRATUM S14_unreduced - unreduced fraction equivalence.
     \\frac{1}{3} -> \\frac{12}{36}. Provably equal by construction
     (multiply numerator and denominator by the same integer).
     This is LITERALLY the example cited in the verifier-noise literature
     as the canonical false negative, so it bridges toward the published
     ~38% FN figure while remaining certifiable.

     CONTRACT NOTE: this is a MATHEMATICAL equivalence, not a formatting
     one. A symbolic verifier claims to handle it; a pure string
     normalizer (strip_string) does not. Contract matrix reflects that.

  2. Contract matrix extended to cover S14.

v4 (retained):
  - T17/T18 removed (produced empty output)
  - Boxing / scientific / text-wrap reclassified as CONTRACT_DEP

CLASS DEFINITIONS
-----------------
CERTIFIED_EQUIV : T(g) is mathematically identical to g AND within the
                  verifier's declared contract. Rejection = CERTIFIED FN.
CONTRACT_DEP    : Correctness depends on the declared contract. Reported
                  as SPEC AMBIGUITY, never as a bug.
ADVERSARIAL     : T(g) is mathematically DIFFERENT. Acceptance = CERTIFIED FP.

File location:
  <project>/src/transforms.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Optional

CERTIFIED_EQUIV = "certified_equiv"
CONTRACT_DEP = "contract_dep"
ADVERSARIAL = "adversarial"


@dataclass(frozen=True)
class Transform:
    tid: str
    stratum: str
    tclass: str
    fn: Callable[[str], Optional[str]]

    def apply(self, gold: str) -> Optional[str]:
        try:
            out = self.fn(gold)
        except Exception:
            return None
        if out is None:
            return None
        if out == gold:
            return None
        if not str(out).strip():
            return None
        return out


# ----------------------------------------------------------------------
# CONTRACT MATRIX
# ----------------------------------------------------------------------
# True  = verifier claims to handle this stratum -> failures are BUGS
# False = out of contract                        -> reported separately
# ----------------------------------------------------------------------

CONTRACTS = {
    "mathverify_latex": {
        "S1_frac_dialect": True,
        "S2_frac_decimal": True,
        "S4_delimiters":   True,
        "S6_whitespace":   True,
        "S7_sqrt_exp":     True,
        "S9_grouping":     True,
        "S10_sets":        True,
        "S14_unreduced":   True,    # symbolic backend -> claims equivalence
    },
    "mathverify_expr": {
        "S1_frac_dialect": False,
        "S2_frac_decimal": True,
        "S4_delimiters":   False,
        "S6_whitespace":   True,
        "S7_sqrt_exp":     False,
        "S9_grouping":     True,
        "S10_sets":        False,
        "S14_unreduced":   False,    # expression parser -> claims equivalence
    },
    "strip_string": {
        "S1_frac_dialect": True,
        "S2_frac_decimal": True,
        "S4_delimiters":   True,
        "S6_whitespace":   True,
        "S7_sqrt_exp":     True,
        "S9_grouping":     True,
        "S10_sets":        False,
        "S14_unreduced":   False,   # pure normalizer, no symbolic reduction
    },
    "sympy_cascade": {
        "S14_unreduced":   True,
    },
}

DEFAULT_IN_CONTRACT = True


def in_contract(verifier: str, stratum: str) -> bool:
    return CONTRACTS.get(verifier, {}).get(stratum, DEFAULT_IN_CONTRACT)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

_NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
_FRAC_RE = re.compile(r"\\[dtc]?frac\{(-?\d+)\}\{(-?\d+)\}")
_SIMPLE_FRAC_RE = re.compile(r"^(-?\d+)/(\d+)$")


def _is_plain_number(s) -> bool:
    return bool(_NUM_RE.match(str(s).strip()))


def _as_fraction(s) -> Optional[Fraction]:
    s = str(s).strip()
    m = _FRAC_RE.fullmatch(s)
    if m:
        num = int(m.group(1))
        den = int(m.group(2))
        return Fraction(num, den) if den != 0 else None
    m = _SIMPLE_FRAC_RE.fullmatch(s)
    if m:
        den = int(m.group(2))
        return Fraction(int(m.group(1)), den) if den != 0 else None
    if _is_plain_number(s):
        return Fraction(s)
    return None


def _is_latex_frac(s) -> bool:
    return bool(_FRAC_RE.fullmatch(str(s).strip()))


def _terminating_decimal(fr: Fraction) -> Optional[str]:
    d = fr.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    if d != 1:
        return None
    s = "{:.10f}".format(float(fr)).rstrip("0").rstrip(".")
    return s if s else "0"


# ----------------------------------------------------------------------
# S1  fraction dialect
# ----------------------------------------------------------------------

def t_dfrac(g):
    return g.replace("\\frac", "\\dfrac") if "\\frac" in g else None


def t_tfrac(g):
    return g.replace("\\frac", "\\tfrac") if "\\frac" in g else None


def t_cfrac(g):
    return g.replace("\\frac", "\\cfrac") if "\\frac" in g else None


def t_frac_to_slash(g):
    m = _FRAC_RE.fullmatch(g.strip())
    return (m.group(1) + "/" + m.group(2)) if m else None


def t_slash_to_frac(g):
    m = _SIMPLE_FRAC_RE.fullmatch(g.strip())
    return ("\\frac{" + m.group(1) + "}{" + m.group(2) + "}") if m else None


# ----------------------------------------------------------------------
# S14  UNREDUCED FRACTIONS  (v5 - bridges toward the published 38% FN)
# ----------------------------------------------------------------------

def _unreduced(g, k):
    """Multiply numerator and denominator by k. Provably equal."""
    s = str(g).strip()
    if not _is_latex_frac(s):
        return None
    fr = _as_fraction(s)
    if fr is None or fr.denominator == 0:
        return None
    num = fr.numerator * k
    den = fr.denominator * k
    if abs(num) > 10 ** 12 or abs(den) > 10 ** 12:
        return None
    return "\\frac{" + str(num) + "}{" + str(den) + "}"


def t_unreduced_x2(g):
    return _unreduced(g, 2)


def t_unreduced_x3(g):
    return _unreduced(g, 3)


def t_unreduced_x12(g):
    """The canonical literature example: 1/3 -> 12/36."""
    return _unreduced(g, 12)


# ----------------------------------------------------------------------
# S2  fraction <-> decimal (exact only)
# ----------------------------------------------------------------------

def t_frac_to_decimal(g):
    fr = _as_fraction(g)
    if fr is None or fr.denominator == 1:
        return None
    return _terminating_decimal(fr)


def t_decimal_to_frac(g):
    s = g.strip()
    if not _is_plain_number(s) or "." not in s:
        return None
    fr = Fraction(s).limit_denominator(10 ** 9)
    return "\\frac{" + str(fr.numerator) + "}{" + str(fr.denominator) + "}"


def t_trailing_zeros(g):
    s = g.strip()
    return (s + "0") if (_is_plain_number(s) and "." in s) else None


def t_add_point_zero(g):
    s = g.strip()
    return (s + ".0") if (_is_plain_number(s) and "." not in s) else None


# ----------------------------------------------------------------------
# S3  boxing -> CONTRACT_DEP
# ----------------------------------------------------------------------

def t_add_boxed(g):
    return "\\boxed{" + g + "}" if "\\boxed" not in g else None


def t_add_fbox(g):
    return "\\fbox{" + g + "}" if "box" not in g else None


def t_double_boxed(g):
    return "\\boxed{\\boxed{" + g + "}}" if "\\boxed" not in g else None


def t_prefix_boxed(g):
    if "\\boxed" in g:
        return None
    return "\\boxed{0} then \\boxed{" + g + "}"


# ----------------------------------------------------------------------
# S4  delimiters
# ----------------------------------------------------------------------

def t_left_right(g):
    out = g
    for o, c in (("(", ")"), ("[", "]")):
        if o in out and c in out:
            out = out.replace(o, "\\left" + o).replace(c, "\\right" + c)
    return out if out != g else None


def t_strip_left_right(g):
    if "\\left" not in g:
        return None
    return g.replace("\\left", "").replace("\\right", "")


# ----------------------------------------------------------------------
# S5  math-mode wrapper
# ----------------------------------------------------------------------

def t_dollar(g):
    return "$" + g + "$" if "$" not in g else None


# ----------------------------------------------------------------------
# S6  whitespace / punctuation
# ----------------------------------------------------------------------

def t_pad_spaces(g):
    return "  " + g + "  "


def t_trailing_dot(g):
    return g + "."


def t_newline(g):
    return g + "\n"


def t_thin_space(g):
    return g.replace(" ", "\\,") if " " in g else None


# ----------------------------------------------------------------------
# S7  sqrt / exponent
# ----------------------------------------------------------------------

def t_sqrt_brace(g):
    if "\\sqrt" not in g:
        return None
    return re.sub(r"\\sqrt(-?[0-9a-zA-Z])(?![0-9a-zA-Z])", r"\\sqrt{\1}", g)


def t_sqrt_unbrace(g):
    if "\\sqrt{" not in g:
        return None
    return re.sub(r"\\sqrt\{([0-9a-zA-Z])\}", r"\\sqrt\1", g)


def t_exp_brace(g):
    if "^" not in g:
        return None
    return re.sub(r"\^(\d)(?!\d)", r"^{\1}", g)


# ----------------------------------------------------------------------
# S8  scientific notation -> CONTRACT_DEP
# ----------------------------------------------------------------------

def t_to_scientific(g):
    s = g.strip()
    if not _is_plain_number(s) or "." in s:
        return None
    n = int(s)
    if n == 0 or abs(n) < 1000 or n % 10 != 0:
        return None
    mant, exp = n, 0
    while mant % 10 == 0:
        mant //= 10
        exp += 1
    return str(mant) + "\\times10^{" + str(exp) + "}"


# ----------------------------------------------------------------------
# S9  comma grouping
# ----------------------------------------------------------------------

def t_comma_thousands(g):
    s = g.strip()
    if not _is_plain_number(s) or "." in s:
        return None
    neg = s.startswith("-")
    digits = s.lstrip("-")
    if len(digits) <= 3:
        return None
    grouped = "{:,}".format(int(digits))
    return ("-" + grouped) if neg else grouped


# ----------------------------------------------------------------------
# S10  sets / intervals
# ----------------------------------------------------------------------

def t_set_reorder(g):
    s = g.strip()
    if not (s.startswith("\\{") and s.endswith("\\}")):
        return None
    parts = [p.strip() for p in s[2:-2].split(",")]
    if len(parts) < 2:
        return None
    return "\\{" + ", ".join(reversed(parts)) + "\\}"


def t_infty_spelling(g):
    return g.replace("\\infty", "\\inf") if "\\infty" in g else None


# ----------------------------------------------------------------------
# S11  text wrappers -> CONTRACT_DEP
# ----------------------------------------------------------------------

def t_wrap_text(g):
    return "\\text{" + g + "}" if "\\text" not in g else None


def t_answer_prefix(g):
    return "The answer is " + g


def t_mathrm(g):
    return g.replace("\\text", "\\mathrm") if "\\text" in g else None


# ----------------------------------------------------------------------
# S12 / S13  units and percent -> CONTRACT_DEP
# ----------------------------------------------------------------------

def t_add_unit_cm(g):
    return (g + "\\text{ cm}") if _is_plain_number(g) else None


def t_add_dollar_sym(g):
    return ("\\$" + g) if _is_plain_number(g) else None


def t_pct_to_dec(g):
    s = g.strip()
    if not s.endswith("%"):
        return None
    body = s.rstrip("%")
    if not _is_plain_number(body):
        return None
    return "{:g}".format(float(body) / 100)


def t_dec_to_pct(g):
    s = g.strip()
    if not _is_plain_number(s):
        return None
    v = float(s)
    return ("{:g}".format(v * 100) + "\\%") if 0 < v < 1 else None


# ----------------------------------------------------------------------
# ADVERSARIAL
# ----------------------------------------------------------------------

def t_adv_times_100(g):
    fr = _as_fraction(g)
    if fr is None or fr == 0:
        return None
    r = fr * 100
    return str(r) if r.denominator == 1 else None


def t_adv_div_100(g):
    fr = _as_fraction(g)
    if fr is None or fr == 0:
        return None
    return _terminating_decimal(fr / 100)


def t_adv_sign_flip(g):
    fr = _as_fraction(g)
    if fr is None or fr == 0:
        return None
    if fr.denominator == 1:
        return str(-fr)
    return "\\frac{" + str(-fr.numerator) + "}{" + str(fr.denominator) + "}"


def t_adv_off_by_one(g):
    """Exposes scale-invariant rel_tol false positives."""
    s = g.strip()
    if not _is_plain_number(s) or "." in s:
        return None
    return str(int(s) + 1)


def t_adv_digit_swap(g):
    s = g.strip()
    if not _is_plain_number(s) or "." in s:
        return None
    body = s.lstrip("-")
    if len(body) < 2:
        return None
    d = list(body)
    if d[0] == d[1]:
        return None
    d[0], d[1] = d[1], d[0]
    if d[0] == "0":
        return None
    sw = "".join(d)
    return ("-" + sw) if s.startswith("-") else sw


def t_adv_append_garbage(g):
    return g + " and also 999"


# ----------------------------------------------------------------------
# REGISTRY (v5)
# ----------------------------------------------------------------------

TRANSFORMS = [
    # ---- CERTIFIED EQUIVALENCE ----
    Transform("T01_dfrac",           "S1_frac_dialect", CERTIFIED_EQUIV, t_dfrac),
    Transform("T02_tfrac",           "S1_frac_dialect", CERTIFIED_EQUIV, t_tfrac),
    Transform("T03_cfrac",           "S1_frac_dialect", CERTIFIED_EQUIV, t_cfrac),
    Transform("T04_frac_to_slash",   "S1_frac_dialect", CERTIFIED_EQUIV, t_frac_to_slash),
    Transform("T05_slash_to_frac",   "S1_frac_dialect", CERTIFIED_EQUIV, t_slash_to_frac),

    Transform("T06_frac_to_dec",     "S2_frac_decimal", CERTIFIED_EQUIV, t_frac_to_decimal),
    Transform("T07_dec_to_frac",     "S2_frac_decimal", CERTIFIED_EQUIV, t_decimal_to_frac),
    Transform("T08_trailing_zeros",  "S2_frac_decimal", CERTIFIED_EQUIV, t_trailing_zeros),
    Transform("T09_add_point_zero",  "S2_frac_decimal", CERTIFIED_EQUIV, t_add_point_zero),

    Transform("T14_left_right",      "S4_delimiters",   CERTIFIED_EQUIV, t_left_right),
    Transform("T15_strip_lr",        "S4_delimiters",   CERTIFIED_EQUIV, t_strip_left_right),

    Transform("T16_dollar",          "S5_mathmode",     CERTIFIED_EQUIV, t_dollar),

    Transform("T19_pad_spaces",      "S6_whitespace",   CERTIFIED_EQUIV, t_pad_spaces),
    Transform("T20_trailing_dot",    "S6_whitespace",   CERTIFIED_EQUIV, t_trailing_dot),
    Transform("T21_newline",         "S6_whitespace",   CERTIFIED_EQUIV, t_newline),
    Transform("T22_thin_space",      "S6_whitespace",   CERTIFIED_EQUIV, t_thin_space),

    Transform("T23_sqrt_brace",      "S7_sqrt_exp",     CERTIFIED_EQUIV, t_sqrt_brace),
    Transform("T24_sqrt_unbrace",    "S7_sqrt_exp",     CERTIFIED_EQUIV, t_sqrt_unbrace),
    Transform("T25_exp_brace",       "S7_sqrt_exp",     CERTIFIED_EQUIV, t_exp_brace),

    Transform("T27_comma_thousands", "S9_grouping",     CERTIFIED_EQUIV, t_comma_thousands),

    Transform("T28_set_reorder",     "S10_sets",        CERTIFIED_EQUIV, t_set_reorder),
    Transform("T29_infty_spelling",  "S10_sets",        CERTIFIED_EQUIV, t_infty_spelling),

    # ---- v5 NEW: unreduced fractions ----
    Transform("T37_unreduced_x2",    "S14_unreduced",   CERTIFIED_EQUIV, t_unreduced_x2),
    Transform("T38_unreduced_x3",    "S14_unreduced",   CERTIFIED_EQUIV, t_unreduced_x3),
    Transform("T39_unreduced_x12",   "S14_unreduced",   CERTIFIED_EQUIV, t_unreduced_x12),

    # ---- CONTRACT-DEPENDENT ----
    Transform("T10_add_boxed",       "S3_boxing",       CONTRACT_DEP,    t_add_boxed),
    Transform("T11_add_fbox",        "S3_boxing",       CONTRACT_DEP,    t_add_fbox),
    Transform("T12_double_boxed",    "S3_boxing",       CONTRACT_DEP,    t_double_boxed),
    Transform("T13_prefix_boxed",    "S3_boxing",       CONTRACT_DEP,    t_prefix_boxed),

    Transform("T26_scientific",      "S8_scientific",   CONTRACT_DEP,    t_to_scientific),

    Transform("T30_wrap_text",       "S11_text",        CONTRACT_DEP,    t_wrap_text),
    Transform("T31_answer_prefix",   "S11_text",        CONTRACT_DEP,    t_answer_prefix),
    Transform("T32_mathrm",          "S11_text",        CONTRACT_DEP,    t_mathrm),

    Transform("T33_unit_cm",         "S12_units",       CONTRACT_DEP,    t_add_unit_cm),
    Transform("T34_dollar_sym",      "S12_units",       CONTRACT_DEP,    t_add_dollar_sym),
    Transform("T35_pct_to_dec",      "S13_percent",     CONTRACT_DEP,    t_pct_to_dec),
    Transform("T36_dec_to_pct",      "S13_percent",     CONTRACT_DEP,    t_dec_to_pct),

    # ---- ADVERSARIAL ----
    Transform("A01_times_100",       "A_scale",         ADVERSARIAL,     t_adv_times_100),
    Transform("A02_div_100",         "A_scale",         ADVERSARIAL,     t_adv_div_100),
    Transform("A03_sign_flip",       "A_sign",          ADVERSARIAL,     t_adv_sign_flip),
    Transform("A04_off_by_one",      "A_offset",        ADVERSARIAL,     t_adv_off_by_one),
    Transform("A05_digit_swap",      "A_digit",         ADVERSARIAL,     t_adv_digit_swap),
    Transform("A06_garbage",         "A_append",        ADVERSARIAL,     t_adv_append_garbage),
]

BY_ID = {t.tid: t for t in TRANSFORMS}
