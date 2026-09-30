#!/usr/bin/env python3
"""Independent continuum-reference calculation supplied by a read-only reviewer.
No FV solver imports, empirical correlations, experimental data, or fits.
Analytical Poiseuille velocity; numerically converged sine-Galerkin thermal
modes and quadrature; exact axial exponential propagation of those modes.
The finite basis does not exactly capture the t=0 wall/inlet discontinuity.
"""
import json
import numpy as np
from scipy.linalg import eigh

a, q = 2.0, 160
g, gw = np.polynomial.legendre.leggauss(q)
x, y = (g + 1) * a / 2, (g + 1) / 2
quadrature = np.outer(gw / 2, gw * a / 2)
n = np.arange(1, 4000, 2, dtype=float)
z = n[:, None] * np.pi * abs(x - a / 2)
c = n[:, None] * np.pi * a / 2
ratio = np.exp(z - c) * (1 + np.exp(-2 * z)) / (1 + np.exp(-2 * c))
w = y[:, None] * (1 - y[:, None]) / 2 - 4 / np.pi**3 * (np.sin(np.pi * y[:, None] * n) / n**3) @ ratio
mean_w = np.sum(w * quadrature) / a
vmass = (w / mean_w * quadrature).ravel()
taus = np.array([.001, .002, .004, .008, .016, .032, .064, .128, .256, .512])
for count in [16, 24, 32, 40]:
    modes = np.arange(1, 2 * count, 2)
    sx = np.sin(np.pi * np.outer(x / a, modes))
    sy = np.sin(np.pi * np.outer(y, modes))
    F = (2 / np.sqrt(a) * np.einsum('yn,xm->yxnm', sy, sx)).reshape(q*q, count*count)
    M = F.T @ (vmass[:, None] * F)
    K = np.diag((np.pi**2 * (modes[:, None]**2 + (modes[None, :] / a)**2)).ravel())
    eigenvalues, eigenvectors = eigh(K, M)
    weights = (eigenvectors.T @ (F.T @ vmass))**2 / a
    bulk = weights @ np.exp(-eigenvalues[:, None] * taus[None, :])
    print(json.dumps({'odd_modes_per_direction': count, 'quadrature_mean_w': mean_w, 'captured_inlet_norm': float(sum(weights)), 'fundamental_eigenvalue': float(eigenvalues[0]), 'Nu_fully_developed': float(eigenvalues[0] * (4/3)**2 / 4), 'bulk': dict(zip(map(str, taus), bulk.tolist()))}),flush=True)
