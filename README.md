# sachinfrayne.com

A static site served by GitHub Pages. The custom domain `sachinfrayne.com` is forwarded from GoDaddy to this repo, so pushing to `main` publishes the site. No server runs anywhere.

Site copy lives in `site.json` (name, intro, about paragraphs, topics, and links). HTML templates live in `templates/`, and styles live in `styles.css`.

## Adding a blog

1. Copy `templates/post.html` to `blogs/your-slug.html` and write the post. Update the `<title>`, the `description`, and the `og:` tags to match the post, and point `og:image` at the post's full-size image.
2. Optionally add a hero image at `images/your-slug.jpg` and reference it from the post.
3. Add an entry to `blogs.json` with `title`, `date` (YYYY-MM-DD), `url` (`blogs/your-slug.html`), and `excerpt`. Optional keys: `image` (`images/tiny/your-slug.jpg`) and `imageAlt`.
4. Regenerate the index and thumbnails:

```bash
python scripts/build_index.py
```

The build script creates `images/tiny/` thumbnails (30% scale, using Pillow) and writes `index.html` (10 posts per page, newest first). It needs Pillow, installed once with `pip install Pillow`. It runs on your machine, and the output files are committed, so the site stays static.

Commit the post, the image, `blogs.json`, and the regenerated `index.html`, then push to `main`.

## Tests

`scripts/check_blog_snippets.py` runs the Qdrant post's code blocks against a Qdrant server:

```bash
QDRANT_URL=http://localhost:6333 python scripts/check_blog_snippets.py
```

It needs a running Qdrant server (for example, `docker run -p 6333:6333 qdrant/qdrant`). It uses only the Python standard library.
