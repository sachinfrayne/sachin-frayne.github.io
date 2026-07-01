# sachinfrayne.com

Site copy lives in `site.json`. HTML templates live in `templates/`.

## Adding a blog

1. Add a full-size hero image to `images/your-slug.jpg`.
2. Create `blogs/your-slug.html` (copy structure from an existing post).
3. Add an entry to `blogs.json` with `title`, `date` (YYYY-MM-DD), `url`, `excerpt`, `image` (`images/tiny/your-slug.jpg`), and `imageAlt`.
4. Regenerate thumbnails and the index (use whichever you have installed):

```bash
python scripts/build_index.py
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_index.ps1
```

The build script creates `images/tiny/` thumbnails (30% scale via ImageMagick) and writes `index.html` and `page-2.html`, etc. (10 posts per page, newest first). No JavaScript required on the site.

Requires [ImageMagick](https://imagemagick.org). On Windows: `winget install ImageMagick.ImageMagick`
