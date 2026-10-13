# Reconcile pack v2
Input CSV: id,batch,account,group,src,dst,amount,num,den,split_id,part,total
Output CSV: id,batch,account,group,dst,allocation
Supported currencies: USD, EUR, GBP. Rates and all allocation decisions are exact rationals.
