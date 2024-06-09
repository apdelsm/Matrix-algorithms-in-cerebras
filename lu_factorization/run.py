import argparse
import json
import numpy as np
import random
from scipy.sparse.linalg import splu

from cerebras.sdk.runtime.sdkruntimepybind import SdkRuntime, MemcpyDataType, MemcpyOrder # pylint: disable=no-name-in-module

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

# Construct A
A = np.array([random.random() for i in range(N*M)],  dtype=np.float32).reshape(M,N)
for i in range(N):
  A[i][i] = np.sum(A[i])

# Construct a runner using SdkRuntime
runner = SdkRuntime(args.name, cmaddr=args.cmaddr)

# Get symbols
element_symbol = runner.get_id('element')
runner.load()
runner.run()

runner.memcpy_h2d(element_symbol, A.ravel(), 0, 0, N, M, 1, streaming=False, data_type=MemcpyDataType.MEMCPY_32BIT, order=MemcpyOrder.ROW_MAJOR, nonblock=False)
runner.launch('start', nonblock=False)

lu = np.zeros(shape=N*M, dtype=np.float32)
runner.memcpy_d2h(lu, element_symbol, 0, 0, N, M, 1, streaming=False, data_type=MemcpyDataType.MEMCPY_32BIT, order=MemcpyOrder.ROW_MAJOR, nonblock=False)
runner.stop()

lu = lu.reshape(M,N)

slu = splu(A, permc_spec = "NATURAL", diag_pivot_thresh=0, options={"SymmetricMode":True})
slu = slu.L.todense() + slu.U.todense() - np.eye(N)

print(f'Error: {np.linalg.norm(slu-lu)}')

