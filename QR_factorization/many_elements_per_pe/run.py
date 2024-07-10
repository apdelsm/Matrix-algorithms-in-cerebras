import argparse
import json
import numpy as np
import random

from cerebras.sdk.runtime.sdkruntimepybind import SdkRuntime, MemcpyDataType, MemcpyOrder # pylint: disable=no-name-in-module

def reorganize_grid(arr, width, height):
  m,n = arr.shape
  reshaped = arr.reshape((height, m//height, width, n//width))
  transposed = reshaped.transpose(0, 2, 1, 3)
  flattened_blocks = transposed.reshape(-1, n*m)
  result = flattened_blocks.flatten()
  return result

def inverse_reorganize_grid(flat_arr, width, height, n, m):
  num_blocks = width*height
  blocks = flat_arr.reshape(num_blocks, m//height, n//width)
  reshaped = blocks.reshape(height, width, m//height, n//width)
  transposed = reshaped.transpose(0, 2, 1, 3)
  result = transposed.reshape(m, n)
  return result

def get_sin_cos(a, b):
  if b == 0:
    return (0,1)
  else:
    if abs(b) > abs(a):
      tau = np.float32(-a)/np.float32(b)
      s = np.float32(1)/np.float32(1+tau*tau)**0.5
      c = np.float32(s)*np.float32(tau)
      return (s,c)
    else:
      tau= np.float32(-b)/np.float32(a)
      c = np.float32(1)/np.float32(1+tau*tau)**0.5
      s = np.float32(c)*np.float32(tau)
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
grid_width = int(compile_data['params']['grid_width'])
grid_height = int(compile_data['params']['grid_height'])

elements_per_pe = int(N/grid_width)*int(M/grid_height)

#construct A
A = np.array([random.random() for i in range(N*M)],  dtype=np.float32).reshape(M,N)

# Construct a runner using SdkRuntime
runner = SdkRuntime(args.name, cmaddr=args.cmaddr, suppress_simfab_trace=True)

# Get symbols
A_symbol = runner.get_id('A')
runner.load()
runner.run()

print("computing in device...")
runner.memcpy_h2d(A_symbol, reorganize_grid(A, grid_width, grid_height), 0, 0, grid_width, grid_height, elements_per_pe, streaming=False, data_type=MemcpyDataType.MEMCPY_32BIT, order=MemcpyOrder.ROW_MAJOR, nonblock=False)
runner.launch('start', nonblock=False)
print("computing expected...")
M_per_pe = M//grid_height
N_per_pe = N//grid_width
for grid_col in range(grid_width):
  for grid_row in range(grid_height-1, -1 + grid_col, -1):
    for pe_col in range(N_per_pe-1):
      for pe_row in range(M_per_pe-1, pe_col, -1):
        global_row = grid_row*M_per_pe + pe_row
        global_col = grid_col*N_per_pe + pe_col
        sin,cos = get_sin_cos(A[global_row - 1][global_col], A[global_row][global_col])
        A[global_row], A[global_row - 1] = (sin*A[global_row-1] + cos*A[global_row], cos*A[global_row-1] - sin*A[global_row])
  
  for pe_col in range(N_per_pe):
    for grid_row in range(grid_height-1, grid_col, -1):
      global_row = grid_row*M_per_pe
      global_col = grid_col*N_per_pe + pe_col
      if grid_row == grid_col + 1:
        sin,cos = get_sin_cos(A[global_row - M_per_pe + pe_col][global_col], A[global_row][global_col])
        A[global_row], A[global_row - M_per_pe + pe_col] = (sin*A[global_row-M_per_pe+pe_col] + cos*A[global_row], cos*A[global_row-M_per_pe+pe_col] - sin*A[global_row])
      else:
        sin,cos = get_sin_cos(A[global_row - M_per_pe][global_col], A[global_row][global_col])
        A[global_row], A[global_row - M_per_pe] = (sin*A[global_row-M_per_pe] + cos*A[global_row], cos*A[global_row-M_per_pe] - sin*A[global_row])
      for pe_row in range(0, N_per_pe - pe_col - 1):
        global_row = grid_row*M_per_pe + pe_row
        global_col = grid_col*N_per_pe + pe_col + 1 + pe_row
        sin,cos = get_sin_cos(A[global_row][global_col], A[global_row + 1][global_col])
        A[global_row + 1], A[global_row] = (sin*A[global_row] + cos*A[global_row+1], cos*A[global_row] - sin*A[global_row+1])

print("expected computed, waiting device...")
result = np.zeros(shape=N*M, dtype=np.float32)
runner.memcpy_d2h(result, A_symbol, 0, 0, grid_width, grid_height, elements_per_pe, streaming=False, data_type=MemcpyDataType.MEMCPY_32BIT, order=MemcpyOrder.ROW_MAJOR, nonblock=False)
runner.stop()
print("compute in device finished.")

result = inverse_reorganize_grid(result, grid_width, grid_height, N, M)
print(f'Error: {np.linalg.norm(A-result)}')
