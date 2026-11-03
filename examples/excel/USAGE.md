# Excel tool recipe

Use an existing private scratch workspace. All files below live directly inside
that directory. An installed Windows Excel provides the backend.

| Tool | Required inputs | Result |
| --- | --- | --- |
| `create_workbook` | `output`, rectangular `values` | New `.xlsx`, `Data` sheet, file hash and Excel version |
| `read_cells` | `workbook`, `address` | Literal values; defaults to sheet `Data` |
| `write_cells_copy` | `workbook`, new `output`, `start_cell`, `values` | New `.xlsx`; original file unchanged |

`read_cells` and `write_cells_copy` optionally accept a
`sheet` name. Filenames end in `.xlsx`, contain ASCII letters, numbers,
spaces, `_`, `-` or `.`, and cannot name an existing output. Inputs accept literal
text, numbers, booleans and null, with a maximum of 10×10 cells per write.

1. Call `create_workbook` with
   `{"output":"sample.xlsx","values":[["material","density"],["copper",8.96]]}`.
2. Call `read_cells` with
   `{"workbook":"sample.xlsx","address":"A1:B2"}`.
   Expected values: `[["material","density"],["copper",8.96]]`.
3. Call `write_cells_copy` with
   `{"workbook":"sample.xlsx","output":"updated.xlsx","start_cell":"B2","values":[[9.1]]}`.
4. Call `read_cells` with
   `{"workbook":"updated.xlsx","address":"B2"}`.
   Expected values: `[[9.1]]`; `sample.xlsx` remains unchanged.

Successful results include `owned_process_closed: true`. Workbook results
include SHA-256 and file size. A missing worksheet is an error, not an empty
answer. Choose a new filename when an output exists. For a timeout or uncertain
cleanup, inspect the reported state before retrying a write; the tool does not
claim completion or overwrite files to recover. A formula/active-content error
means the workbook is outside this example's supported input class.
PDF export is outside this example's supported tools.
