$baseDir = "d:\nu\JARVIS"
$docsDir = Join-Path $baseDir "jarvis_docs"
if (!(Test-Path $docsDir)) {
    New-Item -ItemType Directory -Force -Path $docsDir | Out-Null
}

$dirs = @("plugins", "actions")
$allSkills = @()

foreach ($d in $dirs) {
    $path = Join-Path $baseDir $d
    if (Test-Path $path) {
        $files = Get-ChildItem -Path $path -Filter "*.py"
        foreach ($file in $files) {
            if ($file.Name -ne "__init__.py") {
                $skillName = $file.BaseName
                $content = Get-Content $file.FullName
                
                # Simple parsing for classes and functions
                $classes = $content | Select-String -Pattern "^\s*class\s+([A-Za-z0-9_]+)" | ForEach-Object { $_.Matches.Groups[1].Value }
                $functions = $content | Select-String -Pattern "^\s*def\s+([A-Za-z0-9_]+)" | ForEach-Object { $_.Matches.Groups[1].Value }
                
                $mdFilename = "${d}_${skillName}.md"
                $mdFilepath = Join-Path $docsDir $mdFilename
                
                $mdContent = "# ${skillName} (${d})`n`n"
                $mdContent += "## Sınıflar`n"
                foreach ($c in $classes) { $mdContent += "- $c`n" }
                $mdContent += "`n## Fonksiyonlar`n"
                foreach ($f in $functions) { $mdContent += "- $f`n" }
                
                Set-Content -Path $mdFilepath -Value $mdContent -Encoding UTF8
                
                $allSkills += [PSCustomObject]@{
                    Name = $skillName
                    Type = $d
                    File = $mdFilename
                }
            }
        }
    }
}

$indexFilepath = Join-Path $docsDir "index.md"
$indexContent = "# JARVIS Yetenekleri (Skills) - Genel Bakış`n`n"
$indexContent += "Bu dosya, JARVIS asistanının sahip olduğu tüm eylem ve eklentilerin listesini içerir.`n`n"

$indexContent += "## Actions`n"
foreach ($s in $allSkills | Where-Object Type -eq 'actions') {
    $indexContent += "- [$($s.Name)](./$($s.File))`n"
}

$indexContent += "`n## Plugins`n"
foreach ($s in $allSkills | Where-Object Type -eq 'plugins') {
    $indexContent += "- [$($s.Name)](./$($s.File))`n"
}

Set-Content -Path $indexFilepath -Value $indexContent -Encoding UTF8
