def sparkline(values):
 return ''.join('▁▃▅▇'[min(3,int(abs(v)*4))] for v in values)
