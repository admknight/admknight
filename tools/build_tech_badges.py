#!/usr/bin/env python3
"""Build self-contained Tech Arsenal SVG badges from pinned Simple Icons artwork.

26 recognizable vector logos, four preserved categories, no third-party
runtime image requests. Icons belong to their respective trademark owners.
"""
import argparse
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SIMPLE_ICONS_REV = "98820a4dc8c363ca72fa2c0d294ea4a0a9bba75d"
BASE = "https://raw.githubusercontent.com/simple-icons/simple-icons/"
# CSS3 and VS Code marks were removed from recent Simple Icons collections.
LEGACY = {"css3": "13.21.0", "visualstudiocode": "11.0.0"}

# category / display name / file id / source id / contrasting brand accent
TECHNOLOGIES = (
    ("Languages", "Python", "python", "python", "77BDF3"),
    ("Languages", "JavaScript", "javascript", "javascript", "F7DF72"),
    ("Languages", "TypeScript", "typescript", "typescript", "68B2EF"),
    ("Languages", "Go", "go", "go", "66CCDF"),
    ("Languages", "Kotlin", "kotlin", "kotlin", "A794FA"),
    ("Languages", "Bash", "bash", "gnubash", "87CD6B"),
    ("Languages", "HTML5", "html5", "html5", "F58A72"),
    ("Languages", "CSS3", "css3", "css3", "77B9FA"),
    ("Frameworks & Libraries", "Node.js", "nodejs", "nodedotjs", "86C87A"),
    ("Frameworks & Libraries", "React", "react", "react", "61DAFB"),
    ("Frameworks & Libraries", "FastAPI", "fastapi", "fastapi", "59D5B8"),
    ("Frameworks & Libraries", "Flask", "flask", "flask", "E3EEFA"),
    ("Frameworks & Libraries", "Express.js", "expressjs", "express", "C7D8E9"),
    ("DevOps & Cloud", "Docker", "docker", "docker", "64B9F7"),
    ("DevOps & Cloud", "GitHub Actions", "github-actions", "githubactions", "76ACFA"),
    ("DevOps & Cloud", "Linux", "linux", "linux", "F7CE61"),
    ("DevOps & Cloud", "Nginx", "nginx", "nginx", "58C77E"),
    ("DevOps & Cloud", "Cloudflare", "cloudflare", "cloudflare", "FFAA59"),
    ("DevOps & Cloud", "GitHub Pages", "github-pages", "githubpages", "D5E4F3"),
    ("Databases & Tools", "MongoDB", "mongodb", "mongodb", "77D995"),
    ("Databases & Tools", "PostgreSQL", "postgresql", "postgresql", "8CB7EB"),
    ("Databases & Tools", "Redis", "redis", "redis", "F78B8B"),
    ("Databases & Tools", "SQLite", "sqlite", "sqlite", "8DCDEA"),
    ("Databases & Tools", "Git", "git", "git", "FF8D74"),
    ("Databases & Tools", "VS Code", "vscode", "visualstudiocode", "62B8FA"),
    ("Databases & Tools", "Gradle", "gradle", "gradle", "8FD3D2"),
)
CATEGORIES = ("Languages", "Frameworks & Libraries", "DevOps & Cloud", "Databases & Tools")
ALLOWED_PATH = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9.,+\-eE\s]+$")


def source_url(icon_id):
    rev = LEGACY.get(icon_id, SIMPLE_ICONS_REV)
    return f"{BASE}{rev}/icons/{icon_id}.svg"


