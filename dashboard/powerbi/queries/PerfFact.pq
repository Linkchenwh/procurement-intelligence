let
    Source = Csv.Document(File.Contents(ProjectRoot & "\dashboard\powerbi\input\PerfFact.csv"), [Delimiter=",", Columns=19, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Blanks = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Blanks, {{"PO_ID", type text}, {"Supplier", type text}, {"Order_Date", type date}, {"Delivery_Date", type date}, {"Item_Category", type text}, {"Order_Status", type text}, {"Quantity", Int64.Type}, {"Unit_Price", Currency.Type}, {"Negotiated_Price", Currency.Type}, {"Defective_Units", Int64.Type}, {"Compliance", type text}, {"delivery_days", type number}, {"observed_defective_units", Int64.Type}, {"compliant", Int64.Type}, {"amount", Currency.Type}, {"baseline_amount", Currency.Type}, {"valid_order", type logical}, {"delivered_order", type logical}, {"source_domain", type text}}, "en-US")
in
    Typed
