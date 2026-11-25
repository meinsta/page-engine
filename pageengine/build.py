"""build.py: one path from evidence to a page. A person (or their model) writes the H1, the section
headings and the short lead of each bullet. The engine supplies everything else verbatim from the
index, then judges the authored words in code.

  detail      a docs sentence, verbatim, with the id of its row
  proof       a field note, by segment and vertical
  lead        authored, then audited: it must retrieve its own fact, and state no number the fact lacks

A page with any violation is a DRAFT and the build exits 1, so a publish step can refuse it.

    python3 -m pageengine.build                  # page.json -> out/<id>.md, the product page
    python3 -m pageengine.build --track paid     # the paid landing cut: three sections, one action
"""
import json, os, re, sys

from fieldkit import approvals, qdrant as Q

COLL = os.environ.get("FIELD_COLLECTION", "grounding")
MAX_LEAD_WORDS, AUDIT_K, PAID_SECTIONS = 12, 1, 3
numbers = lambda s: set(re.findall(r"\d[\d,.]*\d|\d", s))


def _lane(q, source, limit):
    return Q.hybrid_query(COLL, q, limit=limit, flt={"must": [{"key": "source", "match": {"value": source}}]})


def check_lead(lead, fact):
    """Violations for one authored lead against the docs row it introduces."""
    text, out = fact["payload"]["text"], []
    if len(lead.split()) > MAX_LEAD_WORDS:
        out.append(f"lead is over {MAX_LEAD_WORDS} words")
    if approvals.norm(lead) == approvals.norm(text):
        out.append("lead repeats its sentence")
    if numbers(lead) - numbers(text):
        out.append(f"lead states {sorted(numbers(lead) - numbers(text))}, which its sentence does not")
    if fact["id"] not in [r["id"] for r in _lane(lead, "docs", AUDIT_K)]:
        out.append("lead does not retrieve its own fact")
    return out


def build(spec="page.json", track="product", out="out"):
    page = json.load(open(spec))
    sections = page["sections"][:PAID_SECTIONS] if track == "paid" else page["sections"]
    cta = f"[{page['cta']['text']}]({page['cta']['url']})"
    body, violations, subline = [], [], None
    if not page.get("h1"):
        violations.append("page has no H1")
    for s in sections:
        bullets = []
        for f in s["facts"]:
            rows = _lane(f["q"], "docs", 1)
            if not rows:
                violations.append(f"'{f['lead']}': no docs sentence found")
                continue
            violations += [f"'{f['lead']}': {v}" for v in check_lead(f["lead"], rows[0])]
            subline = subline or rows[0]["payload"]["text"]
            bullets.append(f"- **{f['lead']}.** {rows[0]['payload']['text']} `[{rows[0]['id']}]`")
        if not bullets:
            violations.append(f"section '{s['heading']}' is empty")
        proof = _lane(s["proof"], "field", 1) if s.get("proof") else []
        quote = [f"> Customer ({p['payload']['segment']}, {p['payload']['vertical']}): {p['payload']['text']} `[{p['id']}]`" for p in proof]
        body += [f"## {s['heading']}", ""] + bullets + [""] + quote + [""] + ([] if track == "paid" else [cta, ""])
    banner = [f"> DRAFT: {len(violations)} violation(s). This page does not publish."] + [f"> - {v}" for v in violations] + [""] if violations else []
    md = banner + [f"# {page.get('h1', '')}", "", subline or "", "", cta, ""] + body
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{page['id']}.{track}.md")
    open(path, "w").write("\n".join(md))
    return path, violations


if __name__ == "__main__":
    track = sys.argv[sys.argv.index("--track") + 1] if "--track" in sys.argv else "product"
    path, violations = build(track=track)
    print(f"{'DRAFT' if violations else 'READY'} {path}")
    for v in violations:
        print("  -", v)
    sys.exit(1 if violations else 0)
