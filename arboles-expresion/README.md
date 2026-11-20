# Expresiones

Explorador de árboles de expresión, curvas y programación genética en Python y PySide6.

```sh
uv run expression-tree
```

El botón **Evolución** abre dos secciones explícitas: **Algoritmo completo** para ejecutar una corrida y **Demostraciones** para estudiar cada operador. El árbol del explorador se conserva.

## Algoritmo completo

1. Define la referencia con una ecuación o un CSV con columnas `x,y`. Los CSV usan todos sus puntos exactos y requieren una `y` finita en cada fila.
2. Ajusta tamaño de población, nivel máximo, selección, tipos de mutación activos y límite de generaciones. La raíz está en el nivel **0**; nivel máximo 2 permite tres niveles. Cada genotipo admite hasta 63 nodos, incluidas sus ramas recesivas.
3. Abre **Opciones avanzadas** para cambiar el intervalo, cantidad de puntos, variable, métrica, reparaciones, tamaño del torneo, semilla, probabilidades, operadores permitidos, elitismo, Hall of Fame y tolerancia de paro.
4. Pulsa **Iniciar ejecución**. La app genera y evalúa G0 y repite selección → cruza → mutación → evaluación hasta el criterio de paro. No necesitas ejecutar las fases manualmente.
5. **Pausar** conserva la corrida y termina la generación en curso. Después puedes **Continuar ejecución**, **Avanzar una generación** completa o **Iniciar nueva ejecución**. Las acciones aparecen según el estado.

Las cuatro **Mutaciones activas** están marcadas por defecto: hojas, operadores, switching y subrama aleatoria. Puedes activar o descartar cada tipo con sus casillas. La probabilidad de mutación se aplica por hijo (5 % por defecto); si muta, se sortea **un solo tipo** entre los activos, con igual probabilidad. Una corrida corta puede no llegar a usar todos. Si el árbol no tiene nodos compatibles con el tipo elegido, se conserva y el registro explica el intento. Desmarcar todas permite ejecutar sin mutación y deshabilita su probabilidad sin borrar el valor. Los élites siguen copiándose sin cambios y el origen de cada hijo identifica la mutación aplicada.

La vista inicial **Comparación** muestra las curvas de referencia y élite. Las otras vistas son Población, Hall of Fame y Progreso. Las operaciones reales de la última generación se consultan desde Progreso en una ventana de detalle sin controles para modificarlas.
La tabla muestra genotipo, ecuación y adaptación de cada individuo. MSE y NMSE se minimizan; para maximizar R² se minimiza `1 − R²`. Una predicción fuera del dominio invalida al individuo completo, sin descartar puntos para mejorar artificialmente su adaptación. La evaluación protegida aplica las políticas de reparación del explorador, capturadas al abrir la ventana. NMSE y R² requieren al menos dos referencias con distinta `y`.

La semilla reproduce la ejecución con los mismos datos y ajustes. Las pruebas manuales tienen su propio generador aleatorio y no alteran la trayectoria evolutiva. Cambiar ajustes exige iniciar una nueva ejecución; los resultados anteriores quedan visibles hasta entonces. El archivo y la población se conservan en memoria mientras la app está abierta.

## Comparación de curvas por generación

**Comparación** se actualiza al terminar G0 y cada generación. Superpone la referencia en naranja con trazo discontinuo y la predicción en azul, usando exactamente los mismos puntos `x` y la misma política de evaluación de la corrida. El eje vertical incluye ambas series. Mueve el cursor para leer el valor de referencia y la predicción en un mismo punto.

- **En vivo · última generación** sigue al mejor individuo por defecto. Si configuraste varios élites, el selector **Individuo** permite consultar cada uno de los mejores N de esa generación.
- El selector **Generación** permite volver a G0 o cualquier generación terminada. La consulta histórica permanece fija mientras el algoritmo continúa; vuelve a **En vivo** para seguir la corrida.
- Se muestran la ecuación del individuo, MSE, NMSE y R². Los CSV conservan todos sus valores x exactos, incluidos los repetidos; solo se ordenan visualmente para trazar la gráfica.
- Si el elitismo está desactivado, se compara el mejor individuo y se indica explícitamente. Las predicciones fuera de dominio quedan como huecos y el individuo conserva su estado inválido.

