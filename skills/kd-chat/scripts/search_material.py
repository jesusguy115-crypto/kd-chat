#!/usr/bin/env python3
"""Search the bundled public text snapshot. Standard library only; no network."""
import argparse
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    refs = Path(__file__).resolve().parents[1] / "references"
    query = args.query.casefold().strip()
    if not query:
        parser.error("query must not be empty")
    topics = json.loads((refs / "corpus-topics.json").read_text())["topics"]
    matched = [t for t in topics if any(c.casefold() in query for c in t["chinese_cues"])]
    preferred = {i for t in matched for i in t["reviewed_ids"]}
    terms = set(re.findall(r"[a-z][a-z0-9'-]{2,}", query))
    terms.update(t.casefold() for topic in matched for t in topic["english_terms"])
    terms -= {"the", "you", "your", "and", "are", "was", "with", "that"}
    results = []
    anchors = json.loads((refs / "knowledge-index.json").read_text())["records"]
    linked_ids = set()
    for r in anchors:
        cues = [c.casefold() for c in r["semantic_cues"]]
        hits = sum(c in query for c in cues)
        if hits:
            linked_ids.update(r.get("post_ids", []))
            results.append((40 + hits, {"kind": "knowledge_anchor", **r}))
    fan_context = json.loads((refs / "chinese-fan-context.json").read_text())["records"]
    for r in fan_context:
        hits = sum(alias.casefold() in query for alias in r["aliases"])
        if hits:
            results.append((35 + hits, {"kind": "chinese_fan_context", **r}))
    events = json.loads((refs / "recent-events.json").read_text())["events"]
    for r in events:
        hits = sum(c.casefold() in query for c in r["triggers"])
        if hits:
            results.append((35 + hits, {"kind": "dated_event", **r}))
    reviewed = {
        r["kd_id"]: r
        for r in json.loads((refs / "reviewed-dialogues.json").read_text())["records"]
    }
    for line in (refs / "public-corpus.jsonl").open():
        r = json.loads(line)
        text = r["original_text"].casefold()
        parent = (r.get("parent") or {}).get("text", "").casefold()
        score = sum(3 for term in terms if term in text)
        score += sum(1 for term in terms if term in parent)
        score += 15 if r["id"] in preferred else 0
        score += 25 if r["id"] in linked_ids else 0
        if query in text or query in parent:
            score += 10
        if score:
            result = {"kind": "public_post", **r}
            if r["id"] in reviewed:
                result["reviewed_observation"] = reviewed[r["id"]]["response_observation"]
                result["observation_is_design_inference"] = True
            if len(result["original_text"]) > 2400:
                result["original_text"] = result["original_text"][:2400]
                result["output_excerpt_truncated"] = True
            results.append((score, result))
    results.sort(key=lambda item: (-item[0], str(item[1].get("id", item[1].get("key", "")))))
    print(json.dumps({
        "query": args.query,
        "matched_topics": [t["topic"] for t in matched],
        "method": "词项扩展与已读样本优先，不是语义模型；候选需要阅读确认。",
        "limits": "公开文本快照并非全量历史；带直接上文不等于完整对话，未查看的媒体不可视为已读。",
        "results": [r for _, r in results[:args.limit]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
