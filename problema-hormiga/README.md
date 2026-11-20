# Problema de la hormiga

La hormiga debe recoger toda la comida y alcanzar la meta en una cuadrícula con obstáculos. Cada movimiento ortogonal tiene costo unitario. La aplicación permite editar el mapa y recorrer la búsqueda con BFS, Dijkstra o A*.

## Ejecución

Desde esta carpeta, con Python 3.12 y `uv`, ejecuta los siguientes comandos.

```bash
uv sync --locked
uv run --locked ant-pathfinding
```

En **Generate** puedes elegir la cantidad de alimentos, la proporción de obstáculos y la semilla. En **Search**, selecciona el algoritmo y pulsa **Run** para calcular una ruta o **Step** para avanzar una expansión. Usa **Play** para recorrer el camino encontrado y observar la recolección de alimentos.

## Verificación

En Linux puedes ejecutar la comprobación de estilo, tipos y pruebas con Qt sin pantalla.

```bash
QT_QPA_PLATFORM=offscreen ./scripts/check.sh
```

La [documentación de arquitectura](docs/architecture/README.md) describe la separación entre el editor, el dominio y el motor de búsqueda.
