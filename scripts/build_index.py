#!/usr/bin/env python3
"""Generate blog index pages from blogs.json (no client-side JavaScript)."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

BLOGS_PER_PAGE = 10
ROOT = Path(__file__).resolve().parent.parent
BLOGS_JSON = ROOT / "blogs.json"
SITE_JSON = ROOT / "site.json"
TEMPLATES_DIR = ROOT / "templates"
IMAGES_DIR = ROOT / "images"
TINY_DIR = IMAGES_DIR / "tiny"
THUMBNAIL_SCALE = "30%"
THUMBNAIL_SCALE_FACTOR = 0.3


def shrink_with_magick(magick: str, image: Path, output: Path) -> None:
    subprocess.run(
        [magick, str(image), "-resize", THUMBNAIL_SCALE, str(output)],
        check=True,
    )


def shrink_with_pillow(image: Path, output: Path) -> None:
    from PIL import Image

    with Image.open(image) as img:
        width, height = img.size
        new_size = (
            max(1, int(width * THUMBNAIL_SCALE_FACTOR)),
            max(1, int(height * THUMBNAIL_SCALE_FACTOR)),
        )
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        resized.save(output, format="JPEG", quality=85, optimize=True)


def shrink_images() -> None:
    TINY_DIR.mkdir(parents=True, exist_ok=True)
    images = sorted(IMAGES_DIR.glob("*.jpg"))
    if not images:
        print("No source images found in images/.")
        return

    magick = shutil.which("magick")
    method = "ImageMagick" if magick else None

    for image in images:
        output = TINY_DIR / image.name
        if magick:
            shrink_with_magick(magick, image, output)
        else:
            try:
                shrink_with_pillow(image, output)
                method = "Pillow"
            except ImportError as exc:
                raise SystemExit(
                    "Thumbnail generation requires ImageMagick (magick) or Pillow "
                    "(pip install Pillow)."
                ) from exc
        print(f"Shrunk {image.name} -> tiny/{image.name}")

    if method == "Pillow":
        print("Thumbnails generated using Pillow (install ImageMagick for magick CLI).")


def render_template(name: str, variables: dict[str, str]) -> str:
    content = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    for key, value in variables.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def load_site() -> dict:
    with SITE_JSON.open(encoding="utf-8") as f:
        return json.load(f)


def format_date(iso_date: str) -> str:
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return f"{dt.day} {dt.strftime('%B')} {dt.year}"


def render_blog_box(blog: dict) -> str:
    return render_template(
        "blog-box.html",
        {
            "URL": blog["url"],
            "TITLE": blog["title"],
            "DATE": blog["date"],
            "DATE_DISPLAY": format_date(blog["date"]),
            "EXCERPT": blog["excerpt"],
            "IMAGE": blog["image"],
            "IMAGE_ALT": blog["imageAlt"],
        },
    )


def render_pagination(current_page: int, total_pages: int) -> str:
    if total_pages <= 1:
        return ""

    links: list[str] = []
    for page in range(1, total_pages + 1):
        href = "index.html" if page == 1 else f"page-{page}.html"
        if page == current_page:
            links.append(f'      <span class="pagination-current">{page}</span>')
        else:
            links.append(f'      <a href="{href}">{page}</a>')

    return f"""
      <nav class="pagination" aria-label="Blog pages">
{chr(10).join(links)}
      </nav>"""


def render_index_page(
    blogs: list[dict], current_page: int, total_pages: int, site: dict
) -> str:
    blog_boxes = "\n\n".join(render_blog_box(b) for b in blogs)
    pagination = render_pagination(current_page, total_pages)
    page_title = site["title"] if current_page == 1 else f"{site['title']} — Page {current_page}"

    return render_template(
        "index.html",
        {
            "PAGE_TITLE": page_title,
            "HEADING": site["heading"],
            "TAGLINE": site["tagline"],
            "BLOG_LIST": blog_boxes,
            "PAGINATION": pagination,
        },
    )


def load_blogs() -> list[dict]:
    with BLOGS_JSON.open(encoding="utf-8") as f:
        blogs = json.load(f)

    for blog in blogs:
        for key in ("title", "date", "url", "excerpt", "image", "imageAlt"):
            if key not in blog:
                raise ValueError(f"Blog entry missing '{key}': {blog}")

    blogs.sort(key=lambda b: b["date"], reverse=True)
    return blogs


def main() -> None:
    shrink_images()
    site = load_site()
    blogs = load_blogs()
    total_pages = max(1, (len(blogs) + BLOGS_PER_PAGE - 1) // BLOGS_PER_PAGE)

    for old_page in ROOT.glob("page-*.html"):
        old_page.unlink()

    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * BLOGS_PER_PAGE
        end = start + BLOGS_PER_PAGE
        page_blogs = blogs[start:end]
        html = render_index_page(page_blogs, page_num, total_pages, site)

        out_path = ROOT / ("index.html" if page_num == 1 else f"page-{page_num}.html")
        out_path.write_text(html, encoding="utf-8", newline="\n")
        print(f"Wrote {out_path.relative_to(ROOT)} ({len(page_blogs)} posts)")


if __name__ == "__main__":
    main()
