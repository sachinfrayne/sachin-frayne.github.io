# Generate blog index pages from blogs.json (no client-side JavaScript).

$ErrorActionPreference = "Stop"
$BlogsPerPage = 10
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BlogsJson = Join-Path $Root "blogs.json"
$SiteJson = Join-Path $Root "site.json"
$TemplatesDir = Join-Path $Root "templates"
$ImagesDir = Join-Path $Root "images"
$TinyDir = Join-Path $ImagesDir "tiny"
$ThumbnailScale = "30%"

function Get-MagickCommand {
    $cmd = Get-Command magick -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $searchPaths = @(
        (Join-Path ${env:ProgramFiles} "ImageMagick*\magick.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "ImageMagick*\magick.exe")
    )

    foreach ($pattern in $searchPaths) {
        $found = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            return $found.FullName
        }
    }

    return $null
}

function Shrink-Images {
    if (-not (Test-Path $ImagesDir)) {
        Write-Warning "Images directory not found; skipping thumbnail generation."
        return
    }

    if (-not (Test-Path $TinyDir)) {
        New-Item -ItemType Directory -Path $TinyDir | Out-Null
    }

    $magick = Get-MagickCommand
    if (-not $magick) {
        throw "ImageMagick (magick) not found. Install from https://imagemagick.org or run: winget install ImageMagick.ImageMagick"
    }

    $images = Get-ChildItem -Path $ImagesDir -Filter "*.jpg" -File
    if ($images.Count -eq 0) {
        Write-Host "No source images found in images/."
        return
    }

    foreach ($image in $images) {
        $output = Join-Path $TinyDir $image.Name
        & $magick $image.FullName -resize $ThumbnailScale $output
        Write-Host "Shrunk $($image.Name) -> tiny/$($image.Name)"
    }
}

function Render-Template([string]$Name, [hashtable]$Vars) {
    $path = Join-Path $TemplatesDir $Name
    $content = Get-Content $path -Raw -Encoding UTF8
    foreach ($key in $Vars.Keys) {
        $content = $content.Replace("{{$key}}", [string]$Vars[$key])
    }
    return $content
}

function FormatBlogDate([string]$IsoDate) {
    $dt = [datetime]::ParseExact($IsoDate, "yyyy-MM-dd", $null)
    return "$($dt.Day) $($dt.ToString("MMMM")) $($dt.Year)"
}

function RenderBlogBox($Blog) {
    $displayDate = FormatBlogDate $Blog.date
    return Render-Template "blog-box.html" @{
        URL          = $Blog.url
        TITLE        = $Blog.title
        DATE         = $Blog.date
        DATE_DISPLAY = $displayDate
        EXCERPT      = $Blog.excerpt
        IMAGE        = $Blog.image
        IMAGE_ALT    = $Blog.imageAlt
    }
}

function RenderPagination([int]$CurrentPage, [int]$TotalPages) {
    if ($TotalPages -le 1) { return "" }

    $links = @()
    for ($page = 1; $page -le $TotalPages; $page++) {
        $href = if ($page -eq 1) { "index.html" } else { "page-$page.html" }
        if ($page -eq $CurrentPage) {
            $links += "      <span class=`"pagination-current`">$page</span>"
        } else {
            $links += "      <a href=`"$href`">$page</a>"
        }
    }

    return (@"

      <nav class="pagination" aria-label="Blog pages">
$($links -join "`n")
      </nav>
"@)
}

function RenderIndexPage($Blogs, [int]$CurrentPage, [int]$TotalPages, $Site) {
    $blogBoxes = ($Blogs | ForEach-Object { RenderBlogBox $_ }) -join "`n`n"
    $pagination = RenderPagination $CurrentPage $TotalPages
    $pageTitle = if ($CurrentPage -eq 1) { $Site.title } else { "$($Site.title) - Page $CurrentPage" }

    return Render-Template "index.html" @{
        PAGE_TITLE = $pageTitle
        HEADING    = $Site.heading
        TAGLINE    = $Site.tagline
        BLOG_LIST  = $blogBoxes
        PAGINATION = $pagination
    }
}

Shrink-Images

$site = Get-Content $SiteJson -Raw -Encoding UTF8 | ConvertFrom-Json
$blogs = Get-Content $BlogsJson -Raw -Encoding UTF8 | ConvertFrom-Json
$blogs = $blogs | Sort-Object { [datetime]::ParseExact($_.date, "yyyy-MM-dd", $null) } -Descending
$totalPages = [Math]::Max(1, [Math]::Ceiling($blogs.Count / $BlogsPerPage))

Get-ChildItem (Join-Path $Root "page-*.html") -ErrorAction SilentlyContinue | Remove-Item

for ($pageNum = 1; $pageNum -le $totalPages; $pageNum++) {
    $start = ($pageNum - 1) * $BlogsPerPage
    $pageBlogs = $blogs[$start..([Math]::Min($start + $BlogsPerPage - 1, $blogs.Count - 1))]
    $html = RenderIndexPage $pageBlogs $pageNum $totalPages $site
    $outPath = if ($pageNum -eq 1) { Join-Path $Root "index.html" } else { Join-Path $Root "page-$pageNum.html" }
    [System.IO.File]::WriteAllText($outPath, $html.Replace("`r`n", "`n"))
    Write-Host "Wrote $(Split-Path $outPath -Leaf) ($($pageBlogs.Count) posts)"
}
