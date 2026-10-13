import shutil
shutil.copyfile('/app/service_fixed.py','/tmp/unused_fixed.py')
exec(compile(open('/app/service_fixed.py').read().replace("elif v[3]>old[0]","elif False"),'/app/service_fixed.py','exec'))
