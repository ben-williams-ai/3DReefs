"""PySide6 GUI entrypoints and testable controller for colour restoration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from reefs.colour.filters import ColourParameterSet
from reefs.colour.interpolation import Keyframe, rebuild_keyframes
from reefs.colour.ordering import build_image_sequence
from reefs.colour.pipeline import apply_state_corrections, colour_state_path
from reefs.colour.state import ColourRestorationState, ColourStatus, save_state


class ColourGuiController:
    """State-changing operations used by the colour GUI."""

    def __init__(self, *, state: ColourRestorationState, run_dir: Path):
        self.state = state
        self.run_dir = run_dir
        self.state_path = colour_state_path(run_dir)

    def _persist(self, state: ColourRestorationState) -> ColourRestorationState:
        self.state = state
        save_state(self.state_path, state)
        return state

    def set_active(self, active: bool) -> ColourRestorationState:
        """Mark the GUI session active or inactive."""
        status = ColourStatus.ACTIVE if active else self.state.status
        return self._persist(self.state.with_status(status, active_session=active))

    def rebuild(self, *, keyframe_count: int | None = None, mode: str | None = None) -> ColourRestorationState:
        """Rebuild keyframes while preserving valid edits."""
        sequence = build_image_sequence(self.state.source_raw_root)
        count = keyframe_count or self.state.keyframe_count
        chosen_mode = mode or self.state.mode
        keyframes = rebuild_keyframes(
            sequence,
            count=count,
            existing=self.state.keyframes,
            per_camera=chosen_mode == "per_camera",
        )
        return self._persist(
            replace(
                self.state,
                keyframes=keyframes,
                keyframe_count=count,
                mode=chosen_mode,
            ).with_status(ColourStatus.ACTIVE, active_session=True)
        )

    def save_edit(self, keyframe_id: str, parameters: ColourParameterSet) -> ColourRestorationState:
        """Save or overwrite one keyframe edit."""
        keyframes = [
            replace(keyframe, parameters=parameters, edited=True)
            if keyframe.id == keyframe_id
            else keyframe
            for keyframe in self.state.keyframes
        ]
        if keyframes == self.state.keyframes:
            raise ValueError(f"Unknown keyframe: {keyframe_id}")
        return self._persist(replace(self.state, keyframes=keyframes).with_status(ColourStatus.ACTIVE, active_session=True))

    def delete_keyframe(self, keyframe_id: str, *, confirmed: bool) -> ColourRestorationState:
        """Delete a keyframe after confirmation."""
        if not confirmed:
            raise ValueError("Keyframe deletion requires confirmation")
        keyframes = [keyframe for keyframe in self.state.keyframes if keyframe.id != keyframe_id]
        keyframes = [replace(keyframe, list_index=index) for index, keyframe in enumerate(keyframes, start=1)]
        return self._persist(replace(self.state, keyframes=keyframes).with_status(ColourStatus.ACTIVE, active_session=True))

    def close(self, choice: str) -> ColourRestorationState:
        """Apply the user's close choice."""
        if choice == "cancel":
            return self._persist(self.state.with_status(ColourStatus.CANCELLED, active_session=False))
        if choice == "skip":
            return self._persist(self.state.with_status(ColourStatus.SKIPPED, active_session=False))
        if choice == "continue":
            return self._persist(self.state.with_status(ColourStatus.ACTIVE, active_session=True))
        raise ValueError(f"Unknown close choice: {choice}")

    def apply(self) -> ColourRestorationState:
        """Apply full-dataset correction from saved edits."""
        return self._persist(
            apply_state_corrections(state=self.state, run_dir=self.run_dir, overwrite_existing=True)
        )


def apply_confirmation_text(*, total_keyframes: int, edited_keyframes: int, total_images: int) -> str:
    """Return apply confirmation text for the current keyframe state."""
    unedited = total_keyframes - edited_keyframes
    if unedited > 0:
        return (
            f"You have not corrected {unedited} keyframes. Are you sure you want to finish "
            f"and apply colour correction to all {total_images} images in the dataset using "
            f"the {edited_keyframes} edited keyframes?"
        )
    return f"Ready to colour correct all {total_images} images, proceed?"


def close_choices() -> tuple[str, str, str]:
    """Return the required close choices."""
    return (
        "Yes, and cancel job",
        "Yes, progress to SfM without colour restoration",
        "No, continue applying colour restoration",
    )


def overwrite_warning_text() -> str:
    """Return the required overwrite warning text."""
    return "Reapplying colour restoration will overwrite the current corrected version."


