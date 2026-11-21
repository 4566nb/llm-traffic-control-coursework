# Round 2 design brief

Use the same grammar, data and frozen scores. Round 1 mean results in order (reward; T, W, C, M improvements in percent):

- R1A: 0.757; 0, +1.984, +1.616, 0.
- R1B: 0.092; 0, −2.253, +7.685, 0.
- R1C: 0.771; 0, +1.433, +3.411, 0.

Every rule passed all three seeds. R1B exhibits a conflict between the two traffic-quality proxies. For seed 1, at 207/208/209 s its requested ceilings were 9.52/8.52/8.00 m/s; direct net gaps were 153/169/186 m. At 208 s the direct leader was doing 26.43 m/s while the forward average was 5.36. On the same seed, R1C was already braking on the fixed-zone signal at 3520 m, and stayed close to 11–12 m/s around the approach. Design three variants to test a more moderate response, local-gap feedback, and a position-dependent taper toward the queue. Aim to protect follower variation while monitoring trip time. Return three full tables before running them.
