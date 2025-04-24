# Matrix algorithms in cerebras

<div style="text-align: justify">

This project were developed as part of my final project for the Cloud and High-Performance Computing Master's at Universitat Politècnica de València. It explores the use of the Cerebras Wafer-Scale Engine (WSE) for implementing and benchmarking classic linear algebra algorithms.

A full version of this project, originally written in Spanish, is available in the [`docs/`](./docs/) folder with the name `TFM_AbdelSandova.pdf`. It contains detailed explanations, development insights, and extended performance analysis. This README serves as a summarized version in English.

## Table of Contents:
- [Objectives](#objectives)
- [What is Cerebras](#what-is-cerebras)
- [Why use Cerebras for linear algebra](#why-use-cerebras-for-linear-algebra)
- [Implementation](#implementation)
- [Results](#results)
- [Challenges and Future Work](#challenges-and-future-work)
- [Conclusions](#conclusions)
- [References](#references)

## Objectives

The main objective is to develop, analyze, and validate basic computational kernels of linear algebra on the Wafer-Scale Engine architecture.

#### Specific Objectives

- Analyze matrix multiplication, LU factorization, and QR factorization algorithms to determine which are best suited for the Wafer-Scale Engine architecture.
- Design implementations of the selected algorithms, taking into account the communication and computation patterns of the WSE architecture.
- Implement the proposed algorithms and evaluate their performance using metrics such as execution time and FLOPs per clock cycle.

## What is Cerebras?

The Cerebras Wafer-Scale Engine (WSE) is a massively parallel architecture originally designed for deep learning and inference tasks. It contains approximately 850,000 processing cores (called PEs) arranged in a rectangular mesh, about two orders of magnitude more than modern GPUs. For comparison, the NVIDIA Blackwell GPU contains up to 24,576 CUDA cores.

One of the key features of the WSE architecture is its high-bandwidth, low-latency communication between PEs, capable of transmitting 32 bits per clock cycle. Each PE also has its own local memory physically close to the compute unit, allowing for fast memory access and reducing data movement overhead.

These features make the WSE a promising platform for exploring fine-grained parallelism and data-locality-sensitive algorithms, such as those used in linear algebra.

## Why use Cerebras for linear algebra?

Due to the fact that the WSE architecture was originally designed for AI,  its application beyond the AI context has not been extensively explored. However, it is interesting to investigate its performance on linear algebra algorithms,  especially those that do not fully exploit the properties present in today's more commonly used architectures, or that can uniquely benefit from the high-bandwidth and low-latency characteristics of the WSE.

Similar to the evolution seen with GPUs, which were originally designed for graphics processing and are now a staple in every HPC center, we believe that the WSE architecture also holds great potential beyond the AI domain.

Recent works already show promising advances in this area. For instance, the study "Efficient Algorithms for Monte Carlo Particle Transport on AI Accelerator Hardware"[[1]](#1) implemented a solution on WSE hardware, achieving up to 130 times better performance than the NVIDIA A100 GPU for Monte Carlo particle transport. Another example is "Wafer-Scale Fast Fourier Transforms"[[2]](#2), which reported a time of 959 microseconds for a complex problem of size 
512^3^, the largest parallelization achieved for this problem size, breaking the millisecond barrier for the first time.

The high degree of parallelism, high bandwidth, and low-latency communication between PEs make this architecture an attractive alternative for algorithms characterized by low data reuse or those that require intense, local data processing.

## Implementation

Before diving into the implementations, it is important to highlight some key points that influenced the design decisions:
- As an initial step to understand the architecture, versions of LU and QR factorizations were developed using only one element per PE. These implementations also served as a foundation for versions that manage multiple elements per PE.
- Due to the limited memory available in each PE, matrices must be subdivided into smaller submatrices.
- At this stage of development, the implementations assume square matrices (except for QR factorization) and square submatrices, as an initial simplification.
- The code is designed to use a reduced number of communication channels (referred to as "colors") since these are limited. This constraint was considered to allow future integration of these components into more complex versions or larger algorithmic workflows.

Section table of contents:
- [LU factorization](#lu-factorization)
  - [LU factorization in Cerebras](#lu-factorization-in-cerebras)
- [QR factorization](#qr-factorization)
  - [QR factorization in Cerebras](#qr-factorization-in-cerebras)
- [Cannon's algorithm](#cannons-algorithm)
  - [Cannon's algorithm in Cerebras](#cannons-algorithm-in-cerebras)

### LU factorization

The algorithm selected for LU factorization is the version without pivoting. This decision was made because this is an initial step toward implementing these algorithms on this architecture, and thus, a simplification that serves as a base for adding complexity in the future. The algorithm requires $2n^3/3$ FLOPs and is detailed below.

> function LU_factorization(A)
>> for <it = 0 To n$-$1> do
>>> for <row = it$+$1 To n$-$1> do⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀▷ Division Step
>>>> A[row, it] = A[row, it]$/$A[it, it];
>>>
>>> end for
>>> for <row = it$+$1 To n$-$1> do
>>>> for <col = it$+$1 To n$-$1> do⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀▷ Elimination Step
>>>>> A[row, col] = A[row, col]$-$A[it, col] $\cdot$ A[row, it]
>>>>
>>>> end for
>>>
>>> end for
>>
>> end for
>
> end function


For parallel environments exist a pipelined version of the LU factorization. If you have $p^2$ process and a matrix $A \in \mathbb{R}^{n \times n}$, with $n/p \in \mathbb{N}$, is possible divide the matrix $A$ in $p^2$ square submatrices of $n^2/p^2$ elements, assigning a different submatrix to each process. To perform LU factorization in this setup, each process must follow the behavior described below:
1. If a process holds data needed by other processes, it sends the corresponding values to them.
2. If a process has enough data to compute part of the factorization, it performs the necessary computation (division or elimination step).
3. Otherwise, the process waits to receive the data required to proceed.

#### LU factorization in Cerebras
To implement the pipelined version on Cerebras, it is necessary to define the communication patterns among the PEs in the mesh. For each iteration, the following values must be exchanged:
1. The diagonal element must be sent to all PEs below it in the same column to perform the division step.
2. The elements below the diagonal in the same column must be sent to their corresponding PEs to the right, in the same row, to enable the elimination step.
3. The elements to the right of the diagonal in the same row must be sent downward to the PEs in the same column to complete the elimination step.

Considering this, the design uses 4 colors, as illustrated in the example below for a $3\times3$ matrix with one element per PE.

<img src="/docs/images/lu/lu_single_design.png" width="250" style="display: block; margin: auto"/>
<br/>

The use of each color is:
- **Green**: Sends the diagonal element from a PE to all PEs below it in the same column (division step).
- **Blue**: Sends a signal from the diagonal PE to all PEs on its right.
- **Purple**: Sends the required element from PEs at the right of the diagonal to PEs below them, to perform the elimination step. This occurs after receiving the signal sent via the blue color.
- **Red**: Sends the required element from PEs below the diagonal to PEs at their right,  to perform the elimination step. This happens once the PE has completed the division step.

The communication flow can be visualized in the following diagram:
<img src="/docs/images/lu/lu_single_flow.png" style="display: block; margin: auto"/>

The previous examples help illustrate the flow of communications and data across the mesh. However, in real scenarios, each PE must manage more data due to larger problem sizes. The diagram below shows the layout for a $9\times9$ matrix distributed across a $3\times3$ PEs mesh.

<img src="/docs/images/lu/lu_many_design.png" width="250" style="display: block; margin: auto"/>
<br/>

Although the problem size per PE increases, no additional colors are required. The following diagram shows the progression of computation until the lower right PE performs its first elimination step. Initially, parallelism is low, but as communications propagate, more PEs become active in parallel. This grows to a peak and then gradually decreases as fewer matrix elements remain to be processed

<img src="/docs/images/lu/lu_many_flow.png" style="display: block; margin: auto"/>
<br/>

The current implementation uses more communication colors than strictly necessary. This was part of the early experimentation phase while I was still gaining familiarity with the architecture. Given time constraints, these optimizations were left for future refinement.

To reduce the number of colors:
- The purple and blue colors can be removed.
- To replace the purple color, all row data can be sent via the green color, and logic can be added in each PE to decide whether to use the data for a division or elimination step.
- To replace the blue color, each PE can manage the logic to determine after which step it should send data downward.

### QR factorization
The algorithm selected for QR factorization is the Givens rotations method. This implementation only computes the $R$ matrix, for the same reason LU factorization was implemented without pivoting: it is an initial step that provides a foundation for future improvements. The algorithm for applying a Givens rotation between two elements, such that one becomes zero, is shown below, where s and c correspond to $\sin{\theta}$ and $\cos{\theta}$ respectively, with $\theta$ being the angle of rotation.

> function givens(a, b)
>> if b==0 then
>>> c = 1; s = 0;
>>
>> else
>>> if |b|$>$|a| then
>>>> $\tau$ = $-$a$/$b; s = 1/$\sqrt{1+\tau^2}$; c = s$\cdot \tau$;
>>>
>>> else
>>>> $\tau$ = $-$b$/$a; c = 1/$\sqrt{1+\tau^2}$; s = c$\cdot \tau$;
>>>
>>> end if
>>
>> end if
>
> end function

The computation of the $R$ matrix using Givens rotations is detailed in the following algorithm, which requires approximately $3n^2(m - n/3)$ FLOPs for a matrix $A \in \mathbb{R}^{m \times n}$. The algorithm starts zeroing elements from the bottom row up, moving left to right across columns:

> function QR_givens(A)
>> for <j = 1 To n$-$1> do
>>> for <i = m$-$1 To j> do
>>>> [c, s] = givens(A[i$-$1, j], A[i, j]);
>>>> (A[i$-$1], A[i]) = (A[i$-$1]$\cdot$c$-$A[i]$\cdot$s, A[i$-$1]$\cdot$s $+$ A[i]$\cdot$c)  
>>>
>>> end for
>>
>> end for
>
> end function

#### QR factorization in Cerebras

To take advantage of the WSE architecture for QR factorization, the main objective is to maximize the number of zeros inserted in parallel across the matrix. In a parallel environment, the algorithm requires:

- Sending and receiving matrix values to compute $\sin{\theta}$ and $\cos{\theta}$.
- Sending and receiving the matrix values required to apply the rotation.
- Sending and receiving the $\sin{\theta}$ and $\cos{\theta}$ values themselves.

To support this, the design uses three communication colors, illustrated below with an example using a $4 \times 3$ matrix where each PE stores one element:

<img src="/docs/images/qr/qr_single_design.png" width="250" style="display: block; margin: auto"/>

The role of each color is as follows:

- **Green**: Sends matrix values.
- **Blue**: Sends $\sin{\theta}$ and $\cos{\theta}$ values.
- **Purple**: Sends a signal indicating that the current column can start inserting zeros. This was added to resolve race conditions.

The communication flow up to the moment when the second column inserts its first zero can be visualized in the following diagram:

<img src="/docs/images/qr/qr_single_flow.png" style="display: block; margin: auto"/>
<br/>

The previous examples help illustrate the flow of communications and data across the mesh. However, in real scenarios, each PE must manage more data due to larger problem sizes. The diagram below shows the layout for a $9 \times 9$ matrix distributed across a $3 \times 3$ PEs mesh.

<img src="/docs/images/qr/qr_many_design.png" width="250" style="display: block; margin: auto"/>
<br/>

To better exploit the architecture and the properties of Givens-based QR factorization, the implementation strategy in this version differs slightly. Each PE begins inserting zeros in its submatrix as soon as it has the data required. Only when it can no longer proceed independently does it start communicating with other PEs to continue the process.

This approach leads to better parallelism and eliminates the race conditions that previously required the use of the purple color. The diagram below shows the progression of the computation until the bottom-left PE has inserted five zeros in its submatrix. Once it has inserted all zeros, the PE to its right begins its own zeroing process and the cycle continues:

<img src="/docs/images/qr/qr_many_flow.png" style="display: block; margin: auto"/>
<br/>

### Cannon's algorithm
Cannon's algorithm is a method for parallel matrix multiplication that divides the input matrices $A$ and $B$ into $p^2$ square blocks. Processes are labeled from $P_{0,0}$ to $P_{p-1, p-1}$, with the initial assignment of submatrices $A_{i,j}$ and $B_{i,j}$ to process $P_{i,j}$.

To perform the multiplication, each process in the $i$-th row requires all $p$ submatrices $A_{i,k}$ with $0 \leq k < p$, and each process in the $j$-th column requires all $p$ submatrices $B_{k,j}$ with $0 \leq k < p$. The algorithm organizes communication and computation so that at any given moment, each process operates on a different pair of submatrices and contributes to computing its assigned submatrix $C_{i,j}$. The steps are as follows:

1. The submatrices of $A$ in the $i$-th row are shifted left by $i$ positions. Overflows wrap around using ring behavior.
2. The submatrices of $B$ in the $j$-th column are shifted up by $j$ positions, also using ring behavior.
3. Each $C$ submatrix is initialized to zero (or to a given initial value).
4. Each process multiplies its local submatrices and adds the result to $C_{i,j}$. Then, $A$ submatrices are shifted left by one position, and $B$ submatrices are shifted up by one position. This step is repeated $p - 1$ times.
5. A final multiplication and addition is performed using the current submatrices to complete the computation of $C_{i,j}$.

The image below illustrates the movement of the submatrices throughout the algorithm with 16 processes:

<img src="/docs/images/cannon/cannon_flow.png" style="display: block; margin: auto"/>
<br/>

#### Cannon's algorithm in Cerebras

Cannon's algorithm can be conceptually divided into two phases: the initial alignment and the computation phase. To simplify the implementation, and considering that data must be reorganized on the host before being transferred to the WSE, the initial alignment is performed on the host.

As a result, the implementation on Cerebras focuses on the following communication needs during the computation phase:

- Sending and receiving $A$ submatrices horizontally.
- Sending and receiving $B$ submatrices vertically.

Because each PE communicates primarily with its immediate neighbors, except in overflow cases where data must loop across the mesh, the design uses six communication colors: three for horizontal transfers of $A$, and three for vertical transfers of $B$. The role of each color is as follows:

- **Red**: Sends $A$ submatrices from the first column to the last.
- **Blue**: Sends $A$ submatrices to the left from the PEs in odd columns.
- **Cyan**: Sends $A$ submatrices to the left from the PEs in even columns.
- **Purple**: Sends $B$ submatrices from the first column to the last.
- **Green**: Sends $B$ submatrices upward from the PEs in odd rows.
- **Brown**: Sends $B$ submatrices upward from the Pes in even rows.

In addition, due to the behavior of reading and writing data in the same memory space, temporary submatrices are required to store received data. To maximize memory usage for problem data, only one temporary matrix is used per PE. The diagram below illustrates this configuration for a $4 \times 4$ PE mesh:

<img src="/docs/images/cannon/cannon_wse_design.png" width="300" style="display: block; margin: auto"/>
<br/>

The dataflow between two updates of matrix $C$ in this configuration is illustrated in the image below:

<img src="/docs/images/cannon/cannon_wse_flow.png" style="display: block; margin: auto"/>

## Results

### Experiments configuration

The experiments aim to analize the performance of the architecture while the size the problem increase and the impact of how much information is managed by each PE. To accomplish this, two kind of experiments was done, the first maintain the amount of elements in each PE constant over all experiments and while the problem size growth, the mesh also growth. The second fix the mesh dimensions and while the problem size growth, the ammount of elements in each PE is increased.

Every experiment use square matrices of $n \times n$, where $n$ is the problem size. In the same way, all mesh will be sqares of $p \times p$ PEs, where $p$ will be the mesh size. Finally, the submatrices size for each PE will be denotated by $n\_pe \times n\_pe$.

The table below shows the different experiments configurations done for this work. Note that Cannon's algorithm have one experiment less due to it needs hold four submatrices instead of one, reason why it start with $p = 4$ instead of 2.
<img src="/docs/images/results/experiments_table.jpg" width="800" style="display: block; margin: auto"/>

The information got for each experiment is the ammount of cycles informed by the simulator of the architecture, which include the data transmission from the borders of the architecture to their respectives PEs, the algorithm execution and the transmission of the data to the borders for the output.

Is important mention that due to the simulator limitations, perform bigger experiments requires a lot of time, for instance, the bigger experiment of this project took more than eight days of simulation, while the time that it should take in a real architecture would be less than a second, so increase the problems size to next relevant size without access to a real Cerebras System would take a lot of time.

### Experimental Results

#### Time analysis
To convert the number of clock cycles into time, we use the equation provided in the SDK documentation:

```math
\text{Tiempo }[\mu s] = (\text{cycles} / 0.85) \cdot 1.0\text{ }\mathrm{e}-3\text{ }[\mu s]
```

The plot below shows the execution time for the QR factorization across different experiments. It is clear that the version with increasing elements per PE outperforms the version with constant elements per PE. However, the latter exhibits a nearly linear growth trend.

This behavior is explained by two main factors:

- QR factorization has low communication overhead, and many operations occur in parallel.

- The PE with the highest workload (bottom-right PE) performs $n\_pe^2 \cdot (p-1) + n\_pe^2 / 2$ rotations, which grows linearly with the problem size when the number of elements per PE is constant, and exponentially in the increasing-elements case.

<img src="/docs/images/results/qr_time.png" width="800" style="display: block; margin: auto"/>
<br/>

The plot below shows the execution time for the LU factorization. A similar trend is observed: increasing elements per PE yields better performance than the constant case. However, unlike in QR, the constant elements version exhibits less linear growth. This is due to LU factorization requiring greater communication coordination, especially because the most active PE (again, the bottom-right PE) must update its elements $n\_pe \cdot p$ times, a value that grows linearly in the constant elements case.

<img src="/docs/images/results/lu_time.png" width="800" style="display: block; margin: auto"/>
<br/>

The plot below details the execution time of Cannon's algorithm. Here, the time increases with problem size following an exponential trend. While all PEs perform the same number of operations ($n\_pe^3 \cdot p$), the volume of data transmitted and the synchronization required are significantly higher than in LU or QR factorizations.

<img src="/docs/images/results/cannon_time.png" width="800" style="display: block; margin: auto"/>
<br/>

In all three algorithms, the increasing-elements-per-PE configuration consistently outperforms the constant case. In many cases, the performance difference is substantial. This indicates that, although data must travel further and through more PEs, the higher degree of parallelism effectively compensates for the communication cost.

#### FLOPs analysis

It is also interesting to analyze performance in terms of FLOPs per clock cycle. Since the number of floating point operations for each algorithm is known, we can divide it by the number of cycles to estimate the average FLOPs per cycle on the WSE.

The plot below shows the FLOPs per clock cycle for QR factorization. The increasing elements per PE configuration achieves better performance, but shows a decreasing slope. In contrast, the constant elements case exhibits exponential growth, suggesting that the implementation effectively scales the parallelism of the architecture with problem size.

<img src="/docs/images/results/qr_flops_cycle.png" width="800" style="display: block; margin: auto"/>
<br/>

The next plot shows FLOPs per clock cycle for LU factorization. The curves reflect the same behavior seen in QR. Additionally, LU achieves the lowest FLOPs per cycle among the three algorithms. This is likely due to the longer build up time to reach peak parallelism, as the computation propagates through the mesh and the number of active PEs decreases more quickly than in QR.

<img src="/docs/images/results/lu_flops_cycle.png" width="800" style="display: block; margin: auto"/>
<br/>

The plot below shows FLOPs per clock cycle for Cannon’s algorithm. Once again, the increasing elements configuration outperforms the constant elements version. Notably, Cannon achieves the highest performance in this metric, even with smaller problem sizes, because all PEs remain active throughout the entire execution, maximizing resource utilization.

<img src="/docs/images/results/cannon_flops_cycle.png" width="800" style="display: block; margin: auto"/>
<br/>

The following table summarizes the peak GFLOPs/s performance achieved by each algorithm under their best configurations. Cannon’s algorithm reaches 621 GFLOPs/s using only about 5% of the hardware (i.e., 4,096 out of ~850,000 PEs), highlighting the potential of this architecture.

<img src="/docs/images/results/gflops_table.jpg" width="600" style="display: block; margin: auto"/>

## Challenges and Future Work

Throughout the development of this project, several challenges were encountered, many of which are inherent to the novelty of the Cerebras architecture and its programming model. These challenges offer valuable insights for future improvements and exploration.

### Key Challenges

While the Wafer Scale Engine offers impressive capabilities in terms of parallelism and communication efficiency, there are several limitations and challenges to consider when applying it to traditional high performance computing tasks:
- Programming Model Maturity: Unlike well established ecosystems such as CUDA or OpenMP, the programming tools and abstractions for WSE are still under development and may lack the flexibility or robustness required for general purpose HPC applications. However, the same was said about CUDA and now is widely used in the HPC world.
- Limited Access and Hardware Availability: As of now, access to actual WSE hardware is restricted to collaborations with Cerebras or specific partner institutions. This makes experimentation and benchmarking more difficult outside simulation environments.
- Community and Ecosystem: Since it is a relatively new platform, there is limited community support, fewer examples, and less documentation compared to established HPC systems.

Despite these challenges, the WSE remains a promising architecture for specific types of problems, particularly those that can be mapped to regular, highly parallel patterns with localized communication.

### Future Work

Given the results obtained and the current implementation status, several directions are proposed for future exploration:

- **Evaluate Asynchronous Communication**: All communication in this work was implemented synchronously. It would be valuable to explore asynchronous communication models, especially in algorithms like Cannon’s, which are heavily affected by communication overhead.
- **Implementation of Complete Factorizations**: The current versions focus only on computing the $R$ matrix in QR and omit pivoting in LU for simplicity. Future work could include full implementations to improve numerical stability and completeness.
- **Extend the capacities of actual implementations**: The current versions could be adapted to be used in larger algorithms workflows.
- **Develop Additional Algorithms**: Many important linear algebra algorithms remain unexplored in this context. The knowledge gained in this project provides a strong foundation for implementing these and evaluating their behavior on the WSE.

## Conclusions

This project successfully implemented core linear algebra operations, including matrix multiplication, LU factorization, and QR factorization, on the Wafer-Scale Engine (WSE) architecture. These implementations serve as foundational components for future extensions into more complex numerical applications.

While Cannon’s algorithm and pipelined LU factorization naturally aligned with the architectural properties of the WSE, this work also introduced a customized version of QR factorization. This version was specifically adapted to maximize parallelism within the mesh structure, improving performance beyond what would be achievable with a direct translation of the classical algorithm.

The experimental results provided valuable insights into the architecture’s behavior, especially regarding PE utilization, communication overhead, and synchronization. Notably, the findings suggest that distributing work across a greater number of less-loaded PEs tends to yield better performance than concentrating data in fewer, heavily loaded cores. Additionally, the cost of coordination and communication emerged as a critical factor, particularly in algorithms with high data exchange.

Overall, this project demonstrates the potential of the WSE architecture for high performance numerical computing beyond its original focus on AI workloads. It also highlights both the opportunities and challenges of working with emerging, massively parallel hardware and lays the groundwork for future exploration in this space.

## References

<a id=1>[1]</a> Tramm, John, Bryce Allen, Kazutomo Yoshii, Andrew Siegel y Leighton Wilson: Efficient Algorithms for Monte Carlo Particle Transport on AI Accelerator Hardware, 2023. https://arxiv.org/abs/2311.01739.
<a id=2>[2]</a> Orenes-Vera, Marcelo, Ilya Sharapov, Robert Schreiber, Mathias Jacquelin, Philippe Vandermersch y Sharan Chetlur: Wafer-Scale Fast Fourier Transforms. En Proceedings of the 37th ACM International Conference on Supercomputing, ICS ’23, p´agina 180–191, New York, NY, USA, 2023. Association for Computing Machinery, ISBN 9798400700569. https://doi.org/10.1145/3577193.3593708.
</div>