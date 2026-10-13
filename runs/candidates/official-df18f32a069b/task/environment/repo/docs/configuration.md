# Contract compiler configuration

The command reads TOML sections named `input`, `output`, `policy`, `aliases`, and
`exceptions`. Input and output directories are repository-relative when given as
relative paths. Policy keys are deliberately independent: an omitted key does
not mean that a parent or child explicitly selected the false value.

An alias maps an input field spelling to the canonical registry spelling. Alias
maps are applied to resolved fields, and canonical names win when both forms
are present. Exceptions identify compatibility classifications that the policy
allows. Configuration is data, not a command-line override mechanism.

A contract has a name, optional parent, fields, and policy. The parent graph is
resolved before records are emitted. Names are the stable identity of records;
file names are not identity. A malformed file is an input diagnostic and does
not invalidate other files.
