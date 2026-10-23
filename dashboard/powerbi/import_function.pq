// Create a text parameter ProjectRoot containing your checkout folder.
// Add one blank query called LoadCsv with this function. Invoke for each input table.
(TableName as text) as table =>
let
    Source = Csv.Document(File.Contents(ProjectRoot & "\dashboard\powerbi\input\" & TableName & ".csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
in
    Headers
