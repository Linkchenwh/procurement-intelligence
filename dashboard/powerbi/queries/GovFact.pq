let
    Source = Csv.Document(File.Contents(ProjectRoot & "\dashboard\powerbi\input\GovFact.csv"), [Delimiter=",", Columns=9, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Blanks = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Blanks, {{"row_id", Int64.Type}, {"order_key", type text}, {"order_id", Int64.Type}, {"supplier_key", type text}, {"purchase_date", type date}, {"department", type text}, {"fiscal_year", type text}, {"acquisition_type", type text}, {"amount", Currency.Type}}, "en-US")
in
    Typed
