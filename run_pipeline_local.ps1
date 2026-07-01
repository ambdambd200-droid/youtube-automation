cd C:\Users\A\Desktop\Movies
Write-Host "========================================"
Write-Host "  VARY — Daily Pipeline (Local)"
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "========================================"
python run_pipeline.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "PIPELINE FAILED (exit: $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "PIPELINE COMPLETED SUCCESSFULLY" -ForegroundColor Green
