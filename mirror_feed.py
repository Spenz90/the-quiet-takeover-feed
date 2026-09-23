#!/usr/bin/env python3
"""Mirror feed generator for "The Quiet Takeover".

Fetches the official platform RSS feed and injects the iTunes tags that
directory submissions require but the platform does not render:

    <itunes:author>Milo and Nadia</itunes:author>
    <itunes:owner>
      <itunes:name>Spenz</itunes:name>
      <itunes:email>spencererskine2009@gmail.com</itunes:email>
    </itunes:owner>

The itunes:email is Spenz's Gmail: Spotify sends its ownership-verification
code to that address during the "claim existing show" import flow.

Usage:
    python3 mirror_feed.py                 # write feed.xml next to this script
    python3 mirror_feed.py -o /path/feed.xml
    python3 mirror_feed.py --check /path/feed.xml   # validate a built file

Stdlib only. Idempotent: re-running over an already-mirrored feed replaces
(rather than duplicates) the injected tags. Episode GUIDs, enclosure URLs,
titles, and descriptions are passed through untouched.
"""

import argparse
import sys
import urllib.request
import xml.etree.ElementTree as ET

OFFICIAL_FEED_URL = (
    "https://muse.ai/podcasts/feed/1282384998281277/"
    "5435f036-8a3c-4b28-95f2-d6c2e4a05e29"
)
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NS = "http://www.w3.org/2005/Atom"

AUTHOR = "Milo and Nadia"
OWNER_NAME = "Spenz"
OWNER_EMAIL = "spencererskine2009@gmail.com"
CATEGORY = "Technology"  # Apple Podcasts requires itunes:category; Spotify/YouTube don't

# Keep the original prefixes on re-serialization instead of ns0:/ns1:.
ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("atom", ATOM_NS)


def fetch_official_feed(url: str = OFFICIAL_FEED_URL) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tqt-mirror-feed/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"official feed returned HTTP {resp.status}")
        return resp.read()


def inject_tags(xml_bytes: bytes) -> bytes:
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("no <channel> element in official feed")

    # Idempotency: drop any previously injected tags first.
    for tag in (f"{{{ITUNES_NS}}}author", f"{{{ITUNES_NS}}}owner",
                f"{{{ITUNES_NS}}}category"):
        for el in channel.findall(tag):
            channel.remove(el)

    author_el = ET.Element(f"{{{ITUNES_NS}}}author")
    author_el.text = AUTHOR
    owner_el = ET.Element(f"{{{ITUNES_NS}}}owner")
    name_el = ET.SubElement(owner_el, f"{{{ITUNES_NS}}}name")
    name_el.text = OWNER_NAME
    email_el = ET.SubElement(owner_el, f"{{{ITUNES_NS}}}email")
    email_el.text = OWNER_EMAIL
    category_el = ET.Element(f"{{{ITUNES_NS}}}category")
    category_el.set("text", CATEGORY)

    # Conventional placement: right after <title>.
    children = list(channel)
    try:
        title_idx = next(i for i, c in enumerate(children) if c.tag == "title")
    except StopIteration:
        title_idx = -1
    channel.insert(title_idx + 1, owner_el)
    channel.insert(title_idx + 1, category_el)
    channel.insert(title_idx + 1, author_el)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def validate(xml_bytes: bytes) -> list:
    """Return a list of problems (empty = valid)."""
    problems = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return [f"not well-formed XML: {e}"]
    channel = root.find("channel")
    if channel is None:
        return ["no <channel> element"]
    author = channel.find(f"{{{ITUNES_NS}}}author")
    owner = channel.find(f"{{{ITUNES_NS}}}owner")
    if author is None or (author.text or "").strip() != AUTHOR:
        problems.append("itunes:author missing or wrong")
    if owner is None:
        problems.append("itunes:owner missing")
    else:
        email = owner.find(f"{{{ITUNES_NS}}}email")
        name = owner.find(f"{{{ITUNES_NS}}}name")
        if email is None or (email.text or "").strip() != OWNER_EMAIL:
            problems.append("itunes:owner/itunes:email missing or wrong")
        if name is None or (name.text or "").strip() != OWNER_NAME:
            problems.append("itunes:owner/itunes:name missing or wrong")
    cat = channel.find(f"{{{ITUNES_NS}}}category")
    if cat is None or cat.get("text") != CATEGORY:
        problems.append("itunes:category missing or wrong")
    items = channel.findall("item")
    if not items:
        problems.append("no <item> episodes found")
    for item in items:
        enc = item.find("enclosure")
        if enc is None or not enc.get("url"):
            title = item.findtext("title") or "?"
            problems.append(f"item '{title[:40]}' has no enclosure url")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Quiet Takeover mirror feed.")
    ap.add_argument("-o", "--output", default="feed.xml",
                    help="where to write the mirrored feed")
    ap.add_argument("--source", default=OFFICIAL_FEED_URL,
                    help="official feed URL to mirror")
    ap.add_argument("--check", metavar="FILE",
                    help="validate an existing file instead of building")
    args = ap.parse_args()

    if args.check:
        with open(args.check, "rb") as f:
            problems = validate(f.read())
        if problems:
            print("INVALID:")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("OK: mirror feed valid")
        return 0

    xml_bytes = inject_tags(fetch_official_feed(args.source))
    problems = validate(xml_bytes)
    if problems:
        print("Refusing to write: generated feed failed validation:")
        for p in problems:
            print(f"  - {p}")
        return 1
    with open(args.output, "wb") as f:
        f.write(xml_bytes)
    print(f"wrote {args.output} ({len(xml_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