def keyframe_saved_values_text(keyframe: Keyframe) -> str:
    """Return a compact saved-value summary for a keyframe row."""
    if not keyframe.edited or keyframe.parameters is None:
        return "unedited"
    values = keyframe.parameters.as_dict()
    changed = [
        f"{name}={value:g}"
        for name, value in values.items()
        if value != getattr(ColourParameterSet(), name)
    ]
    if not changed:
        return "edited: neutral"
    return "edited: " + ", ".join(changed[:4]) + ("..." if len(changed) > 4 else "")


def keyframe_row_summary(keyframe: Keyframe) -> str:
    """Return the text context shown in the keyframe list."""
    return (
        f"{keyframe.list_index}. {keyframe.relative_path.name}\n"
        f"camera: {keyframe.camera_group} | dataset: {keyframe.global_position} | "
        f"camera pos: {keyframe.camera_position}\n"
        f"path: {keyframe.relative_path.as_posix()}\n"
        f"{keyframe_saved_values_text(keyframe)}"
    )


def launch_colour_gui(
    *,
    state: ColourRestorationState,
    run_dir: Path,
    start_sfm_immediately: bool = True,
    auto_close_ms: int | None = None,
    screenshot_path: Path | None = None,
    initial_size: tuple[int, int] | None = None,
) -> int:
    """Launch a small PySide6 colour restoration GUI.

    The heavy image processing remains in the controller/pipeline modules; this
    window provides resumable edits, previews, navigation, mode controls, and
    apply/close prompts.
    """
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDoubleSpinBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )

    class ColourWindow(QMainWindow):
        """Thin Qt widget layer over `ColourGuiController`."""

        def __init__(self, controller: ColourGuiController):
            super().__init__()
            self.controller = controller
            self.sequence = build_image_sequence(controller.state.source_raw_root)
            self.current_index = 0
            self.parameter_inputs: dict[str, QDoubleSpinBox] = {}
            self.raw_preview = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
            self.corrected_preview = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
            self.keyframe_list = QListWidget()
            self.keyframe_list.setMinimumWidth(360)
            self.index_input = QSpinBox()
            self.mode_input = QComboBox()
            self.count_input = QSpinBox()
            self.status_label = QLabel()
            self.setWindowTitle("3DReefs Colour Restoration")
            self.resize(1180, 760)
            self.setMinimumSize(920, 600)
            self._build_ui()
            self.controller.set_active(True)
            if not self.controller.state.keyframes:
                self.controller.rebuild()
            self._refresh_keyframes()
            self._show_image(0)

        def _build_ui(self) -> None:
            central = QWidget()
            outer = QVBoxLayout(central)

            top = QHBoxLayout()
            previous_button = QPushButton("Previous")
            next_button = QPushButton("Next")
            previous_button.clicked.connect(lambda: self._show_image(max(0, self.current_index - 1)))
            next_button.clicked.connect(lambda: self._show_image(min(len(self.sequence.items) - 1, self.current_index + 1)))
            self.index_input.setRange(1, max(1, len(self.sequence.items)))
            self.index_input.valueChanged.connect(lambda value: self._show_image(value - 1))
            self.mode_input.addItems(["global", "per_camera"])
            self.mode_input.setCurrentText(self.controller.state.mode)
            self.count_input.setRange(1, max(1, len(self.sequence.items)))
            self.count_input.setValue(self.controller.state.keyframe_count)
            rebuild_button = QPushButton("Rebuild keyframes")
            rebuild_button.clicked.connect(self._rebuild_keyframes)
            top.addWidget(previous_button)
            top.addWidget(next_button)
            top.addWidget(QLabel("Image"))
            top.addWidget(self.index_input)
            top.addWidget(QLabel("Mode"))
            top.addWidget(self.mode_input)
            top.addWidget(QLabel("Keyframes"))
            top.addWidget(self.count_input)
            top.addWidget(rebuild_button)
            top.addStretch(1)
            outer.addLayout(top)

            splitter = QSplitter()
            preview_panel = QWidget()
            preview_layout = QVBoxLayout(preview_panel)
            preview_row = QHBoxLayout()
            for label, preview in [("Raw", self.raw_preview), ("Corrected preview", self.corrected_preview)]:
                box = QWidget()
                box_layout = QVBoxLayout(box)
                box_layout.addWidget(QLabel(label))
                preview.setMinimumSize(300, 260)
                preview.setStyleSheet("border: 1px solid #999; background: #222; color: white;")
                box_layout.addWidget(preview, 1)
                preview_row.addWidget(box, 1)
            preview_layout.addLayout(preview_row)
            preview_layout.addWidget(self.status_label)

            form_widget = QWidget()
            form = QFormLayout(form_widget)
            for field, default in ColourParameterSet().as_dict().items():
                control = QDoubleSpinBox()
                control.setDecimals(4)
                control.setRange(-10_000.0, 10_000.0)
                control.setSingleStep(0.05)
                control.setValue(float(default))
                control.valueChanged.connect(self._refresh_corrected_preview)
                self.parameter_inputs[field] = control
                form.addRow(field, control)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(form_widget)
            preview_layout.addWidget(scroll)

            actions = QHBoxLayout()
            save_button = QPushButton("Save edit")
            delete_button = QPushButton("Delete keyframe")
            apply_button = QPushButton("Apply to dataset")
            skip_button = QPushButton("Skip colour")
            cancel_button = QPushButton("Cancel")
            save_button.clicked.connect(self._save_edit)
            delete_button.clicked.connect(self._delete_keyframe)
            apply_button.clicked.connect(self._apply)
            skip_button.clicked.connect(lambda: self._close_with_choice("skip"))
            cancel_button.clicked.connect(lambda: self._close_with_choice("cancel"))
            for button in [save_button, delete_button, apply_button, skip_button, cancel_button]:
                actions.addWidget(button)
            preview_layout.addLayout(actions)

            self.keyframe_list.itemClicked.connect(self._select_keyframe_item)
            splitter.addWidget(preview_panel)
            splitter.addWidget(self.keyframe_list)
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 1)
            splitter.setSizes([760, 380])
            outer.addWidget(splitter, 1)
            self.setCentralWidget(central)

        def _current_item(self):
            return self.sequence.items[self.current_index]

        def _current_parameters(self) -> ColourParameterSet:
            values = {field: control.value() for field, control in self.parameter_inputs.items()}
            return ColourParameterSet(**values)

        def _refresh_keyframes(self) -> None:
            self.keyframe_list.clear()
            for keyframe in self.controller.state.keyframes:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, keyframe.id)
                self.keyframe_list.addItem(item)
                row = self._build_keyframe_row(keyframe)
                item.setSizeHint(row.sizeHint())
                self.keyframe_list.setItemWidget(item, row)

        def _build_keyframe_row(self, keyframe):
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(4, 4, 4, 4)
            thumbnail = QLabel()
            thumbnail.setFixedSize(72, 54)
            thumbnail.setStyleSheet("border: 1px solid #aaa; background: #222; color: white;")
            pixmap = QPixmap(str(self.controller.state.source_raw_root / keyframe.relative_path))
            if pixmap.isNull():
                thumbnail.setText("raw")
                thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                thumbnail.setPixmap(pixmap.scaled(thumbnail.size(), Qt.AspectRatioMode.KeepAspectRatio))
            summary = QLabel(keyframe_row_summary(keyframe))
            summary.setWordWrap(True)
            summary.setMinimumWidth(190)
            delete_button = QPushButton("Delete")
            delete_button.setFixedWidth(72)
            delete_button.clicked.connect(lambda _checked=False, keyframe_id=keyframe.id: self._delete_keyframe_by_id(keyframe_id))
            layout.addWidget(thumbnail)
            layout.addWidget(summary, 1)
            layout.addWidget(delete_button)
            return row

        def _show_image(self, index: int) -> None:
            self.current_index = index
            self.index_input.blockSignals(True)
            self.index_input.setValue(index + 1)
            self.index_input.blockSignals(False)
            item = self._current_item()
            raw_path = self.controller.state.source_raw_root / item.relative_path
            pixmap = QPixmap(str(raw_path))
            if pixmap.isNull():
                self.raw_preview.setText(f"Cannot load {item.relative_path.as_posix()}")
            else:
                self.raw_preview.setPixmap(pixmap.scaled(self.raw_preview.size(), Qt.AspectRatioMode.KeepAspectRatio))
            self.status_label.setText(
                f"{item.relative_path.as_posix()} | global {item.global_index + 1}/{len(self.sequence.items)} | "
                f"{item.camera_group} {item.camera_index + 1}"
            )
            for keyframe in self.controller.state.keyframes:
                if keyframe.relative_path == item.relative_path and keyframe.parameters:
                    for field, value in keyframe.parameters.as_dict().items():
                        self.parameter_inputs[field].blockSignals(True)
                        self.parameter_inputs[field].setValue(float(value))
                        self.parameter_inputs[field].blockSignals(False)
                    break
            self._refresh_corrected_preview()

        def _refresh_corrected_preview(self) -> None:
            from PIL.ImageQt import ImageQt

            try:
                from PIL import Image
                from reefs.colour.filters import apply_colour_filters

                item = self._current_item()
                with Image.open(self.controller.state.source_raw_root / item.relative_path) as image:
                    image.thumbnail((900, 700))
                    corrected = apply_colour_filters(image, self._current_parameters())
                qt_image = ImageQt(corrected)
                pixmap = QPixmap.fromImage(qt_image)
                self.corrected_preview.setPixmap(
                    pixmap.scaled(self.corrected_preview.size(), Qt.AspectRatioMode.KeepAspectRatio)
                )
            except Exception as exc:
                self.corrected_preview.setText(f"Preview failed: {exc}")

        def _keyframe_for_current_image(self):
            item = self._current_item()
            for keyframe in self.controller.state.keyframes:
                if keyframe.relative_path == item.relative_path:
                    return keyframe
            return None

        def _save_edit(self) -> None:
            keyframe = self._keyframe_for_current_image()
            if keyframe is None:
                QMessageBox.warning(self, "Not a keyframe", "Navigate to a listed keyframe before saving an edit.")
                return
            self.controller.save_edit(keyframe.id, self._current_parameters())
            self._refresh_keyframes()

        def _delete_keyframe(self) -> None:
            keyframe = self._keyframe_for_current_image()
            if keyframe is None:
                return
            self._delete_keyframe_by_id(keyframe.id)

        def _delete_keyframe_by_id(self, keyframe_id: str) -> None:
            if QMessageBox.question(self, "Delete keyframe", "Delete this saved keyframe?") == QMessageBox.StandardButton.Yes:
                self.controller.delete_keyframe(keyframe_id, confirmed=True)
                self._refresh_keyframes()

        def _rebuild_keyframes(self) -> None:
            self.controller.rebuild(keyframe_count=self.count_input.value(), mode=self.mode_input.currentText())
            self.sequence = build_image_sequence(self.controller.state.source_raw_root)
            self._refresh_keyframes()
            self._show_image(min(self.current_index, len(self.sequence.items) - 1))

        def _select_keyframe_item(self, item: QListWidgetItem) -> None:
            keyframe_id = item.data(Qt.ItemDataRole.UserRole)
            for keyframe in self.controller.state.keyframes:
                if keyframe.id == keyframe_id:
                    self._show_image(keyframe.global_position - 1)
                    return

        def _apply(self) -> None:
            edited = len([keyframe for keyframe in self.controller.state.keyframes if keyframe.edited])
            message = apply_confirmation_text(
                total_keyframes=len(self.controller.state.keyframes),
                edited_keyframes=edited,
                total_images=len(self.sequence.items),
            )
            if self.controller.state.output_recoloured_root.exists() and any(self.controller.state.output_recoloured_root.rglob("*")):
                message += "\n\n" + overwrite_warning_text()
            if QMessageBox.question(self, "Apply colour restoration", message) != QMessageBox.StandardButton.Yes:
                return
            try:
                self.controller.apply()
            except Exception as exc:
                QMessageBox.critical(self, "Apply failed", str(exc))
                return
            QMessageBox.information(
                self,
                "Colour restoration complete",
                completion_message(start_sfm_immediately=start_sfm_immediately),
            )
            self.close()

        def _close_with_choice(self, choice: str) -> None:
            self.controller.close(choice)
            self.close()

        def closeEvent(self, event) -> None:  # noqa: N802 - Qt override.
            if self.controller.state.active_session:
                self.controller.set_active(False)
            event.accept()

    app = QApplication.instance() or QApplication([])
    window = ColourWindow(ColourGuiController(state=state, run_dir=run_dir))
    if initial_size is not None:
        window.resize(*initial_size)
    window.show()
    if screenshot_path is not None:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        QTimer.singleShot(100, lambda: window.grab().save(str(screenshot_path)))
    if auto_close_ms is not None:
        QTimer.singleShot(auto_close_ms, window.close)
    return int(app.exec())


def completion_message(*, start_sfm_immediately: bool) -> str:
    """Return completion text for the GUI after apply."""
    if start_sfm_immediately:
        return "Colour restoration is complete. SfM may already be running; splatting can continue once handoff checks pass."
    return "Colour restoration is complete. SfM can start from the saved run state."