El historial de comparación guarda copias de los mejores árboles de cada generación, aunque salgan de la población o del Hall of Fame. Solo se conserva la última predicción en el motor; las curvas históricas se reconstruyen al consultarlas, sin acumular todos los vectores de puntos. El historial se reinicia con una nueva ejecución y vive en memoria.

## Demostraciones y representación visual

En **Demostraciones** tienes pestañas independientes para selección, cruza y mutación. Funcionan desde el primer momento con ejemplos de clase, sin preparar una corrida. La selección usa seis ecuaciones comparadas con `x² + x + 1`, y permite cambiar su propio método y tamaño de torneo. Puedes importar una **Copia de la ejecución**; esa copia solo cambia al pulsar **Actualizar copia**.

Los ajustes de demostración, sus árboles y su generador aleatorio son independientes de la ejecución completa. Puedes cambiar de sección mientras corre el algoritmo. El nivel máximo de las demos se ajusta en su cabecera; los operadores disponibles y la variable se toman del generador al abrir la ventana. Las pruebas manuales siempre aplican el operador.

En cruza puedes elegir los cortes pulsando un nodo. En mutación eliges el árbol desde un selector: explorador, ejemplo switching o individuo de la población de prueba. **Continuar desde el resultado** permite encadenar cambios sobre una copia. Los ejemplos permiten reproducir la cruza `2 + 3*x` con `5 − x/2` y el switching de `sqrt(2*x)` a `sqrt(x/5)`.

- **Cruza monopunto:** intercambia subárboles cortando una arista en cada padre. Una raíz no tiene arista de entrada. Si algún padre es una sola hoja, se copian los padres. Azul y verde identifican las ramas intercambiadas.
- **Poda y reparación:** al exceder altura o presupuesto de nodos, reemplaza la rama por su operando más cercano. Se busca por niveles, con prioridad izquierda en empates. Naranja identifica las reparaciones; ninguna hoja queda como operador sin hijos.
- **Mutación de hojas:** sustituye una hoja por otra constante o variable. La prueba manual permite escribir un operando, por ejemplo `3.2`.
- **Mutación de operadores:** sustituye un operador válido. Si pasa a unario, siempre evalúa la izquierda y conserva la derecha como gen recesivo. Si pasa a binario, recupera la rama derecha o genera un operando cuando faltaba.
- **Switching:** intercambia ramas izquierda y derecha. También puede activar un gen recesivo de un operador unario.
- **Subrama aleatoria:** sustituye una rama, incluida la raíz, por un árbol generado dentro de la altura disponible.

Las ramas recesivas aparecen **punteadas**. Participan en cruza, mutación y límites estructurales; no participan en la ecuación, valores, variables activas ni pasos de evaluación. **Abrir** envía el genotipo completo al explorador, conservando esas ramas. Editar y reconstruir la ecuación genera un árbol a partir del fenotipo escrito.

## Elitismo, Hall of Fame y progreso

En **Opciones avanzadas**, **Élites** determina cuántos de los mejores individuos se copian sin modificación a la siguiente generación. `0` desactiva el elitismo; debe quedar al menos un lugar para reproducción.

**Hall of Fame** guarda los mejores genotipos distintos de todas las generaciones, junto con su generación de aparición y métricas. Son copias independientes y permanecen aunque salgan de la población. No se reinsertan automáticamente. Su capacidad es configurable y `0` lo desactiva.

**Progreso** compara la mejor pérdida y la media de los individuos válidos, muestra el conteo de cruza, mutación y poda, y permite inspeccionar operaciones reales de la última generación. La gráfica usa `log(1 + pérdida)` para incluir el cero y valores de distinta escala.

## Verificación

```sh
QT_QPA_PLATFORM=offscreen uv run python -m unittest discover -s tests -v
```

Las pruebas cubren parser, evaluación, datos, métricas, invariantes estructurales, genes recesivos, selección, reproducción, elitismo, archivo y flujos Qt en tamaño compacto.

## Git local

El `.gitignore` excluye entornos virtuales, bytecode, compilaciones, cachés, cobertura, archivos `.env`, configuración local de editores y capturas/revisiones generadas en `.impeccable/review/`. Se conservan el código, las pruebas, `uv.lock`, la documentación y el CSV de ejemplo. Los commits locales siguen Conventional Commits.
