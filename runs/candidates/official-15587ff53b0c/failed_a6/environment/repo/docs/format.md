# Reconcile pack v2

Input CSV: `id,batch,account,group,src,dst,amount,num,den,split_id,part,total`

Output CSV: `id,batch,account,group,dst,allocation`

Supported currencies are USD, EUR, and GBP. Amounts are signed source minor units. `num/den` is a positive exact rational FX rate; no floating-point arithmetic is used. The converted value is `amount*num/den`.

A blank `split_id` means an ordinary line and requires blank `part` and `total`. A split is a set of child rows sharing one nonblank split_id. Every child must have the same batch, account, group, source currency, destination currency, numerator, denominator, and total. Parts are the integers 1 through total exactly once. The child amounts are the complete exact representation of that logical parent: their exact sum is the parent amount, and their allocations collectively conserve the rounded exact sum of the parent. Children are expanded before grouping and retain input order in output.

Settlement groups use the complete identity `batch/account/group/dst`, including destination currency, and may be interleaved in the input. For each group, sum exact rational converted values and round to the nearest integer, with half-way cases going to the even integer. Give every line its mathematical floor. A positive residual is assigned one unit at a time to largest fractional remainders; a negative residual removes one unit at a time from smallest fractional remainders. Equal remainders use original input order. The resulting allocations conserve the rounded exact group sum.
