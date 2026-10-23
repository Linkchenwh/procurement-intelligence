let
    Source = Csv.Document(File.Contents(ProjectRoot & "\dashboard\powerbi\input\GovDate.csv"), [Delimiter=",", Columns=3, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Blanks = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Blanks, {{"date", type date}, {"month", type text}, {"year", Int64.Type}}, "en-US")
in
    Typed
