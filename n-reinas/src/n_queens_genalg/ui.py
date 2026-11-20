from __future__ import annotations

import time
import dearpygui.dearpygui as dpg

from n_queens_genalg.ga_engine import (
    GenerationRecord,
    GeneticQueensSolver,
    Individual,
    evaluate_individual,
)

# Color Palette
COL_BG_DARK = (18, 20, 27, 255)
COL_PANEL_BG = (26, 29, 39, 255)
COL_BOARD_LIGHT = (232, 224, 205, 255)
COL_BOARD_DARK = (98, 114, 138, 255)
COL_BOARD_BORDER = (55, 65, 85, 255)
COL_QUEEN_SAFE = (38, 166, 91, 255)
COL_QUEEN_CONFLICT = (224, 68, 68, 255)
COL_QUEEN_CROWN = (255, 215, 70, 255)
COL_QUEEN_OUTLINE = (24, 26, 34, 255)
COL_CONFLICT_LINE = (245, 75, 75, 215)
COL_SWAP_HIGHLIGHT = (255, 184, 48, 95)
COL_SELECTED_COL = (86, 156, 214, 110)
COL_ACCENT = (86, 156, 214, 255)
COL_SUCCESS = (78, 201, 176, 255)
COL_WARNING = (235, 175, 65, 255)
COL_DANGER = (244, 90, 90, 255)
COL_TEXT_DIM = (155, 165, 185, 255)


