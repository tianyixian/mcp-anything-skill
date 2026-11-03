param([string]$CleanupOwner)
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ProgressPreference = 'SilentlyContinue'

function Stop-OwnedExcel([string]$OwnerPath) {
    if (-not (Test-Path -LiteralPath $OwnerPath)) { return $false }
    $record = Get-Content -LiteralPath $OwnerPath -Raw | ConvertFrom-Json
    $process = Get-Process -Id ([int]$record.process_id) -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $true }
    if ($process.ProcessName -ne 'EXCEL' -or $process.StartTime.ToUniversalTime().Ticks.ToString() -ne $record.start_ticks) {
        throw 'Process identity changed; refusing cleanup'
    }
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit(5000) | Out-Null
    return (-not (Get-Process -Id ([int]$record.process_id) -ErrorAction SilentlyContinue))
}

if ($CleanupOwner) {
    try {
        if (-not (Stop-OwnedExcel $CleanupOwner)) { exit 2 }
        exit 0
    } catch { exit 2 }
}

function Release-Com($Value) {
    if ($null -ne $Value -and [Runtime.InteropServices.Marshal]::IsComObject($Value)) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Value)
    }
}

$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
$application = $null
$workbooks = $null
$workbook = $null
$worksheets = $null
$worksheet = $null
$owned = $false
$closed = $true
$reply = @{ ok = $false; error = 'excel_operation_failed' }
try {
    if ($request.operation -notin @('create', 'read', 'write_copy')) { throw 'Unsupported operation' }
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class ExcelWindowOwner { [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId); }'
    $previousIds = @(Get-Process EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $application = New-Object -ComObject Excel.Application
    $version = [string]$application.Version
    $windowHandle = $application.Hwnd
    for ($attempt = 0; $attempt -lt 30 -and -not $windowHandle; $attempt++) {
        Start-Sleep -Milliseconds 100
        $windowHandle = $application.Hwnd
    }
    if (-not $windowHandle) { throw 'Excel did not expose an ownership window' }
    [uint32]$ownedProcessId = 0
    [void][ExcelWindowOwner]::GetWindowThreadProcessId([IntPtr]$windowHandle, [ref]$ownedProcessId)
    if ($ownedProcessId -eq 0 -or $previousIds -contains [int]$ownedProcessId) {
        $reply.error = 'existing_process_refused'
        throw 'Refusing to control an existing Excel process'
    }
    $process = Get-Process -Id ([int]$ownedProcessId)
    $owned = $true
    @{ process_id = [int]$ownedProcessId; start_ticks = $process.StartTime.ToUniversalTime().Ticks.ToString() } |
        ConvertTo-Json -Compress | Set-Content -LiteralPath $request.owner_file -Encoding UTF8
    $application.Visible = $false
    $application.DisplayAlerts = $false
    $application.EnableEvents = $false
    $application.AutomationSecurity = 3
    $application.AskToUpdateLinks = $false
    $workbooks = $application.Workbooks
    if ($request.operation -eq 'create') {
        $workbook = $workbooks.Add(-4167)
    } else {
        # UpdateLinks=0, ReadOnly=true. Only the new staged output can be saved.
        $workbook = $workbooks.Open([string]$request.source, 0, $true)
    }
    $application.Calculation = -4135
    $worksheets = $workbook.Worksheets
    if ($request.operation -eq 'create') {
        $worksheet = $worksheets.Item(1)
        $worksheet.Name = 'Data'
    } else {
        $worksheet = $worksheets.Item([string]$request.sheet)
    }
    $result = @{ sheet = [string]$worksheet.Name; excel_version = $version }
    if ($request.operation -in @('create', 'write_copy')) {
        for ($rowIndex = 0; $rowIndex -lt $request.values.Count; $rowIndex++) {
            $rowValues = $request.values[$rowIndex]
            for ($columnIndex = 0; $columnIndex -lt $rowValues.Count; $columnIndex++) {
                $cell = $worksheet.Cells.Item([int]$request.row + $rowIndex, [int]$request.column + $columnIndex)
                try {
                    $value = $rowValues[$columnIndex]
                    if ($null -eq $value) { $cell.ClearContents() | Out-Null }
                    elseif ($value -is [string]) { $cell.NumberFormat = '@'; $cell.Value2 = [string]$value }
                    elseif ($value -is [bool]) { $cell.Value2 = [bool]$value }
                    else { $cell.Value2 = [double]$value }
                } finally { Release-Com $cell }
            }
        }
        $workbook.SaveAs([string]$request.output, 51)
    } elseif ($request.operation -eq 'read') {
        $range = $worksheet.Range([string]$request.address)
        try {
            $rows = $range.Rows
            $columns = $range.Columns
            try { $rowCount = [int]$rows.Count; $columnCount = [int]$columns.Count }
            finally { Release-Com $rows; Release-Com $columns }
            $matrix = [System.Collections.Generic.List[object]]::new()
            $clipped = 0
            for ($rowIndex = 1; $rowIndex -le $rowCount; $rowIndex++) {
                $line = [System.Collections.Generic.List[object]]::new()
                for ($columnIndex = 1; $columnIndex -le $columnCount; $columnIndex++) {
                    $cell = $range.Cells.Item($rowIndex, $columnIndex)
                    try {
                        $value = $cell.Value2
                        if ($value -is [string] -and $value.Length -gt 256) {
                            $length = 256
                            if ([char]::IsHighSurrogate($value[$length - 1])) { $length-- }
                            $value = $value.Substring(0, $length)
                            $clipped++
                        }
                        $line.Add($value)
                    } finally { Release-Com $cell }
                }
                $matrix.Add($line.ToArray())
            }
            $result.values = $matrix.ToArray()
            $result.address = [string]$request.address
            $result.truncated_cells = $clipped
        } finally { Release-Com $range }
    }
    $reply = @{ ok = $true; result = $result }
} catch {
    if ($reply.error -ne 'existing_process_refused') { $reply.error = 'excel_operation_failed_' + $_.Exception.HResult.ToString('X8') }
    $reply.worker_line = $_.InvocationInfo.ScriptLineNumber
} finally {
    if ($null -ne $workbook) { try { $workbook.Close($false) } catch { $closed = $false } }
    if ($owned -and $null -ne $application) { try { $application.Quit() } catch { $closed = $false } }
    Release-Com $worksheet
    Release-Com $worksheets
    Release-Com $workbook
    Release-Com $workbooks
    Release-Com $application
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    if ($owned) {
        try { $closed = Stop-OwnedExcel $request.owner_file } catch { $closed = $false }
    }
}
$reply.owned_process_closed = $closed
$reply | ConvertTo-Json -Compress -Depth 12 | Write-Output
if (-not $reply.ok -or -not $closed) { exit 1 }
