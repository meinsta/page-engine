"""Offline checks against an in-memory stand-in for the cluster. Run: python3 test_offline.py"""
import json, os, re, tempfile

from fieldkit import qdrant as Q

from pageengine import build as B

words = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
ROWS = [{"id": "d1", "payload": {"source": "docs", "text": "Rotate a key and the old key keeps working for 24 hours."}},
        {"id": "d2", "payload": {"source": "docs", "text": "Route and driver data never leaves the region a workspace was created in."}},
        {"id": "d3", "payload": {"source": "docs", "text": "The default limit is 600 requests per minute for each workspace."}},
        {"id": "d4", "payload": {"source": "docs", "text": "Webhook events for one route always arrive in order."}},
        {"id": "f1", "payload": {"source": "field", "text": "Security blocks the rollout without key rotation.", "segment": "enterprise", "vertical": "grocery delivery"}}]


def _page(sections):
    Q.hybrid_query = lambda name, q, limit=1, flt=None, **k: sorted(
        [r for r in ROWS if r["payload"]["source"] == flt["must"][0]["match"]["value"] and words(q) & words(r["payload"]["text"])],
        key=lambda r: -len(words(q) & words(r["payload"]["text"])))[:limit]
    os.chdir(tempfile.mkdtemp())
    json.dump({"id": "p", "h1": "Pass Your Security Review", "cta": {"text": "Start Free", "url": "https://example.com"},
               "sections": sections}, open("page.json", "w"))


SEC = lambda lead, q="rotate a key old key keeps working": {"heading": "H", "proof": "security key rotation", "facts": [{"lead": lead, "q": q}]}


def test_a_clean_page_is_ready_and_every_detail_is_verbatim():
    _page([SEC("Rotate a key and keep the old one for 24 hours")])
    path, violations = B.build()
    md = open(path).read()
    assert violations == [] and "DRAFT" not in md
    assert "- **Rotate a key and keep the old one for 24 hours.** Rotate a key and the old key keeps working for 24 hours. `[d1]`" in md
    assert "> Customer (enterprise, grocery delivery): Security blocks the rollout" in md


def test_authored_words_are_judged_in_code():
    _page([SEC("Rotate a key and keep the old one for 72 hours"),                       # a number the docs do not state
           SEC("Rotate a key and the old key keeps working for 24 hours"),              # the sentence again, not a lead
           SEC("Enjoy peace of mind"),                                                  # retrieves nothing like its fact
           SEC("Rotate a key and keep the old key working for a full 24 hours with no changes to the app")])
    path, violations = B.build()
    joined = " | ".join(violations)
    assert "states ['72']" in joined and "repeats its sentence" in joined and "does not retrieve its own fact" in joined and "over 12 words" in joined
    assert open(path).read().startswith("> DRAFT: ")


def test_paid_track_cuts_to_three_sections_and_one_action():
    _page([SEC("Rotate a key and keep the old one for 24 hours")] * 5)
    assert open(B.build(track="paid")[0]).read().count("## H") == 3 and open(B.build(track="paid")[0]).read().count("[Start Free]") == 1
    assert open(B.build()[0]).read().count("## H") == 5 and open(B.build()[0]).read().count("[Start Free]") == 6


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
