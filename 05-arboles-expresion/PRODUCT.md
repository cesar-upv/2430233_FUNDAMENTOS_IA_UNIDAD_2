# Expresiones

Aplicación de escritorio en español, implementada en Python y PySide6, para estudiar árboles de expresión y regresión simbólica mediante programación genética. El usuario aprende con los temas de clase y necesita observar la relación entre genotipo, ecuación y adaptación.

## Autoridad visual y uso

Esta ampliación hereda la interfaz existente: Flexoki claro en `src/expression_tree/ui/theme.py`, controles nativos, tipografía sans para interfaz y monoespaciada para ecuaciones y valores, superficies de papel y geometría precisa. La captura previa `.impeccable/review/data-desktop.png` documenta esa identidad. No se aprobó un cambio de sistema visual.

Modo de la superficie de evolución: **Operate**, con explicaciones visuales educativas. Se admiten ventanas de escritorio de 1440×940 y compactas de 1024×768. Los árboles deben poder inspeccionarse, ampliarse, ajustarse y desplazarse. La información debe relacionar cada fila seleccionada con su árbol y métricas actuales.

## Flujo

El explorador conserva parser, notaciones, recorridos, evaluación, reparaciones numéricas, curvas y métricas. El botón Evolución abre un laboratorio no modal; los resultados pueden enviarse como árboles completos al explorador.

La ventana tiene dos entradas explícitas:

- **Algoritmo completo:** referencia por ecuación o CSV, configuración básica y opciones avanzadas. Una única acción inicial, **Iniciar ejecución**, prepara G0 y repite automáticamente todas las fases hasta el criterio de paro. Después permite pausar, continuar, avanzar una generación completa o iniciar una nueva corrida. Su vista inicial es Comparación, seguida de Población, Hall of Fame y Progreso.
- **Demostraciones:** selección, cruza y mutación individuales con ejemplos listos para usar. No exige crear una corrida. Tiene método de selección, tamaño de torneo, nivel máximo, árboles y generador aleatorio propios. Puede importar una copia explícita de la población de una generación terminada; actualizar la copia requiere una acción del usuario.

Los controles y errores de cada sección permanecen en su espacio. Cambiar una demo no altera los ajustes, la semilla, la población ni el progreso del algoritmo completo. La corrida puede continuar mientras el usuario explora las demos. Su estado en curso se indica en la navegación. Las operaciones reales se abren desde Progreso en un visor de consulta, separado de las demos editables.

La semilla reproduce una ejecución con los mismos ajustes y datos. Los ajustes poco frecuentes se revelan en Opciones avanzadas. Se muestran únicamente las acciones pertinentes al estado de la corrida; los controles de inspección de árboles aparecen cuando hay un árbol.

## Reglas solicitadas en clase

- Selección por torneo, ruleta y muestreo estocástico universal (SUS). Ruleta y SUS usan peso `1 / (1 + pérdida)`; SUS usa un inicio aleatorio y punteros equidistantes. Se permite repetir padres.
- Cruza monopunto por aristas, intercambiando subárboles entre padres. La raíz no es un corte de arista. Los padres de una hoja se copian cuando no hay corte posible.
- Poda al exceder altura o presupuesto de nodos, promoviendo el operando más cercano por niveles y con prioridad izquierda en empates. Una hoja nunca puede quedar como operador.
- Mutación de hojas, operadores, switching y subrama aleatoria. La raíz sí es válida para regeneración de subrama. Los cuatro tipos están activos por defecto en la ejecución completa; casillas visibles permiten activar o descartar cada uno. Se conserva una probabilidad de mutación por hijo y, cuando corresponde mutar, se elige un tipo activo al azar con igual probabilidad. Sin tipos activos se desactiva la mutación y su control de probabilidad, conservando el valor para reactivarlo. Los élites se copian sin mutación y las demostraciones mantienen su selector individual.
- Los operadores unarios siempre evalúan la izquierda. La derecha puede conservarse como gen recesivo, visible con trazos punteados, utilizable en cruza y futuras mutaciones. No participa en el fenotipo, variables activas ni evaluación.
- El nivel máximo de evolución cuenta la raíz como 0. Los genotipos tienen hasta 63 nodos, incluyendo genes recesivos. El generador previo mantiene su altura en niveles, con raíz en 1.

La adaptación puede usar MSE, NMSE o R²; la pérdida que se minimiza es MSE, NMSE o `1 − R²`. Una predicción inválida descalifica al individuo completo. La evaluación protegida es configurable. NMSE y R² requieren referencias no constantes. El paro usa tolerancia de pérdida o máximo de generaciones después de G0.

## Elitismo y Hall of Fame

Elitismo configurable: copia sin variación los mejores individuos a la siguiente generación. Cero lo desactiva y siempre queda espacio para reproducción.

Hall of Fame configurable: archiva copias independientes de los mejores genotipos distintos de toda la ejecución, con generación de aparición y métricas. Persiste aunque salgan de la población y no los reinserta automáticamente. Cero lo desactiva. Se reinicia con cada ejecución y vive en memoria mientras la aplicación está abierta.

## Comparación de referencia y élites

La vista Comparación superpone la referencia (naranja, discontinua) y la predicción del individuo (azul, continua). Se actualiza al terminar G0 y cada generación y usa los puntos y políticas de evaluación de la corrida, tanto para referencias por ecuación como CSV. Los ejes incluyen ambas series y el cursor consulta el par de valores de la misma muestra.

En vivo sigue por defecto al mejor individuo de la última generación. El usuario puede elegir entre los mejores N, donde N es la cantidad de élites configurada, o consultar una generación anterior sin que cambie mientras continúa la corrida. Los élites mostrados son los mejores evaluados de esa generación, independientemente de su origen; con elitismo 0 se muestra el mejor y se informa que el elitismo está desactivado.

Se conservan copias de los árboles y métricas por generación separadas del Hall of Fame. La predicción más reciente se prepara en el trabajador de evolución. Las curvas históricas se reconstruyen al consultarlas. Se muestran ecuación, MSE, NMSE, R², datos reparados y advertencias por predicciones inválidas. Una nueva ejecución reinicia esta comparación y su historial; las demos permanecen independientes.

## Evidencia y estados

Las comparaciones de cruza identifican ramas de A en azul y de B en verde; las reparaciones se marcan en naranja. Las mutaciones muestran antes y después. El historial permite inspeccionar operaciones reales de la última generación. Las demostraciones conservan sus copias y resultados al cambiar la generación de la corrida. Cambiar la fuente o los parámetros de la demo de selección limpia únicamente esa prueba.

Los ajustes del algoritmo modificados exigen iniciar una nueva ejecución para aplicarlos; los resultados previos permanecen identificados. El trabajo de evolución se ejecuta fuera del hilo de interfaz. Pausar permite terminar la generación en curso. La gráfica muestra mejor pérdida y media de individuos válidos, con escala `log(1 + pérdida)`.
