# Evolutionary Lab

Laboratorio interactivo de **algoritmos evolutivos** para estudiar, implementar y visualizar el comportamiento de poblaciones, individuos y operadores genéticos. Es un proyecto académico basado inicialmente en los Proyectos 1 y 2 de *Algoritmos evolutivos: un enfoque práctico*, de Lourdes Araujo y Carlos Cervigón.

**Estado actual:** Proyectos 1 y 2 integrados (M18–M19 y M21–M23). La aplicación ejecuta funciones verificadas de maximización y minimización con una o varias variables, mediante representación binaria o real. Permite navegar generaciones, inspeccionar individuos y analizar objetivo y diversidad. Ambos proyectos comparten un motor reproducible, independiente de Qt, ejecutado en segundo plano. Se conservan los temas claro, oscuro y del sistema.

## Objetivos

- Comprender genotipo, fenotipo, función objetivo y adaptación mediante ejemplos interactivos.
- Observar selección por ruleta, muestreo estocástico universal y torneo binario.
- Visualizar cruzamiento, mutación, reemplazo, diversidad genética y convergencia entre generaciones.
- Implementar los algoritmos desde cero en Python, sin delegar su lógica a bibliotecas de algoritmos evolutivos.
- Ampliar el laboratorio durante el curso con nuevos problemas, operadores, representaciones y ejercicios.

## Tecnologías

Python 3.12 · [uv](https://docs.astral.sh/uv/) · PySide6 · PyQtGraph · NumPy · SQLite (en una fase posterior). Calidad: Ruff, mypy y pytest. Desarrollo y ejecución previstos para **Linux y Windows** desde el repositorio; no se contemplan instaladores por ahora.

## Preparación del entorno

Se requiere `uv` instalado. En la raíz del repositorio:

```bash
uv sync --locked
uv run python --version
uv run python -c "import PySide6, pyqtgraph, numpy; print('Dependencies OK')"
```

Para abrir la aplicación:

```bash
uv run evolutionary-lab
```

En **Laboratorio → Parámetros**, elige proyecto, función, dominios, población, generaciones, semilla y operadores, y pulsa **Ejecutar con estos parámetros**. El Proyecto 1 permite configurar la precisión binaria; el Proyecto 2 usa una componente real por variable, mutación uniforme y cruzamiento monopunto, uniforme, aritmético o SBX. Monopunto requiere dos variables. **Simulación** muestra curvas, mapas de calor o coordenadas normalizadas según la dimensión. **Análisis** muestra el objetivo y la diversidad adecuada a la representación. Los valores iniciales (10 individuos, 100 generaciones y semilla 42) son de demostración.

**Pausar** detiene la reproducción del historial; **Cancelar cálculo** detiene el worker entre generaciones. Usa Anterior/Siguiente, el deslizador o **Ir a generación** para explorar los snapshots disponibles. Puedes ajustar la velocidad o desactivar la reproducción animada. **Reiniciar** descarta el historial actual. La interfaz limita el historial a 100 000 individuos almacenados en memoria.

**Configuración**, en la parte inferior de la barra lateral, guarda el tema mediante `QSettings`. Experimentos y Aprendizaje siguen pendientes. Para cerrar, utiliza la ventana o **Ctrl+Q**.

La versión de Python del proyecto está fijada a **3.12** en `.python-version`; `uv` utiliza ese intérprete aunque el Python del sistema sea distinto. No se necesitan dependencias adicionales a las declaradas en `pyproject.toml`.

Comandos de calidad:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Ruff, mypy en modo estricto y pytest están configurados en `pyproject.toml`. Las pruebas comprueban la independencia del núcleo respecto a Qt, la navegación, las pestañas, los temas y su persistencia, el tamaño mínimo y el arranque del punto de entrada instalado. Las pruebas de GUI usan Qt en modo `offscreen`, no requieren pantalla y guardan preferencias en archivos temporales.

Comprobación gráfica breve: abre el punto de entrada instalado, verifica que la ventana esté visible y cierra el bucle de eventos con un código de salida. La captura es opcional y no se versiona:

```bash
uv run python scripts/smoke_gui.py --screenshot output/gui-smoke.png
uv run python scripts/smoke_gui.py --settings --screenshot output/settings-smoke.png
uv run python scripts/smoke_gui.py --simulate --theme dark --screenshot output/gui/mvp-dark.png
uv run python scripts/smoke_gui.py --simulate --project 2 --problem project_01.rastrigin --real-crossover arithmetic --screenshot output/gui/project2.png
```

En Linux sin servidor gráfico, puedes comprobar el arranque con `QT_QPA_PLATFORM=offscreen uv run python scripts/smoke_gui.py`. Esta modalidad no verifica la integración con una pantalla real.

Los iconos SVG de Tabler son recursos locales; su [licencia MIT y atribución](src/evolutionary_lab/presentation/assets/icons/ATTRIBUTION.md) se distribuyen con el paquete.

## Alcance inicial

La primera entrega demostrable implementa **f1 de maximización de una variable del Proyecto 1** con cromosomas binarios, selección por ruleta/SUS/torneo, cruzamiento monopunto, mutación por bit y reemplazo de referencia o mejora estricta de clase. El perfil de referencia conserva la secuencia del capítulo 2; las alternativas y las correcciones de límites respecto al C++ se documentan en arquitectura.

El Proyecto 2 reutiliza el catálogo verificado del Proyecto 1. SBX conserva por separado la expresión impresa del libro y una extensión continua; el recorte al dominio es una política explícita del laboratorio. La diversidad real usa distancia absoluta normalizada por dominio, distinta de Hamming. Las verificaciones y limitaciones de las fórmulas están en [`docs/PROJECT_02_VERIFICATION.md`](docs/PROJECT_02_VERIFICATION.md).

Las funciones personalizadas, la persistencia SQLite, los ejercicios guiados y los formatos avanzados de exportación quedan pendientes.

## Documentación

- [`INSTRUCTIONS.md`](INSTRUCTIONS.md): alcance, requisitos y reglas académicas.
- [`AGENTS.md`](AGENTS.md): instrucciones operativas para agentes de programación.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): límites de módulos y contratos.
- [`docs/ROADMAP.md`](docs/ROADMAP.md): planificación por hitos.
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md): estado y siguiente paso para retomar el desarrollo.

La documentación técnica está en inglés; la interfaz y los contenidos educativos estarán en español y preparados para incorporar otros idiomas en el futuro.

## Material bibliográfico

Araujo, L., y Cervigón, C. (2009). *Algoritmos evolutivos: un enfoque práctico*. Alfaomega / RA-MA. Sección de optimización de funciones y Apéndice B (solución en C++ del Proyecto 1).

El PDF del libro es material de referencia del usuario y **no debe añadirse al repositorio ni redistribuirse**. Si es necesario revisar su código o ecuaciones, debe proporcionarse localmente al agente mediante una ruta no versionada.

## Desarrollo

Los hitos se implementarán de manera incremental y verificable. No se realizarán publicaciones en repositorios remotos sin autorización expresa. La guía de contribución y la política de versiones se ampliarán conforme avance el proyecto.
