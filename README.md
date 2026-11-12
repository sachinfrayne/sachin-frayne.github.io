# sachinfrayne.com

Site copy lives in `site.json` (name, intro, about paragraphs, topics, and links). HTML templates live in `templates/`, and styles live in `styles.css`.

## Adding a blog

1. Copy `templates/post.html` to `blogs/your-slug.html` and write the post. Optionally add a hero image at `images/your-slug.jpg` and reference it from the post.
2. Add an entry to `blogs.json` with `title`, `date` (YYYY-MM-DD), `url` (`blogs/your-slug.html`), and `excerpt`. Optional keys: `image` (`images/tiny/your-slug.jpg`) and `imageAlt`.
3. Regenerate the thumbnails and index (use whichever you have installed):

```bash
python scripts/build_index.py
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_index.ps1
```

The build script creates `images/tiny/` thumbnails (30% scale via ImageMagick, or Pillow if ImageMagick is missing) and writes `index.html` and `page-2.html`, etc. (10 posts per page, newest first). No JavaScript required on the site.

Requires [ImageMagick](https://imagemagick.org) for the PowerShell script. On Windows: `winget install ImageMagick.ImageMagick`
