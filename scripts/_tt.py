import sys,time
from pathlib import Path
from evaluator.harbor_runner import run_job
m,name=sys.argv[1],sys.argv[2]
t=time.time()
for x in run_job(Path("runs/candidates/official-p0-ledger-reconcile/task"),"terminus-2",name,model=f"openrouter/{m}",attempts=1,agent_kwargs={"max_turns":100}):
    print(m,x.outcome,x.reward,x.n_episodes,round(x.priced_cost(),3),round(time.time()-t),"s",x.exception_message[:150])
