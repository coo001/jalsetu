"""Officer actions and interim household advice, taken verbatim from the pinned table only."""
from . import pinned


def build(param_key: str) -> dict:
    srcs = pinned.sources()
    table = pinned.lines()
    officer, household = [], []
    for line_id in pinned.mapping()[param_key]:
        line = table[line_id]
        item = {
            "id": line_id,
            "text": line["text"],
            "ref": line["ref"],
            "sources": [{"id": s, "title": srcs[s]["title"], "url": srcs[s]["url"]} for s in line["source_ids"]],
        }
        (officer if line["kind"] == "officer" else household).append(item)
    return {"officer_actions": officer, "household_advice": household}