def fetch_icon(icon_id):
    request = urllib.request.Request(source_url(icon_id), headers={
        "Accept": "image/svg+xml", "User-Agent": "admknight-tech-badges/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError(f"Unexpected source HTTP {response.status}: {icon_id}")
        data = response.read(35000)
    return data


def paths_from_svg(data):
    root = ET.fromstring(data)
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("Icon source is not an SVG")
    box = root.attrib.get("viewBox", "0 0 24 24").split()
    if len(box) != 4 or box[:2] != ["0", "0"] or float(box[2]) != 24 or float(box[3]) != 24:
        raise ValueError("Unexpected source viewBox; cannot place icon accurately")
    paths = []
    for child in root.iter():
        if child.tag.rsplit("}", 1)[-1] != "path":
            continue
        d = child.attrib.get("d", "").strip()
        if not d or not ALLOWED_PATH.fullmatch(d):
            raise ValueError("Icon source has invalid SVG path geometry")
        paths.append(d)
    if not paths:
        raise ValueError("Icon source contains no recognizable vector paths")
    return paths


def badge_svg(technology, icon_paths):
    category, label, slug, icon_id, accent = technology
    width = max(112, 62 + round(len(label) * 8.0))
    color = f"#{accent}"
    vector = "".join(f'<path d="{html.escape(path, quote=True)}"/>' for path in icon_paths)
    safe_label = html.escape(label, quote=True)
    # A 24x24 official icon silhouette, a thin brand-color rail, and consistent type.
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="42" '
            f'viewBox="0 0 {width} 42" role="img" aria-label="{safe_label}">\n'
            f'<title>{safe_label}</title>\n'
            f'<rect x="0.5" y="0.5" width="{width - 1}" height="41" rx="9" '
            'fill="#11263A" stroke="#34536D"/>\n'
            f'<rect x="1" y="7" width="3" height="28" rx="1.5" fill="{color}"/>\n'
            f'<circle cx="27" cy="21" r="15" fill="{color}" fill-opacity="0.10"/>\n'
            f'<g transform="translate(15 9) scale(1)" fill="{color}">{vector}</g>\n'
            f'<text x="53" y="26" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="13" font-weight="700" letter-spacing=".15" fill="#EDF5FF">'
            f'{safe_label}</text>\n</svg>\n')


def verify(out_dir):
    expected = {item[2] + ".svg" for item in TECHNOLOGIES}
    existing = {p.name for p in out_dir.glob("*.svg")}
    if existing != expected:
        raise ValueError(f"Badge files mismatch: missing={expected - existing}, extra={existing - expected}")
    for item in TECHNOLOGIES:
        path = out_dir / (item[2] + ".svg")
        source = path.read_text(encoding="utf-8")
        element = ET.fromstring(source)
        if element.tag.rsplit("}", 1)[-1] != "svg":
            raise ValueError(f"Invalid badge SVG: {path}")
        if element.attrib.get("aria-label") != item[1]:
            raise ValueError(f"Incorrect label: {path}")
        if not any(n.tag.rsplit("}", 1)[-1] == "path" and n.attrib.get("d") for n in element.iter()):
            raise ValueError(f"Missing actual logo path: {path}")
        if "href=" in source or "<script" in source or "<image" in source:
            raise ValueError(f"Badge contains an external reference or script: {path}")
    print(f"PASS: {len(expected)} self-contained, valid technology SVG badges")


def build(out_dir):
    if len(TECHNOLOGIES) != 26 or len({item[2] for item in TECHNOLOGIES}) != 26:
        raise ValueError("Expected exactly 26 unique technologies")
    if tuple(dict.fromkeys(item[0] for item in TECHNOLOGIES)) != CATEGORIES:
        raise ValueError("Changed Tech Arsenal category ordering")
    out_dir.mkdir(parents=True, exist_ok=True)
    for item in TECHNOLOGIES:
        source = fetch_icon(item[3])
        paths = paths_from_svg(source)
        (out_dir / (item[2] + ".svg")).write_text(badge_svg(item, paths), encoding="utf-8")
        print(f"PASS: {item[1]} ({len(paths)} vector path(s))")
    verify(out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("assets/tech-badges"))
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing:
        verify(args.out)
    else:
        build(args.out)
