import argparse
import json
import numpy as np
import random

from cerebras.sdk.runtime.sdkruntimepybind import SdkRuntime, MemcpyDataType, MemcpyOrder # pylint: disable=no-name-in-module

def get_sin_cos(a, b):
  if b == 0:
    return (0,1)
  else:
    if abs(b) > abs(a):
      tau = -a/b
      s = 1/(1+tau*tau)**0.5
      c = s*tau
      return (s,c)
    else:
      tau=-b/a
      c = 1/(1+tau*tau)**0.5
      s = c*tau
      return (s,c)

# Read arguments
parser = argparse.ArgumentParser()
parser.add_argument('--name', help="the test compile output dir")
parser.add_argument('--cmaddr', help="IP:port for CS system")
args = parser.parse_args()

# Get matrix dimensions from compile metadata
with open(f"{args.name}/out.json", encoding='utf-8') as json_file:
  compile_data = json.load(json_file)

# Matrix dimensions
N = int(compile_data['params']['N'])
M = int(compile_data['params']['M'])

#construct A
A = np.array([random.random() for i in range(N*M)],  dtype=np.float32).reshape(M,N)

# Construct a runner using SdkRuntime
runner = SdkRuntime(args.name, cmaddr=args.cmaddr)

# Get symbols
R_symbol = runner.get_id('R')
runner.load()
runner.run()

runner.memcpy_h2d(R_symbol, A.ravel(), 0, 0, N, M, 1, streaming=False, data_type=MemcpyDataType.MEMCPY_32BIT, order=MemcpyOrder.ROW_MAJOR, nonblock=False)
runner.launch('start', nonblock=False)

print('computing host expected...')
for j in range(N):
  for i in range(M-1, j, -1):
    sin,cos = get_sin_cos(A[i-1][j], A[i][j])
    A[i], A[i-1] = (sin*A[i-1] + cos*A[i], cos*A[i-1] - sin*A[i])

print('end host computing.')
result = np.zeros(shape=N*M, dtype=np.float32)
runner.memcpy_d2h(result, R_symbol, 0, 0, N, M, 1, streaming=False, data_type=MemcpyDataType.MEMCPY_32BIT, order=MemcpyOrder.ROW_MAJOR, nonblock=False)
runner.stop()

result = result.reshape(M,N)
print(f'Error: {np.linalg.norm(A-result)}')
