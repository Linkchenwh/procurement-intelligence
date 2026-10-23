param(
    [string]$QueryFile,
    [string]$OutputFile,
    [string]$Catalog
)
$ErrorActionPreference='Stop'
$pbWorkspaceRoot=Join-Path $env:LOCALAPPDATA 'Microsoft\Power BI Desktop\AnalysisServicesWorkspaces'
$pbPortFile=Get-ChildItem -LiteralPath $pbWorkspaceRoot -Filter msmdsrv.port.txt -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(-not $pbPortFile){throw 'No running local Power BI Analysis Services workspace found'}
$pbPort=(Get-Content -LiteralPath $pbPortFile.FullName -Raw -Encoding Unicode).Trim([char]0).Trim()
if($pbPort -notmatch '^\d+$'){throw 'Invalid local Analysis Services port'}
[void][System.Reflection.Assembly]::LoadFrom('C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll')
$pbConnection=New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection
$pbConnection.ConnectionString="Data Source=localhost:$pbPort;Integrated Security=SSPI"
if($Catalog){$pbConnection.ConnectionString+=";Initial Catalog=$Catalog"}
$pbConnection.Open()
try {
    if($QueryFile -and -not $Catalog){
        $pbCatalogCommand=$pbConnection.CreateCommand()
        $pbCatalogCommand.CommandText='SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS'
        $pbCatalogReader=$pbCatalogCommand.ExecuteReader()
        $pbCatalogs=[System.Collections.Generic.List[string]]::new()
        while($pbCatalogReader.Read()){$pbCatalogs.Add([string]$pbCatalogReader.GetValue(0))}
        $pbCatalogReader.Close()
        if($pbCatalogs.Count -ne 1){throw 'Expected exactly one database in the selected local workspace'}
        $pbConnection.ChangeDatabase($pbCatalogs[0])
    }
    $pbCommand=$pbConnection.CreateCommand()
    $pbCommand.CommandTimeout=120
    if($QueryFile){
        $pbCommand.CommandText=Get-Content -LiteralPath $QueryFile -Raw -Encoding utf8
        if($pbCommand.CommandText.TrimStart() -notmatch '^(EVALUATE|SELECT)\b'){throw 'Only read-only EVALUATE/SELECT queries are supported'}
    } else {
        $pbCommand.CommandText='SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS'
    }
    $pbReader=$pbCommand.ExecuteReader()
    $pbRows=[System.Collections.Generic.List[object]]::new()
    while($pbReader.Read()){
        $pbRow=[ordered]@{}
        for($pbIndex=0;$pbIndex -lt $pbReader.FieldCount;$pbIndex++){
            $pbValue=$pbReader.GetValue($pbIndex)
            $pbRow[$pbReader.GetName($pbIndex)]=if($pbValue -is [DBNull]){$null}else{$pbValue}
        }
        $pbRows.Add([pscustomobject]$pbRow)
    }
    $pbReader.Close()
    $pbJson=ConvertTo-Json -InputObject @($pbRows.ToArray()) -Depth 8
    if($OutputFile){[System.IO.File]::WriteAllText($OutputFile,$pbJson,[System.Text.UTF8Encoding]::new($false))}
    $pbJson
} finally {
    $pbConnection.Close()
    $pbConnection.Dispose()
}