class NQueensApp:
    def __init__(self) -> None:
        self.solver = GeneticQueensSolver(
            n=8,
            pop_size=60,
            crossover_rate=0.35,
            mutation_rate=0.65,
            tournament_k=3,
            elitism_count=2,
            fitness_mode="Crawford [CRA92] (Penalización)",
            crossover_mode="OX (Orden)",
            selection_mode="Torneo",
        )
        self.running: bool = False
        self.auto_stop_on_solution: bool = True
        self.steps_per_sec: float = 12.0
        self.last_step_time: float = 0.0

        self.selected_gen_idx: int = 0
        self.selected_ind_idx: int = 0
        self.selected_move_idx: int = 0
        self.show_conflict_lines: bool = True
        self.show_attack_diagonals: bool = False
        self.manual_swap_col: int | None = None

        self.board_canvas_size: int = 470
        self.vec_canvas_width: int = 470
        self.vec_canvas_height: int = 92
        self.op_canvas_width: int = 500
        self.op_canvas_height: int = 165

    @property
    def current_record(self) -> GenerationRecord:
        idx = max(0, min(self.selected_gen_idx, len(self.solver.history) - 1))
        return self.solver.history[idx]

    @property
    def current_individual(self) -> Individual:
        rec = self.current_record
        idx = max(0, min(self.selected_ind_idx, len(rec.population) - 1))
        return rec.population[idx]

    def setup_themes(self) -> None:
        with dpg.theme(tag="global_theme"):
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 10)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 6, 4)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6)
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 4)
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COL_BG_DARK)
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COL_PANEL_BG)
                dpg.add_theme_color(dpg.mvThemeCol_Border, (52, 58, 76, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Header, (52, 73, 105, 255))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (68, 96, 138, 255))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (82, 116, 168, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (50, 68, 98, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (66, 90, 130, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (84, 114, 165, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (36, 42, 56, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (48, 56, 74, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (38, 50, 72, 255))

        with dpg.theme(tag="btn_play_theme"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (36, 128, 82, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (46, 158, 102, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (30, 105, 68, 255))

        with dpg.theme(tag="btn_pause_theme"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (175, 112, 32, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (205, 134, 42, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (145, 92, 26, 255))

        with dpg.theme(tag="btn_reset_theme"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (142, 48, 56, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (175, 60, 70, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (118, 38, 45, 255))

        dpg.bind_theme("global_theme")

    def draw_crown_icon(self, drawlist: str, cx: float, cy: float, radius: float, fill_col: tuple[int, ...]) -> None:
        dpg.draw_circle(
            (cx, cy),
            radius,
            color=COL_QUEEN_OUTLINE,
            fill=fill_col,
            thickness=2.0,
            parent=drawlist,
        )
        w = radius * 0.62
        h = radius * 0.52
        base_y = cy + h * 0.65
        top_y = cy - h * 0.65
        mid_y = cy + h * 0.05

        pts = [
            (cx - w, base_y),
            (cx - w, top_y),
            (cx - w * 0.35, mid_y),
            (cx, top_y - h * 0.15),
            (cx + w * 0.35, mid_y),
            (cx + w, top_y),
            (cx + w, base_y),
        ]
        dpg.draw_polygon(
            pts,
            color=COL_QUEEN_OUTLINE,
            fill=COL_QUEEN_CROWN,
            thickness=1.5,
            parent=drawlist,
        )

    def render_board(self) -> None:
        dpg.delete_item("board_drawlist", children_only=True)
        ind = self.current_individual
        n = ind.n
        size = self.board_canvas_size
        margin = 32
        grid_px = size - 2 * margin
        cell = grid_px / n

        dpg.draw_rectangle(
            (0, 0),
            (size, size),
            color=COL_BOARD_BORDER,
            fill=(22, 25, 34, 255),
            rounding=6,
            thickness=1.5,
            parent="board_drawlist",
        )

        # Draw column & row labels (1..N as in the book figure)
        for idx in range(n):
            label = str(idx + 1)
            col_cx = margin + idx * cell + cell * 0.5 - 4
            row_cy = margin + idx * cell + cell * 0.5 - 7
            dpg.draw_text((col_cx, 7), label, size=15, color=(210, 220, 235, 255), parent="board_drawlist")
            dpg.draw_text((col_cx, size - 23), label, size=14, color=COL_TEXT_DIM, parent="board_drawlist")
            dpg.draw_text((10, row_cy), label, size=15, color=(210, 220, 235, 255), parent="board_drawlist")
            dpg.draw_text((size - 21, row_cy), label, size=14, color=COL_TEXT_DIM, parent="board_drawlist")

        conflicting_cols: set[int] = set()
        for edge in ind.conflict_edges:
            conflicting_cols.add(edge.col_i)
            conflicting_cols.add(edge.col_j)

        # Draw NxN cells
        for r in range(n):
            for c in range(n):
                x0 = margin + c * cell
                y0 = margin + r * cell
                x1 = x0 + cell
                y1 = y0 + cell
                is_light = (r + c) % 2 == 0
                fill = COL_BOARD_LIGHT if is_light else COL_BOARD_DARK
                dpg.draw_rectangle(
                    (x0, y0),
                    (x1, y1),
                    color=(40, 46, 60, 90),
                    fill=fill,
                    thickness=1.0,
                    parent="board_drawlist",
                )

        # Highlight swapped columns if this individual had a swap mutation
        if ind.mutation_swap is not None:
            for s_col in ind.mutation_swap:
                if 0 <= s_col < n:
                    x0 = margin + s_col * cell
                    y0 = margin
                    dpg.draw_rectangle(
                        (x0, y0),
                        (x0 + cell, y0 + grid_px),
                        color=(255, 190, 50, 200),
                        fill=COL_SWAP_HIGHLIGHT,
                        thickness=2.0,
                        parent="board_drawlist",
                    )

        # Highlight column selected for manual swap
        if self.manual_swap_col is not None and 0 <= self.manual_swap_col < n:
            x0 = margin + self.manual_swap_col * cell
            y0 = margin
            dpg.draw_rectangle(
                (x0, y0),
                (x0 + cell, y0 + grid_px),
                color=COL_ACCENT,
                fill=COL_SELECTED_COL,
                thickness=2.5,
                parent="board_drawlist",
            )

        # Optional: draw diagonal rays for all queens
        if self.show_attack_diagonals:
            for c_idx, r_val in enumerate(ind.genes):
                r_idx = r_val - 1
                cx = margin + (c_idx + 0.5) * cell
                cy = margin + (r_idx + 0.5) * cell
                for dc, dr in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    steps = min(
                        c_idx if dc < 0 else (n - 1 - c_idx),
                        r_idx if dr < 0 else (n - 1 - r_idx),
                    )
                    if steps > 0:
                        ex = margin + (c_idx + dc * steps + 0.5) * cell
                        ey = margin + (r_idx + dr * steps + 0.5) * cell
                        dpg.draw_line(
                            (cx, cy),
                            (ex, ey),
                            color=(255, 225, 90, 75),
                            thickness=1.5,
                            parent="board_drawlist",
                        )

        # Draw conflict lines between attacking queens (|R_i - R_j| == |i - j|)
        if self.show_conflict_lines:
            for edge in ind.conflict_edges:
                x_i = margin + (edge.col_i - 0.5) * cell
                y_i = margin + (edge.row_i - 0.5) * cell
                x_j = margin + (edge.col_j - 0.5) * cell
                y_j = margin + (edge.row_j - 0.5) * cell
                dpg.draw_line(
                    (x_i, y_i),
                    (x_j, y_j),
                    color=(25, 10, 10, 220),
                    thickness=5.5,
                    parent="board_drawlist",
                )
                dpg.draw_line(
                    (x_i, y_i),
                    (x_j, y_j),
                    color=COL_CONFLICT_LINE,
                    thickness=3.0,
                    parent="board_drawlist",
                )

        # Draw Queens
        q_radius = max(8.0, min(cell * 0.37, 26.0))
        for c_idx, r_val in enumerate(ind.genes):
            col_1 = c_idx + 1
            r_idx = r_val - 1
            cx = margin + (c_idx + 0.5) * cell
            cy = margin + (r_idx + 0.5) * cell
            in_conflict = col_1 in conflicting_cols
            fill_col = COL_QUEEN_CONFLICT if in_conflict else COL_QUEEN_SAFE
            self.draw_crown_icon("board_drawlist", cx, cy, q_radius, fill_col)

        # Render Chromosome Vector diagram below board (matching book's [ 2 | 4 | 1 | 3 ] representation)
        dpg.delete_item("vector_drawlist", children_only=True)
        vw = self.vec_canvas_width
        vh = self.vec_canvas_height
        dpg.draw_rectangle(
            (0, 0),
            (vw, vh),
            color=COL_BOARD_BORDER,
            fill=(22, 25, 34, 255),
            rounding=6,
            thickness=1.2,
            parent="vector_drawlist",
        )
        v_margin = 32
        box_w = (vw - 2 * v_margin) / n
        box_y0 = 32
        box_y1 = 70

        # Downward arrow indicator from board to chromosome vector (like textbook diagram)
        mid_x = vw * 0.5
        dpg.draw_text(
            (12, 7),
            "Vector Individuo R = [R_1..R_N] (Posición i = Columna, Valor = Fila):",
            size=14,
            color=COL_ACCENT,
            parent="vector_drawlist",
        )
        dpg.draw_triangle(
            (mid_x - 8, 22),
            (mid_x + 8, 22),
            (mid_x, 30),
            color=COL_ACCENT,
            fill=COL_ACCENT,
            parent="vector_drawlist",
        )

        for i, val in enumerate(ind.genes):
            bx0 = v_margin + i * box_w
            bx1 = bx0 + box_w
            col_1 = i + 1
            in_conflict = col_1 in conflicting_cols
            is_swapped = ind.mutation_swap is not None and i in ind.mutation_swap
            is_selected_col = self.manual_swap_col == i

            if is_selected_col:
                cell_bg = (45, 85, 130, 255)
                border_col = COL_ACCENT
            elif is_swapped:
                cell_bg = (95, 72, 24, 255)
                border_col = (255, 195, 55, 255)
            elif in_conflict:
                cell_bg = (82, 34, 38, 255)
                border_col = (225, 85, 85, 255)
            else:
                cell_bg = (32, 68, 52, 255)
                border_col = (65, 185, 115, 255)

            dpg.draw_rectangle(
                (bx0 + 1, box_y0),
                (bx1 - 1, box_y1),
                color=border_col,
                fill=cell_bg,
                thickness=1.8,
                rounding=3,
                parent="vector_drawlist",
            )
            dpg.draw_text(
                (bx0 + box_w * 0.5 - 6, box_y0 + 9),
                str(val),
                size=18,
                color=(245, 248, 255, 255),
                parent="vector_drawlist",
            )
            dpg.draw_text(
                (bx0 + box_w * 0.5 - 9, box_y1 + 3),
                f"c{col_1}",
                size=12,
                color=COL_TEXT_DIM,
                parent="vector_drawlist",
            )

    def render_genetic_operation_canvas(self) -> None:
        dpg.delete_item("op_drawlist", children_only=True)
        w = self.op_canvas_width
        h = self.op_canvas_height
        dpg.draw_rectangle(
            (0, 0),
            (w, h),
            color=COL_BOARD_BORDER,
            fill=(20, 23, 32, 255),
            rounding=6,
            thickness=1.2,
            parent="op_drawlist",
        )

        rec = self.current_record
        if not rec.logs:
            dpg.draw_text(
                (16, 60),
                "Generación 0 (Población Inicial aleatoria sin repeticiones).\nAvanza 1 generación para inspeccionar cruces y mutaciones paso a paso.",
                size=14,
                color=COL_TEXT_DIM,
                parent="op_drawlist",
            )
            return

        m_idx = max(0, min(self.selected_move_idx, len(rec.logs) - 1))
        log = rec.logs[m_idx]
        n = len(log.child_after_mut)
        box_w = min(34.0, (w - 135) / max(1, n))
        start_x = 120

        dpg.draw_text(
            (12, 8),
            f"Gen {log.generation} | Operación #{m_idx + 1}: {log.action}  ->  Conflictos Hijo: {log.child_conflicts}",
            size=14,
            color=COL_WARNING if log.child_conflicts > 0 else COL_SUCCESS,
            parent="op_drawlist",
        )

        rows_data = [
            ("Padre 1:", log.parent1, (45, 62, 88, 255)),
            ("Padre 2:", log.parent2 if log.parent2 else log.parent1, (45, 52, 78, 255)),
            ("Cruce:", log.child_before_mut, (42, 75, 72, 255)),
            ("Final (Mut):", log.child_after_mut, (38, 88, 58, 255) if log.child_conflicts == 0 else (68, 48, 65, 255)),
        ]

        for r_idx, (label, vec, bg_col) in enumerate(rows_data):
            y0 = 32 + r_idx * 31
            y1 = y0 + 25
            dpg.draw_text((12, y0 + 4), label, size=14, color=(205, 215, 230, 255), parent="op_drawlist")
            for c_idx, val in enumerate(vec):
                x0 = start_x + c_idx * box_w
                x1 = x0 + box_w - 2
                is_swapped = (r_idx == 3 and log.swapped_positions is not None and c_idx in log.swapped_positions)
                border = (255, 200, 60, 255) if is_swapped else (95, 115, 145, 200)
                fill = (120, 88, 25, 255) if is_swapped else bg_col
                dpg.draw_rectangle(
                    (x0, y0),
                    (x1, y1),
                    color=border,
                    fill=fill,
                    rounding=3,
                    thickness=1.6 if is_swapped else 1.0,
                    parent="op_drawlist",
                )
                dpg.draw_text(
                    (x0 + box_w * 0.32, y0 + 4),
                    str(val),
                    size=14,
                    color=(245, 248, 255, 255),
                    parent="op_drawlist",
                )

    def refresh_ui(self) -> None:
        rec = self.current_record
        ind = self.current_individual

        dpg.set_value("lbl_gen_count", f"Generación Vista: {rec.generation} / {len(self.solver.history) - 1}")
        dpg.set_value("lbl_best_conflicts", f"Mín. Conflictos [CRA92]: {rec.best.conflicts}")
        dpg.set_value("lbl_best_homaifar", f"Máx. Adaptación [HOM92]: {rec.best.homaifar_score:.3f}")
        dpg.set_value("lbl_solutions_count", f"Soluciones Únicas (0 ataques): {len(self.solver.found_solutions)}")

        if ind.is_solution:
            dpg.set_value("lbl_board_status", f"¡SOLUCIÓN VÁLIDA ENCONTRADA! Vector = {ind.genes}")
            dpg.configure_item("lbl_board_status", color=COL_SUCCESS)
        else:
            dpg.set_value(
                "lbl_board_status",
                f"Individuo #{self.selected_ind_idx + 1} | Vector = {ind.genes} | Conflictos = {ind.conflicts} | Homaifar = {ind.homaifar_score:.3f}",
            )
            dpg.configure_item("lbl_board_status", color=COL_WARNING)

        dpg.set_value("lbl_ind_origin", f"Origen: {ind.origin}  ({ind.parents_info})")

        if not ind.conflict_edges:
            dpg.set_value(
                "txt_conflict_details",
                "0 violaciones de restricción.\nSe cumple para todo i != j:\n  • R_i != R_j (Sin repetición de fila)\n  • |R_i - R_j| != |i - j| (Sin ataques diagonales)",
            )
        else:
            lines = [f"Violaciones detectadas ({len(ind.conflict_edges)} pares en ataque diagonal |R_i - R_j| == |i - j|):"]
            for idx, e in enumerate(ind.conflict_edges[:8], start=1):
                diff_r = abs(e.row_i - e.row_j)
                lines.append(
                    f"  {idx}. Col {e.col_i} (Fila {e.row_i}) <-> Col {e.col_j} (Fila {e.row_j})  [|{e.row_i}-{e.row_j}| = |{e.col_i}-{e.col_j}| = {diff_r}]"
                )
            if len(ind.conflict_edges) > 8:
                lines.append(f"  ... y {len(ind.conflict_edges) - 8} conflictos adicionales.")
            dpg.set_value("txt_conflict_details", "\n".join(lines))

        max_gen = max(0, len(self.solver.history) - 1)
        dpg.configure_item("slider_history_gen", max_value=max_gen)
        dpg.set_value("slider_history_gen", self.selected_gen_idx)

        dpg.delete_item("table_population", children_only=True)
        dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=32, parent="table_population")
        dpg.add_table_column(label="Vector R=[R1..RN]", width_stretch=True, parent="table_population")
        dpg.add_table_column(label="Conf [CRA92]", width_fixed=True, init_width_or_weight=85, parent="table_population")
        dpg.add_table_column(label="Hom [HOM92]", width_fixed=True, init_width_or_weight=85, parent="table_population")
        dpg.add_table_column(label="Operador / Origen", width_stretch=True, parent="table_population")

        for i, member in enumerate(rec.population[:40]):
            with dpg.table_row(parent="table_population"):
                is_sel = i == self.selected_ind_idx
                dpg.add_selectable(
                    label=f"{i + 1}",
                    span_columns=True,
                    default_value=is_sel,
                    callback=self.on_select_individual,
                    user_data=i,
                )
                dpg.add_text(str(member.genes), color=COL_SUCCESS if member.is_solution else (230, 235, 245, 255))
                dpg.add_text(
                    str(member.conflicts),
                    color=COL_SUCCESS if member.conflicts == 0 else (COL_WARNING if member.conflicts <= 2 else COL_DANGER),
                )
                dpg.add_text(f"{member.homaifar_score:.3f}")
                dpg.add_text(member.origin, color=COL_TEXT_DIM)

        move_items = [
            f"#{idx + 1}: {m.action} -> {m.child_after_mut} (Conf={m.child_conflicts})"
            for idx, m in enumerate(rec.logs)
        ]
        dpg.configure_item("combo_moves", items=move_items if move_items else ["Sin movimientos (Gen 0)"])
        if move_items:
            self.selected_move_idx = max(0, min(self.selected_move_idx, len(move_items) - 1))
            dpg.set_value("combo_moves", move_items[self.selected_move_idx])
        else:
            dpg.set_value("combo_moves", "Sin movimientos (Gen 0)")

        sol_items = [f"Sol #{i + 1}: {sol}" for i, sol in enumerate(self.solver.found_solutions)]
        dpg.configure_item(
            "listbox_solutions",
            items=sol_items if sol_items else ["Aún no se han hallado soluciones con 0 ataques"],
        )

        gens = [float(h.generation) for h in self.solver.history]
        best_c = [float(h.best.conflicts) for h in self.solver.history]
        avg_c = [float(h.avg_conflicts) for h in self.solver.history]
        dpg.set_value("series_best_conflicts", [gens, best_c])
        dpg.set_value("series_avg_conflicts", [gens, avg_c])
        dpg.fit_axis_data("axis_x_gen")
        dpg.fit_axis_data("axis_y_conf")

        self.render_board()
        self.render_genetic_operation_canvas()

    def on_select_individual(self, sender: int, app_data: bool, user_data: int) -> None:
        self.selected_ind_idx = user_data
        self.manual_swap_col = None
        self.refresh_ui()

    def on_select_move(self, sender: int, app_data: str) -> None:
        rec = self.current_record
        for idx, m in enumerate(rec.logs):
            label = f"#{idx + 1}: {m.action} -> {m.child_after_mut} (Conf={m.child_conflicts})"
            if label == app_data:
                self.selected_move_idx = idx
                for pop_idx, ind in enumerate(rec.population):
                    if ind.genes == m.child_after_mut:
                        self.selected_ind_idx = pop_idx
                        break
                break
        self.refresh_ui()

    def on_select_solution_hof(self, sender: int, app_data: str) -> None:
        for idx, sol in enumerate(self.solver.found_solutions):
            if app_data == f"Sol #{idx + 1}: {sol}":
                eval_sol = evaluate_individual(sol, origin="Hall of Fame (Solución Única)", parents_info=f"Solución #{idx + 1}")
                self.current_record.population[0] = eval_sol
                self.selected_ind_idx = 0
                self.manual_swap_col = None
                self.refresh_ui()
                break

    def on_load_book_n4_example(self) -> None:
        """Loads the exact N=4 example from the attached book figure: R = [2, 4, 1, 3]."""
        self.running = False
        dpg.configure_item("btn_play_pause", label="Iniciar Evolución")
        dpg.bind_item_theme("btn_play_pause", "btn_play_theme")

        dpg.set_value("input_n_queens", 4)
        self.solver.n = 4
        self.solver.reset()
        book_ind = evaluate_individual(
            [2, 4, 1, 3],
            origin="Ejemplo Libro (Cap. 3.5.2.5)",
            parents_info="Configuración figura N=4: [2, 4, 1, 3]",
        )
        self.solver.population[0] = book_ind
        self.solver.history[0].population[0] = book_ind
        self.solver.history[0].best = book_ind
        if [2, 4, 1, 3] not in self.solver.found_solutions:
            self.solver.found_solutions.insert(0, [2, 4, 1, 3])
        self.selected_gen_idx = 0
        self.selected_ind_idx = 0
        self.manual_swap_col = None
        self.refresh_ui()

    def on_load_8queens_preset(self) -> None:
        """Resets back to standard N=8 Queens problem."""
        dpg.set_value("input_n_queens", 8)
        self.on_reset_solver()

    def on_board_click(self, sender: int, app_data: tuple[int, ...]) -> None:
        mouse_x, mouse_y = dpg.get_drawing_mouse_pos()
        ind = self.current_individual
        n = ind.n
        margin = 32
        grid_px = self.board_canvas_size - 2 * margin
        cell = grid_px / n

        col_idx = int((mouse_x - margin) // cell)
        row_idx = int((mouse_y - margin) // cell)
        if 0 <= col_idx < n and 0 <= row_idx < n:
            target_row_1 = row_idx + 1
            genes = list(ind.genes)
            if genes[col_idx] == target_row_1:
                # Clicked directly on a queen: select/deselect this column for manual swap
                if self.manual_swap_col is None:
                    self.manual_swap_col = col_idx
                    self.refresh_ui()
                    return
                elif self.manual_swap_col == col_idx:
                    self.manual_swap_col = None
                    self.refresh_ui()
                    return
                else:
                    other_col = self.manual_swap_col
            else:
                # Clicked on another row in col_idx: swap col_idx with the column that currently has target_row_1
                other_col = genes.index(target_row_1)

            genes[col_idx], genes[other_col] = genes[other_col], genes[col_idx]
            swap_pair = (min(col_idx, other_col), max(col_idx, other_col))
            new_ind = evaluate_individual(
                genes,
                origin="Mutación Swap Manual (Tablero)",
                parents_info=f"Intercambio Col {col_idx + 1} <-> Col {other_col + 1}",
                mutation_swap=swap_pair,
            )
            self.current_record.population[self.selected_ind_idx] = new_ind
            if new_ind.is_solution and new_ind.genes not in self.solver.found_solutions:
                self.solver.found_solutions.append(list(new_ind.genes))
            self.manual_swap_col = None
            self.refresh_ui()

    def on_toggle_play(self) -> None:
        self.running = not self.running
        if self.running:
            dpg.configure_item("btn_play_pause", label="Pausar Evolución")
            dpg.bind_item_theme("btn_play_pause", "btn_pause_theme")
        else:
            dpg.configure_item("btn_play_pause", label="Iniciar Evolución")
            dpg.bind_item_theme("btn_play_pause", "btn_play_theme")

    def on_step_once(self) -> None:
        self.running = False
        dpg.configure_item("btn_play_pause", label="Iniciar Evolución")
        dpg.bind_item_theme("btn_play_pause", "btn_play_theme")
        self._advance_generation()

    def on_run_until_solution(self) -> None:
        self.running = False
        max_iters = 500
        for _ in range(max_iters):
            if self.solver.population[0].is_solution:
                break
            self.solver.step_generation()
        self.selected_gen_idx = len(self.solver.history) - 1
        self.selected_ind_idx = 0
        self.selected_move_idx = 0
        self.manual_swap_col = None
        self.refresh_ui()

    def _advance_generation(self) -> None:
        self.solver.step_generation()
        self.selected_gen_idx = len(self.solver.history) - 1
        self.selected_ind_idx = 0
        self.selected_move_idx = 0
        self.manual_swap_col = None
        if self.auto_stop_on_solution and self.solver.population[0].is_solution:
            self.running = False
            dpg.configure_item("btn_play_pause", label="Iniciar Evolución")
            dpg.bind_item_theme("btn_play_pause", "btn_play_theme")
        self.refresh_ui()

    def on_reset_solver(self) -> None:
        self.running = False
        dpg.configure_item("btn_play_pause", label="Iniciar Evolución")
        dpg.bind_item_theme("btn_play_pause", "btn_play_theme")

        self.solver.n = dpg.get_value("input_n_queens")
        self.solver.pop_size = dpg.get_value("input_pop_size")
        self.solver.crossover_rate = dpg.get_value("slider_crossover_rate")
        self.solver.mutation_rate = dpg.get_value("slider_mutation_rate")
        self.solver.tournament_k = dpg.get_value("input_tournament_k")
        self.solver.elitism_count = dpg.get_value("input_elitism")
        self.solver.fitness_mode = dpg.get_value("combo_fitness_mode")
        self.solver.crossover_mode = dpg.get_value("combo_crossover_mode")
        self.solver.selection_mode = dpg.get_value("combo_selection_mode")

        self.solver.reset()
        self.selected_gen_idx = 0
        self.selected_ind_idx = 0
        self.selected_move_idx = 0
        self.manual_swap_col = None
        self.refresh_ui()

    def on_param_live_change(self) -> None:
        self.solver.crossover_rate = dpg.get_value("slider_crossover_rate")
        self.solver.mutation_rate = dpg.get_value("slider_mutation_rate")
        self.solver.tournament_k = dpg.get_value("input_tournament_k")
        self.solver.elitism_count = dpg.get_value("input_elitism")
        self.solver.fitness_mode = dpg.get_value("combo_fitness_mode")
        self.solver.crossover_mode = dpg.get_value("combo_crossover_mode")
        self.solver.selection_mode = dpg.get_value("combo_selection_mode")
        self.steps_per_sec = dpg.get_value("slider_speed")
        self.auto_stop_on_solution = dpg.get_value("chk_auto_stop")
        self.show_conflict_lines = dpg.get_value("chk_show_conflicts")
        self.show_attack_diagonals = dpg.get_value("chk_show_diagonals")
        self.refresh_ui()

    def on_history_slider_change(self, sender: int, app_data: int) -> None:
        self.selected_gen_idx = int(app_data)
        self.selected_ind_idx = 0
        self.selected_move_idx = 0
        self.manual_swap_col = None
        self.refresh_ui()

    def build_gui(self) -> None:
        dpg.create_context()
        self.setup_themes()

        with dpg.window(tag="primary_window"):
            # Top Header & Telemetry Bar
            with dpg.child_window(height=48, border=True):
                with dpg.group(horizontal=True):
                    dpg.add_text("PROBLEMA DE LAS 8-REINAS (N-REINAS) — ALGORITMOS GENÉTICOS", color=COL_ACCENT)
                    dpg.add_spacer(width=18)
                    dpg.add_text("Generación Vista: 0 / 0", tag="lbl_gen_count")
                    dpg.add_spacer(width=16)
                    dpg.add_text("Mín. Conflictos [CRA92]: 0", tag="lbl_best_conflicts", color=COL_WARNING)
                    dpg.add_spacer(width=16)
                    dpg.add_text("Máx. Adaptación [HOM92]: 1.000", tag="lbl_best_homaifar", color=COL_SUCCESS)
                    dpg.add_spacer(width=16)
                    dpg.add_text("Soluciones Únicas: 0", tag="lbl_solutions_count", color=COL_SUCCESS)

            # Main 3-Column Layout
            with dpg.group(horizontal=True):
                # LEFT PANEL: Controls, GA Parameters & Theory
                with dpg.child_window(width=330, border=True):
                    dpg.add_text("1. CONTROL DE EVOLUCIÓN", color=COL_ACCENT)
                    dpg.add_separator()
                    with dpg.group(horizontal=True):
                        btn_play = dpg.add_button(
                            label="Iniciar Evolución",
                            tag="btn_play_pause",
                            width=152,
                            height=34,
                            callback=lambda: self.on_toggle_play(),
                        )
                        dpg.bind_item_theme(btn_play, "btn_play_theme")
                        dpg.add_button(
                            label="+1 Generación",
                            width=148,
                            height=34,
                            callback=lambda: self.on_step_once(),
                        )

                    with dpg.group(horizontal=True):
                        dpg.add_button(
                            label="Hallar Solución Ya",
                            width=152,
                            height=30,
                            callback=lambda: self.on_run_until_solution(),
                        )
                        btn_rst = dpg.add_button(
                            label="Reiniciar Población",
                            width=148,
                            height=30,
                            callback=lambda: self.on_reset_solver(),
                        )
                        dpg.bind_item_theme(btn_rst, "btn_reset_theme")

                    with dpg.group(horizontal=True):
                        dpg.add_button(
                            label="Tablero 8x8 (Estándar)",
                            width=152,
                            height=26,
                            callback=lambda: self.on_load_8queens_preset(),
                        )
                        dpg.add_button(
                            label="Fig. Libro N=4 [2,4,1,3]",
                            width=148,
                            height=26,
                            callback=lambda: self.on_load_book_n4_example(),
                        )

                    dpg.add_slider_float(
                        label="Velocidad",
                        tag="slider_speed",
                        default_value=12.0,
                        min_value=1.0,
                        max_value=60.0,
                        format="%.0f Gen/s",
                        width=195,
                        callback=lambda: self.on_param_live_change(),
                    )
                    dpg.add_checkbox(
                        label="Pausar al hallar solución (0 ataques)",
                        tag="chk_auto_stop",
                        default_value=True,
                        callback=lambda: self.on_param_live_change(),
                    )

                    dpg.add_spacer(height=4)
                    dpg.add_text("2. PARÁMETROS DEL ALGORITMO GENÉTICO", color=COL_ACCENT)
                    dpg.add_separator()
                    dpg.add_slider_int(
                        label="N Reinas (Tablero NxN)",
                        tag="input_n_queens",
                        default_value=8,
                        min_value=4,
                        max_value=16,
                        width=170,
                        callback=lambda: self.on_reset_solver(),
                    )
                    dpg.add_slider_int(
                        label="Tamaño Población",
                        tag="input_pop_size",
                        default_value=60,
                        min_value=10,
                        max_value=300,
                        width=170,
                        callback=lambda: self.on_reset_solver(),
                    )
                    dpg.add_combo(
                        label="Adaptación",
                        tag="combo_fitness_mode",
                        items=[
                            "Crawford [CRA92] (Penalización)",
                            "Homaifar [HOM92] (Recompensa)",
                        ],
                        default_value="Crawford [CRA92] (Penalización)",
                        width=200,
                        callback=lambda: self.on_param_live_change(),
                    )
                    dpg.add_combo(
                        label="Operador Cruce",
                        tag="combo_crossover_mode",
                        items=[
                            "OX (Orden)",
                            "PMX (Permutación)",
                            "Cruce 1-Punto + Reparación",
                            "Cruce 2-Puntos + Reparación",
                        ],
                        default_value="OX (Orden)",
                        width=200,
                        callback=lambda: self.on_param_live_change(),
                    )
                    dpg.add_combo(
                        label="Selección",
                        tag="combo_selection_mode",
                        items=["Torneo", "Ruleta / Proporcional"],
                        default_value="Torneo",
                        width=200,
                        callback=lambda: self.on_param_live_change(),
                    )
                    dpg.add_slider_float(
                        label="Prob. Cruce (Pc)",
                        tag="slider_crossover_rate",
                        default_value=0.35,
                        min_value=0.0,
                        max_value=1.0,
                        format="%.2f",
                        width=190,
                        callback=lambda: self.on_param_live_change(),
                    )
                    dpg.add_slider_float(
                        label="Prob. Mutación Swap",
                        tag="slider_mutation_rate",
                        default_value=0.65,
                        min_value=0.0,
                        max_value=1.0,
                        format="%.2f",
                        width=190,
                        callback=lambda: self.on_param_live_change(),
                    )
                    dpg.add_slider_int(
                        label="Torneo (K)",
                        tag="input_tournament_k",
                        default_value=3,
                        min_value=2,
                        max_value=10,
                        width=190,
                        callback=lambda: self.on_param_live_change(),
                    )
                    dpg.add_slider_int(
                        label="Elitismo",
                        tag="input_elitism",
                        default_value=2,
                        min_value=0,
                        max_value=10,
                        width=190,
                        callback=lambda: self.on_param_live_change(),
                    )

                    dpg.add_spacer(height=4)
                    dpg.add_text("3. CAPAS VISUALES Y RESTRICCIONES", color=COL_ACCENT)
                    dpg.add_separator()
                    dpg.add_checkbox(
                        label="Mostrar líneas rojas de ataque diagonal",
                        tag="chk_show_conflicts",
                        default_value=True,
                        callback=lambda: self.on_param_live_change(),
                    )
                    dpg.add_checkbox(
                        label="Mostrar rayos diagonales de las reinas",
                        tag="chk_show_diagonals",
                        default_value=False,
                        callback=lambda: self.on_param_live_change(),
                    )

                    dpg.add_spacer(height=4)
                    dpg.add_text("4. TEORÍA (CAP. 3.5.2.5 N-REINAS)", color=COL_ACCENT)
                    dpg.add_separator()
                    dpg.add_text(
                        "• Individuo: Vector R = [R_1..R_N] en {1..N}\n"
                        "  sin repeticiones (garantiza R_i != R_j).\n"
                        "• Posición i = columna, Valor R_i = fila.\n"
                        "• Restricción diagonal: |R_i - R_j| != |i - j|.\n"
                        "• Crawford [CRA92]: Cuenta conflictos diagonales,\n"
                        "  usa Pc bajo y mutación por intercambio (Swap).\n"
                        "• Homaifar [HOM92]: Suma 1/(2N) por cada\n"
                        "  diagonal libre de ataques (maximización).",
                        color=COL_TEXT_DIM,
                    )

                # CENTER PANEL: Interactive 8x8 / NxN Board + Chromosome Vector + Conflict Inspector
                with dpg.child_window(width=495, border=True):
                    dpg.add_text("Individuo #1", tag="lbl_board_status", color=COL_WARNING)
                    dpg.add_text("Origen: Población Inicial", tag="lbl_ind_origin", color=COL_TEXT_DIM)

                    with dpg.drawlist(width=self.board_canvas_size, height=self.board_canvas_size, tag="board_drawlist"):
                        pass

                    with dpg.item_handler_registry(tag="board_click_handler"):
                        dpg.add_item_clicked_handler(callback=self.on_board_click)
                    dpg.bind_item_handler_registry("board_drawlist", "board_click_handler")

                    dpg.add_text(
                        "Interactivo: Haz clic en cualquier casilla o en 2 reinas para aplicar un Swap entre columnas.",
                        color=COL_TEXT_DIM,
                    )

                    with dpg.drawlist(width=self.vec_canvas_width, height=self.vec_canvas_height, tag="vector_drawlist"):
                        pass

                    dpg.add_separator()
                    dpg.add_text(" Evaluación de Restricciones (|R_i - R_j| != |i - j|):", color=COL_ACCENT)
                    dpg.add_text("", tag="txt_conflict_details", color=(215, 222, 235, 255))

                # RIGHT PANEL: Generations Timeline, Population Table, Genetic Moves Inspector & Plots
                with dpg.child_window(width=-1, border=True):
                    dpg.add_text("HISTORIAL DE GENERACIONES", color=COL_ACCENT)
                    dpg.add_slider_int(
                        label="Explorar Gen",
                        tag="slider_history_gen",
                        default_value=0,
                        min_value=0,
                        max_value=0,
                        width=380,
                        callback=self.on_history_slider_change,
                    )

                    with dpg.tab_bar():
                        with dpg.tab(label="Población e Individuos"):
                            dpg.add_text(
                                "Selecciona cualquier individuo de la generación para ver su posición en el tablero:",
                                color=COL_TEXT_DIM,
                            )
                            with dpg.child_window(height=225, border=True):
                                with dpg.table(
                                    tag="table_population",
                                    header_row=True,
                                    row_background=True,
                                    borders_innerH=True,
                                    borders_outerH=True,
                                    borders_innerV=True,
                                    borders_outerV=True,
                                    resizable=True,
                                ):
                                    pass

                        with dpg.tab(label="Soluciones Halladas (0 Ataques)"):
                            dpg.add_text(
                                "Soluciones únicas sin conflictos encontradas durante la búsqueda:",
                                color=COL_TEXT_DIM,
                            )
                            dpg.add_listbox(
                                tag="listbox_solutions",
                                items=["Aún no se han hallado soluciones con 0 ataques"],
                                num_items=10,
                                width=-1,
                                callback=self.on_select_solution_hof,
                            )

                    dpg.add_spacer(height=4)
                    dpg.add_text("MOVIMIENTOS GENÉTICOS (CRUCE Y MUTACIÓN POR INTERCAMBIO)", color=COL_ACCENT)
                    dpg.add_combo(
                        label="Operación",
                        tag="combo_moves",
                        items=["Sin movimientos (Gen 0)"],
                        default_value="Sin movimientos (Gen 0)",
                        width=410,
                        callback=self.on_select_move,
                    )
                    with dpg.drawlist(width=self.op_canvas_width, height=self.op_canvas_height, tag="op_drawlist"):
                        pass

                    dpg.add_spacer(height=4)
                    dpg.add_text("CURVA DE CONVERGENCIA EVOLUTIVA", color=COL_ACCENT)
                    with dpg.plot(height=-1, width=-1, anti_aliased=True):
                        dpg.add_plot_legend()
                        dpg.add_plot_axis(dpg.mvXAxis, label="Generación", tag="axis_x_gen")
                        with dpg.plot_axis(dpg.mvYAxis, label="Conflictos [CRA92]", tag="axis_y_conf"):
                            dpg.add_line_series([], [], label="Mejor (Mín Conflictos)", tag="series_best_conflicts")
                            dpg.add_line_series([], [], label="Promedio Población", tag="series_avg_conflicts")

        dpg.create_viewport(
            title="Problema de las 8-Reinas (N-Reinas) — Algoritmos Genéticos [DearPyGui]",
            width=1420,
            height=900,
            min_width=1180,
            min_height=760,
        )
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("primary_window", True)
        self.refresh_ui()

    def run(self) -> None:
        self.build_gui()
        while dpg.is_dearpygui_running():
            if self.running:
                now = time.perf_counter()
                interval = 1.0 / max(0.5, self.steps_per_sec)
                if now - self.last_step_time >= interval:
                    self.last_step_time = now
                    self._advance_generation()
            dpg.render_dearpygui_frame()
        dpg.destroy_context()


def run_app() -> None:
    app = NQueensApp()
    app.run()
