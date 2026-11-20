from PySide6.QtCore import QCoreApplication

STRINGS = {
    "project": "Proyecto del libro",
    "project_binary": "Proyecto 1 · Binaria",
    "project_real": "Proyecto 2 · Real",
    "representation": "Representación",
    "encoding_binary": "Bits por variable · Precisión configurable",
    "encoding_real": "Una componente real por variable",
    "real_crossover": "Operador de cruzamiento",
    "real_cross_one_point": "Monopunto",
    "real_cross_uniform": "Uniforme",
    "real_cross_arithmetic": "Aritmético",
    "real_cross_sbx": "Simulated Binary Crossover (SBX)",
    "real_crossover_help": (
        "Monopunto corta entre variables y requiere al menos dos. "
        "Los otros operadores admiten una o varias variables."
    ),
    "mutation_operator": "Operador de mutación",
    "mutation_bit_flip": "Inversión de bits",
    "mutation_uniform_reset": "Reemplazo uniforme en el dominio",
    "real_mutation_rate": "Probabilidad de mutación por variable",
    "real_mutation_help": (
        "Cada variable seleccionada se sustituye por un valor uniforme en su dominio."
    ),
    "real_crossover_probability_help": "Una decisión de cruzamiento por pareja.",
    "uniform_swap": "Intercambio por variable",
    "uniform_swap_help": (
        "Probabilidad de intercambiar cada componente; los dos hijos "
        "usan máscaras complementarias."
    ),
    "arithmetic_alpha": "Peso α",
    "arithmetic_alpha_help": (
        "Hijos: α p₁ + (1−α) p₂ y (1−α) p₁ + α p₂. α se fija para la ejecución."
    ),
    "sbx_index": "Índice de distribución n",
    "sbx_index_help": (
        "El Proyecto 2 usa n = 1. Un índice mayor concentra los hijos "
        "más cerca de los progenitores."
    ),
    "sbx_formula": "Fórmula de SBX",
    "sbx_literal": "Libro · Expresión impresa",
    "sbx_continuous": "Extensión · Distribución continua",
    "sbx_formula_help": (
        "Para u < 0.5: el libro imprime β = 2 u^(1/(n+1)); "
        "la extensión usa β = (2u)^(1/(n+1)). Un sorteo por pareja."
    ),
    "bounds_policy": "Si SBX excede los límites",
    "bounds_clip": "Recortar al dominio (extensión)",
    "bounds_reject": "Detener con error",
    "bounds_policy_help": (
        "SBX puede salir del dominio. El libro no especifica reparación; "
        "el recorte es una política explícita de este laboratorio."
    ),
    "real_reproduction_help": (
        "Proyecto 2: parejas consecutivas, una decisión de cruce por pareja "
        "y mutación uniforme por variable. El individuo impar sólo se muta."
    ),
    "real_diversity_axis": "Distancia media normalizada (L1)",
    "real_diversity_help": (
        "Promedio entre pares de la distancia absoluta por variable, dividida "
        "por la amplitud de su dominio; después se promedian las variables. "
        "Rango 0–1. Es una medida distinta de Hamming."
    ),
    "binary_diversity_help": (
        "Fracción media de bits distintos entre pares de individuos (0–1)."
    ),
    "real_genotype": "Cromosoma real (variables)",
    "real_cut_point": "Corte entre variables",
    "real_mutation_attempt": "Reemplazos uniformes intentados",
    "operator_details": "Cruzamiento intentado",
    "bounds_repairs": "Recortes del hijo antes de mutar",
    "real_operator_trace": "{operator} · Sorteo de pareja: {draw:.6g}",
    "real_sbx_trace": "u = {draw:.6g} · β = {beta:.6g}",
    "real_alpha_trace": "α = {alpha:g}",
    "real_swap_trace": "Variables intercambiadas: {variables}",
    "real_reset_trace": "x{variable} → {value:.12g} (u = {draw:.6g})",
    "crossover_skipped": "Sin cruzamiento",
    "project_problem_title": "Proyecto {project} · {problem}",
    "project_lab_description": (
        "Proyecto {project} · Optimización de funciones · Representación {encoding}"
    ),
    "binary_short": "binaria",
    "real_short": "real",
    "error_real_bounds": (
        "SBX produjo un hijo fuera del dominio. Puedes activar el recorte "
        "explícito en Parámetros o elegir otro cruzamiento."
    ),
    "error_real_overflow": (
        "El cruzamiento produjo valores no finitos. Reduce los dominios "
        "o cambia los parámetros de SBX."
    ),
    "parameter_operators": "Operadores genéticos",
    "parameter_execution": "Ejecución",
    "variable": "Variable",
    "variable_count": "Número de variables",
    "domain_lower": "Límite inferior",
    "domain_upper": "Límite superior",
    "precision_short": "Paso máximo",
    "variable_count_help": "Estas familias admiten entre 1 y 10 variables en la GUI.",
    "direction_help": "Filtra las funciones según la dirección propuesta en el libro.",
    "generation_limit_help": (
        "Número de transiciones; la población inicial es la generación 0."
    ),
    "seed_help": (
        "Una semilla entera reproduce el experimento con la misma configuración."
    ),
    "selection_help": "Ruleta y SUS usan pesos; el torneo compara dos individuos.",
    "crossover_help": (
        "Probabilidad por candidato en el perfil del libro, o por pareja "
        "en la variante."
    ),
    "reproduction_help": (
        "Cada variable se cruza con la correspondiente del otro progenitor."
    ),
    "replacement_help": (
        "Libro: sustitución directa. Clase: sólo mejora estricta del objetivo."
    ),
    "zero_weights_help": (
        "Política explícita cuando todos los pesos de selección son cero."
    ),
    "variable_domain_help": (
        "Intervalo permitido: [{lower:g}, {upper:g}]. Puedes restringir la búsqueda."
    ),
    "error_variable_domain": (
        "Variable {variable}: usa límites finitos, inferior < superior, "
        "dentro de [{lower:g}, {upper:g}]."
    ),
    "surface_chart_title": "Función objetivo y población · Dos variables",
    "parallel_chart_title": "Coordenadas de la población",
    "parallel_help": (
        "Cada trazo es un individuo. Cada variable se normaliza a su "
        "dominio (0 a 1); consulta el objetivo en el inspector."
    ),
    "variable_axis": "Variable",
    "normalized_axis": "Posición en el dominio (0–1)",
    "x1_axis": "Fenotipo x₁",
    "x2_axis": "Fenotipo x₂",
    "fitness_reference": "cmax de esta generación",
    "fitness_objective_only": "Sólo objetivo (torneo)",
    "maximize": "Maximizar",
    "minimize": "Minimizar",
    "optimization_direction": "Dirección de optimización",
    "objective_problem": "Función objetivo",
    "fitness_policy": "Transformación de aptitud",
    "fitness_policy_help": (
        "La selección usa pesos no negativos; el objetivo original se conserva."
    ),
    "fitness_identity": "Identidad · Aptitud = objetivo",
    "fitness_book": "Libro · 1.05 cmax − objetivo",
    "fitness_signed": "Extensión con margen para signos",
    "nonnegative_identity_help": "Mayor objetivo significa mayor aptitud de selección.",
    "minimization_book_help": (
        "Libro: w = 1.05 cmax − g. Se revisa toda la población; requiere cmax ≥ 0."
    ),
    "minimization_signed_help": (
        "Extensión explícita: w = cmax + 0.05 |cmax| − g. Admite objetivos "
        "negativos; cmax cambia por generación."
    ),
    "problem_description": "f = {formula}\nDominios del libro: {domains}",
    "f1_readable": "sen⁶(5πx) exp[−2 ln(2) ((x−0.1)/0.8)²]",
    "error_negative_cmax": (
        "La transformación literal del libro produciría pesos negativos. "
        "Elige la extensión con margen para signos en Parámetros."
    ),
    "error_fitness_overflow": (
        "La transformación de aptitud excede el rango numérico. Reduce los "
        "dominios o cambia la función."
    ),
    "simulation_problem_title": "Proyecto 1 · Función f1",
    "population_chart_title": "Función objetivo y población actual",
    "fitness_chart_title": "Evolución del valor objetivo",
    "diversity_chart_title": "Diversidad genética por generación",
    "reset_view": "Restablecer vista",
    "reset_view_help": "Ajusta los ejes a los datos sin recalcular el historial.",
    "legend_population": "Individuos",
    "legend_best": "Mejor",
    "legend_selected": "Seleccionado",
    "summary_best": "Mejor actual",
    "summary_diversity": "Diversidad",
    "generation_meta": "Generación {generation} · {size} individuos",
    "parameter_problem": "Problema",
    "parameter_population": "Población",
    "parameter_selection": "Selección",
    "parameter_variation": "Cruza y mutación",
    "parameter_replacement": "Reemplazo y ejecución",
    "resume_history": "Reanudar",
    "reset_simulation_help": "Cancela el cálculo y vacía el historial actual.",
    "population_size": "Individuos en la población",
    "generation_limit": "Generaciones a calcular",
    "precision": "Precisión (paso máximo)",
    "selection_method": "Método de selección",
    "crossover_rate": "Probabilidad de cruzamiento",
    "mutation_rate": "Probabilidad de mutación por bit",
    "reproduction_policy": "Emparejamiento y corte",
    "replacement_strategy": "Reemplazo",
    "zero_weights": "Si toda la aptitud es cero",
    "selection_roulette": "Ruleta",
    "selection_sus": "Muestreo estocástico universal (SUS)",
    "selection_tournament": "Torneo binario",
    "reproduction_book": "Libro: corte común",
    "reproduction_pairwise": "Parejas: corte individual",
    "replacement_book": "Libro: sustitución directa",
    "replacement_classroom": "Clase: mejora estricta",
    "zero_weights_error": "Detener con error",
    "zero_weights_uniform": "Selección uniforme (variante)",
    "parameter_description": (
        "Función f1 · Maximización · Dominio [0,1] · Codificación binaria"
    ),
    "parameter_history_note": (
        "Los cambios se aplican a la próxima ejecución. El historial visible "
        "conserva su configuración original. La misma semilla y configuración "
        "reproducen los resultados en esta versión."
    ),
    "precision_help": (
        "Paso máximo por variable: determina su longitud binaria; no "
        "redondea el objetivo."
    ),
    "mutation_help": "1 % por bit corresponde a una probabilidad de 0.01.",
    "reproduction_book_help": (
        "Referencia: una probabilidad por individuo, candidatos consecutivos "
        "y un corte común por generación."
    ),
    "reproduction_pairwise_help": (
        "Variante: una probabilidad y un corte por pareja consecutiva. "
        "El último individuo impar sólo se muta."
    ),
    "run_parameters": "Ejecutar con estos parámetros",
    "statistics_empty": (
        "Inicia una simulación para analizar la adaptación y la diversidad."
    ),
    "generation_best": "Mejor de generación",
    "generation_mean": "Promedio",
    "best_so_far": "Mejor acumulado",
    "diversity_axis": "Diversidad (Hamming normalizado)",
    "statistics_summary": (
        "Generación {generation} · Mejor: {best:.6f} · Promedio: {mean:.6f} "
        "· Mejor acumulado: {best_so_far:.6f} · Diversidad: {diversity:.4f}"
    ),
    "playback_speed": "Velocidad del historial",
    "generations_per_second": "{rate} gen/s",
    "animate_history": "Reproducción animada",
    "show_final": "Ir al final",
    "replay_manual": "Sin animación · Navegación manual",
    "error_precision": (
        "Introduce una precisión positiva y finita, por ejemplo 0.001."
    ),
    "error_seed": "La semilla debe ser un número entero, por ejemplo 42.",
    "error_short_chromosome": (
        "Esta precisión sólo produce un bit. Reduce la precisión "
        "o configura el cruzamiento en 0 %."
    ),
    "error_precision_grid": (
        "La precisión es demasiado fina para representar números distintos. "
        "Usa una precisión mayor, por ejemplo 0.001."
    ),
    "error_zero_fitness": (
        "Todas las aptitudes son cero. Ruleta y SUS necesitan una suma positiva. "
        "Puedes elegir selección uniforme explícita o torneo en Parámetros."
    ),
    "error_negative_fitness": (
        "La aptitud de selección requiere valores no negativos."
    ),
    "error_nonfinite_objective": (
        "La función produjo un valor no finito. Revisa el problema."
    ),
    "error_history_size": (
        "Reduce la población o las generaciones: esta versión conserva hasta "
        "{limit} individuos en el historial."
    ),
    "start_simulation": "Iniciar cálculo",
    "cancel_computation": "Cancelar cálculo",
    "reset_simulation": "Reiniciar",
    "previous_generation": "Anterior",
    "next_generation": "Siguiente",
    "play_history": "Reproducir",
    "pause_history": "Pausar",
    "stop_playback": "Detener",
    "jump_generation": "Ir a generación",
    "replay_idle": "Reproducción detenida",
    "replay_paused": "Reproducción pausada",
    "replay_playing": "Reproduciendo historial",
    "replay_finished": "Fin del historial",
    "computation_idle": "Cálculo listo · El historial se reproduce por separado.",
    "computation_progress": "Calculando · {count} generaciones disponibles",
    "computation_cancelling": "Cancelando al terminar la generación actual…",
    "computation_completed": "Cálculo completado · {count} generaciones disponibles",
    "computation_cancelled": "Cálculo cancelado · {count} generaciones conservadas",
    "computation_failed": "El cálculo falló · {count} generaciones conservadas",
    "load_population": "Cargar población inicial",
    "plot_ready": "Inicia el cálculo para explorar generaciones y datos reales.",
    "computing": "Calculando en segundo plano…",
    "run_error": (
        "No se pudo calcular la simulación. Revisa los parámetros e inténtalo de nuevo."
    ),
    "phenotype_axis": "Fenotipo x",
    "objective_axis": "Objetivo f(x)",
    "generation_summary": (
        "Generación {generation} · {size} individuos · Mejor: {best:.8f} "
        "· Rombo: mejor individuo"
    ),
    "individual": "Individuo",
    "individual_number": "Individuo {identifier}",
    "generation": "Generación",
    "genotype": "Genotipo binario (MSB → LSB)",
    "decimal_genotype": "Genotipo decimal",
    "phenotype": "Fenotipo (variables)",
    "objective": "Valor objetivo",
    "fitness": "Aptitud de selección",
    "seed": "Semilla",
    "parent_slots": "Progenitores del intento",
    "parent_probability": "Probabilidad del padre seleccionado",
    "parent_draw": "Sorteo / posición / torneo del padre",
    "cut_point": "Corte desde el extremo LSB",
    "mutation_attempt": "Mutación intentada (posiciones LSB)",
    "replacement_decision": "Decisión de reemplazo",
    "parent_origin": "Generación {generation}, individuo {identifier}",
    "tournament_participants": "Torneo: individuos {first} y {second}",
    "child_adopted": "Descendiente adoptado",
    "parent_retained": "Progenitor conservado",
    "unavailable": "Sin datos",
    "none": "Ninguna",
    "app_name": "Evolutionary Lab",
    "brand_name": "Evolutionary\nLab",
    "brand_description": "Laboratorio de algoritmos evolutivos",
    "version": "Versión {version}",
    "shell_status": "Proyectos 1 y 2 · Configura y explora tus experimentos.",
    "quit": "Salir",
    "settings": "Configuración",
    "settings_description": "Preferencias del laboratorio",
    "settings_categories": "Categorías de configuración",
    "appearance": "Apariencia",
    "theme": "Tema de la interfaz",
    "theme_description": (
        "Elige una apariencia clara u oscura, o sigue la preferencia del sistema."
    ),
    "preferences_saved": (
        "Los cambios se aplican al instante y se guardan para la próxima sesión."
    ),
    "preferences_save_error": (
        "El tema se aplicó, pero no pudo guardarse. "
        "Revisa los permisos de la carpeta de configuración."
    ),
    "system": "Sistema",
    "light": "Claro",
    "dark": "Oscuro",
    "navigation": "Secciones del laboratorio",
    "workspaces": "Espacios de trabajo",
    "laboratory": "Laboratorio",
    "laboratory_description": "Proyecto 1 · Optimización de funciones",
    "experiments": "Experimentos",
    "experiments_description": "Historial y comparación de ejecuciones",
    "learning": "Aprendizaje",
    "learning_description": "Conceptos y ejercicios de algoritmos evolutivos",
    "simulation": "Simulación",
    "analysis": "Análisis",
    "parameters": "Parámetros",
    "history": "Historial",
    "comparison": "Comparación",
    "concepts": "Conceptos",
    "exercises": "Ejercicios",
    "simulation_area": "Área de simulación",
    "simulation_empty_title": "Sin simulación activa",
    "simulation_empty_description": (
        "Este espacio mostrará la función objetivo y los individuos de cada "
        "generación. La ejecución y las visualizaciones se incorporarán "
        "en próximas entregas."
    ),
    "inspector": "Inspector de individuos",
    "inspector_empty_title": "Sin individuo seleccionado",
    "inspector_empty_description": (
        "Aquí podrás consultar el genotipo, el fenotipo y la evaluación "
        "de un individuo al seleccionarlo en una simulación."
    ),
    "analysis_empty_title": "Aún no hay resultados",
    "analysis_empty_description": (
        "Las gráficas de adaptación y diversidad estarán disponibles "
        "cuando se incorpore la ejecución de simulaciones."
    ),
    "parameters_empty_title": "Configuración del experimento",
    "parameters_empty_description": (
        "Aquí se definirán el problema, la población, los operadores y "
        "la semilla. Los controles se habilitarán al incorporar "
        "la validación y el motor evolutivo."
    ),
    "history_empty_title": "Historial de experimentos",
    "history_empty_description": (
        "El almacenamiento local se incorporará en una próxima entrega. "
        "Entonces podrás guardar y volver a abrir tus experimentos."
    ),
    "comparison_empty_title": "Comparación de ejecuciones",
    "comparison_empty_description": (
        "Este espacio permitirá comparar los resultados de experimentos "
        "independientes cuando estén disponibles las simulaciones "
        "y el almacenamiento local."
    ),
    "concepts_empty_title": "Comprende los mecanismos",
    "concepts_empty_description": (
        "La biblioteca de conceptos, fórmulas y explicaciones en español "
        "se incorporará en la etapa de contenidos educativos."
    ),
    "exercises_empty_title": "Aprende experimentando",
    "exercises_empty_description": (
        "Los ejercicios guiados y las demostraciones de operadores "
        "se incorporarán después de completar el laboratorio básico."
    ),
}


def text(key: str) -> str:
    return QCoreApplication.translate("EvolutionaryLab", STRINGS[key])
