"""N-BEATS (Oreshkin et al., 2020), versión genérica y global, con salida de cuantiles.

Experimental (D-021): se entrena en CPU con JAX y solo se despliega si gana a LightGBM y a
los modelos estadísticos en validación. JAX es opcional (``pip install .[dl]``).

Entrada: los últimos ``ventana`` log-precios del producto menos el log-precio del origen.
Salida: para cada horizonte, los cuantiles 10/50/90 del cambio logarítmico.
Bloques con conexión doblemente residual: cada bloque explica parte de la entrada
(backcast), se la resta, y suma su aporte al pronóstico.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .datos import Datos, productos_entrenamiento
from .familias import _Base, _filas


def _ventanas(L: np.ndarray, v: int, H: int, hasta: int | None):
    """Ventanas completas (sin huecos) de todos los productos; objetivos con índice ≤ hasta."""
    X, Y = [], []
    T = L.shape[0]
    for j in range(L.shape[1]):
        s = L[:, j]
        entrada = pd.Series(s).ffill(limit=2).to_numpy()       # huecos de hasta 2 meses: último dato conocido
        for t in range(v - 1, T - H):
            if hasta is not None and t + H > hasta:
                break
            x, y = entrada[t - v + 1:t + 1], s[t + 1:t + 1 + H]
            if np.isnan(x).any() or np.isnan(y).any():
                continue
            if np.isnan(s[t]):
                continue
            X.append(x - s[t])
            Y.append(y - s[t])
    return np.asarray(X, dtype=np.float32), np.asarray(Y, dtype=np.float32)


class NBeats(_Base):
    nombre = "nbeats"
    familia = "aprendizaje_profundo"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.params = None
        self.productos_por_ajuste: dict[str, int] = {}

    def _red(self):
        import jax
        import jax.numpy as jnp

        c, H, Q = self.cfg["nbeats"], max(self.h), len(self.tau)
        v, ancho, capas = c["ventana"], c["ancho"], c["capas"]

        def iniciar(clave):
            bloques = []
            for _ in range(c["bloques"]):
                capas_b, entrada = [], v
                for _ in range(capas):
                    clave, k = jax.random.split(clave)
                    capas_b.append((jax.random.normal(k, (entrada, ancho)) * jnp.sqrt(2 / entrada), jnp.zeros(ancho)))
                    entrada = ancho
                clave, k1, k2 = jax.random.split(clave, 3)
                bloques.append({"fc": capas_b,
                                "back": (jax.random.normal(k1, (ancho, v)) * 0.01, jnp.zeros(v)),
                                "fore": (jax.random.normal(k2, (ancho, H * Q)) * 0.01, jnp.zeros(H * Q))})
            return bloques

        def adelante(params, x):
            resto, pron = x, 0.0
            for b in params:
                z = resto
                for w, bb in b["fc"]:
                    z = jax.nn.relu(z @ w + bb)
                resto = resto - (z @ b["back"][0] + b["back"][1])
                pron = pron + (z @ b["fore"][0] + b["fore"][1])
            return pron.reshape(x.shape[0], H, Q)

        return iniciar, adelante

    def ajustar(self, datos: Datos, hasta: pd.Period):
        import jax
        import jax.numpy as jnp
        import optax

        c, H = self.cfg["nbeats"], max(self.h)
        productos = productos_entrenamiento(datos.logp, hasta, int(self.cfg["meses_minimos_entrenamiento"]),
                                            datos.entrenamiento)                 # solo datos hasta `hasta`
        self.productos_por_ajuste[str(hasta)] = len(productos)
        L = datos.logp[productos].to_numpy()
        idx_hasta = datos.logp.index.get_loc(hasta)
        X, Y = _ventanas(L, c["ventana"], H, idx_hasta)
        iniciar, adelante = self._red()
        tau = jnp.asarray(self.tau, dtype=jnp.float32)

        def perdida(params, x, y):
            q = adelante(params, x)                         # (n, H, Q)
            d = y[:, :, None] - q
            return jnp.mean(jnp.maximum(tau * d, (tau - 1) * d))

        opt = optax.adam(c["tasa_aprendizaje"])
        params = iniciar(jax.random.PRNGKey(int(self.cfg["semilla"])))
        estado = opt.init(params)

        @jax.jit
        def paso(params, estado, x, y):
            val, g = jax.value_and_grad(perdida)(params, x, y)
            act, estado = opt.update(g, estado, params)
            return optax.apply_updates(params, act), estado, val

        rng = np.random.default_rng(int(self.cfg["semilla"]))
        for _ in range(c["pasos"]):
            i = rng.integers(0, len(X), c["lote"])
            params, estado, _ = paso(params, estado, X[i], Y[i])
        self.params, self._adelante = params, jax.jit(adelante)

    def predecir(self, datos, origen, productos):
        v = self.cfg["nbeats"]["ventana"]
        L = datos.logp.loc[:origen, productos]
        if len(L) < v:
            return []
        ventana = L.iloc[-v:].ffill(limit=2)                    # mismo relleno causal que en el entrenamiento
        ok = [p for p in productos if ventana[p].notna().all() and pd.notna(L[p].iloc[-1])]
        if not ok:
            return []
        x = (ventana[ok] - ventana[ok].iloc[-1]).to_numpy().T.astype(np.float32)
        q = np.asarray(self._adelante(self.params, x))
        salida = []
        for k, pid in enumerate(ok):
            for h in self.h:
                salida.append(_filas(pid, h, L[pid].iloc[-1], q[k, h - 1]))
        return salida
