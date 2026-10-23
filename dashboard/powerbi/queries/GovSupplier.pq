let
    Source = Csv.Document(File.Contents(ProjectRoot & "\dashboard\powerbi\input\GovSupplier.csv"), [Delimiter=",", Columns=3, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Blanks = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Blanks, {{"supplier_key", type text}, {"supplier_label", type text}, {"name_variants", Int64.Type}}, "en-US")
in
    Typed
