let
    Source = Csv.Document(File.Contents(ProjectRoot & "\dashboard\powerbi\input\PerfCategory.csv"), [Delimiter=",", Columns=1, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Blanks = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Blanks, {{"Item_Category", type text}}, "en-US")
in
    Typed
