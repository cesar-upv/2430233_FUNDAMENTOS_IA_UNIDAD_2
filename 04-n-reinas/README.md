# Problema de las N reinas

La aplicación usa un algoritmo genético para buscar posiciones en las que ninguna reina ataque a otra. Cada individuo representa, mediante una permutación, la fila de la reina en cada columna del tablero.

## Ejecución

Desde esta carpeta, con Python 3.12, `uv` y un entorno gráfico compatible con Dear PyGui, ejecuta los siguientes comandos.

```bash
uv sync --locked
uv run --locked n-queens-genalg
```

La interfaz abre un tablero de ocho reinas. Usa **Hallar Solución Ya** para buscar una distribución con cero conflictos, o **+1 Generación** para observar el avance paso a paso. En el historial puedes inspeccionar los individuos, sus conflictos, las operaciones genéticas y la curva de convergencia.

El panel de parámetros permite variar el tamaño del tablero, la población, los métodos de selección y cruza, y las probabilidades de cruza y mutación.
