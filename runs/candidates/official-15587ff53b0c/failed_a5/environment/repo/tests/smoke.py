import subprocess
s='id,batch,account,group,src,dst,amount,num,den,split_id,part,total\na,b,c,g,USD,EUR,1,1,2,,,\n'
p=subprocess.run(['tools/reconcile-pack'],input=s,text=True,capture_output=True)
assert p.returncode==0 and p.stdout.splitlines()[-1].endswith(',0')
