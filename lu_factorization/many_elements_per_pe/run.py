import argparse
import json
import numpy as np
import random

from cerebras.sdk.runtime.sdkruntimepybind import SdkRuntime, MemcpyDataType, MemcpyOrder # pylint: disable=no-name-in-module

def reorganize_grid(arr, k):
  n = arr.shape[0]
  reshaped = arr.reshape((k, n//k, k, n//k))
  transposed = reshaped.transpose(0, 2, 1, 3)
  flattened_blocks = transposed.reshape(-1, k*k)
  result = flattened_blocks.flatten()

  return result

def inverse_reorganize_grid(flat_arr, k, n):
  num_blocks = k*k
  blocks = flat_arr.reshape(num_blocks, n//k, n//k)  
  reshaped = blocks.reshape(k, k, n//k, n//k)
  transposed = reshaped.transpose(0, 2, 1, 3)  
  result = transposed.reshape(n, n)
  return result

# Read arguments
parser = argparse.ArgumentParser()
parser.add_argument('--name', help="the test compile output dir")
parser.add_argument('--cmaddr', help="IP:port for CS system")
args = parser.parse_args()

# Get matrix dimensions from compile metadata
with open(f"{args.name}/out.json", encoding='utf-8') as json_file:
  compile_data = json.load(json_file)

# Matrix dimensions
M = int(compile_data['params']['M'])
grid_size = int(compile_data['params']['grid_size'])
elements_per_pe = int((M/grid_size)**2)

# Construct A
A = np.array([random.random() for i in range(M*M)],  dtype=np.float32).reshape(M,M)
for i in range(M):
  A[i][i] = np.sum(A[i])

# Construct a runner using SdkRuntime
runner = SdkRuntime(args.name, cmaddr=args.cmaddr)

# Get symbols
A_symbol = runner.get_id('A')
runner.load()
runner.run()

print("computing in device...")
runner.memcpy_h2d(A_symbol, reorganize_grid(A, grid_size), 0, 0, grid_size, grid_size, elements_per_pe, streaming=False, data_type=MemcpyDataType.MEMCPY_32BIT, order=MemcpyOrder.ROW_MAJOR, nonblock=False)
runner.launch('start', nonblock=False)

lu = np.zeros(shape=M*M, dtype=np.float32)
runner.memcpy_d2h(lu, A_symbol, 0, 0, grid_size, grid_size, elements_per_pe, streaming=False, data_type=MemcpyDataType.MEMCPY_32BIT, order=MemcpyOrder.ROW_MAJOR, nonblock=False)
runner.stop()

print("computing expected...")
expected_lu = np.array(A, copy=True)
for col in range(M):
  for row in range(col+1, M):
    expected_lu[row][col] /= expected_lu[col][col]
  for col2 in range(col+1, M):
    for row in range(col+1, M):
      expected_lu[row][col2] -= expected_lu[row][col]*expected_lu[col][col2]

lu = inverse_reorganize_grid(lu, grid_size, M)
print(f'Error: {np.linalg.norm(expected_lu-lu)}')

