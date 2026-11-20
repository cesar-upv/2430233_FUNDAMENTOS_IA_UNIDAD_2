# Fundamentos de Inteligencia Artificial · Unidad 2

**Universidad Politécnica de Victoria**

- **Profesor** Said Polanco Martagón
- **Estudiante** César Euresti
- **Matrícula** 2430233

## Índice de prácticas

| N.º | Práctica | Contenido | Comando de inicio |
| --- | --- | --- | --- |
| 1 | [Árboles de expresión](arboles-expresion/README.md) | Construcción de árboles, evaluación de curvas y programación genética. | `uv run --locked expression-tree` |
| 2 | [Laboratorio de algoritmos evolutivos](lab-algoritmos-evolutivos/README.md) | Optimización de funciones con representaciones binarias y reales. | `uv run --locked evolutionary-lab` |
| 3 | [Problema de las N reinas](n-reinas/README.md) | Búsqueda de una disposición sin ataques mediante un algoritmo genético. | `uv run --locked n-queens-genalg` |
| 4 | [Problema de la hormiga](problema-hormiga/README.md) | Búsqueda de una ruta que recolecte todos los alimentos y alcance la meta. | `uv run --locked ant-pathfinding` |
| 5 | [Visualizador de grafos](visualizador-de-grafos/README.md) | Exploración de Dijkstra, A*, Bellman-Ford y Floyd-Warshall paso a paso. | `uv run --locked graph-visualizer` |

Cada práctica usa Python 3.12 y `uv`. Ejecuta `uv sync --locked` en su carpeta antes de usar el comando de inicio.

## Capturas de las prácticas

### Árboles de expresión

![Árbol de una expresión con coseno y curva evaluada en 1001 puntos](capturas/arboles-expresion.png)

### Laboratorio de algoritmos evolutivos

![Evolución de la función de Rastrigin y diversidad de la población hasta la generación 100](capturas/lab-algoritmos-evolutivos.png)

### Problema de las N reinas

![Tablero de ocho reinas con cero conflictos en la segunda generación](capturas/n-reinas.png)

### Problema de la hormiga

![Ruta de costo 17 calculada con A* con los tres alimentos recogidos](capturas/problema-hormiga.png)

### Visualizador de grafos

![Ruta de costo 16 del nodo 1 al nodo 12 calculada con Dijkstra](capturas/visualizador-de-grafos.png)
