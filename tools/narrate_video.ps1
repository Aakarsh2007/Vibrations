$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoice('Microsoft Zira Desktop')
$speaker.Rate = 0
$scenes = Get-Content -LiteralPath (Join-Path $taskRoot 'video/scenes.json') -Raw | ConvertFrom-Json
for ($i = 0; $i -lt $scenes.Count; $i++) {
    $outputPath = Join-Path $taskRoot ('video/build/scene-{0}.wav' -f $i)
    $speaker.SetOutputToWaveFile($outputPath)
    $speaker.Speak($scenes[$i].narration)
}
$speaker.Dispose()
Write-Output 'Narration rendered with installed Microsoft Zira voice.'
