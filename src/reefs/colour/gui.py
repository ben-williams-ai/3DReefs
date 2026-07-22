"""PySide6 GUI entrypoints and testable controller for colour restoration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from reefs.colour.filters import ColourParameterSet
from reefs.colour.interpolation import Keyframe, rebuild_keyframes
from reefs.colour.ordering import build_image_sequence
from reefs.colour.pipeline import apply_state_corrections, colour_state_path
from reefs.colour.profile import build_profile, save_profile
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
        found = False
        keyframes = []
        for keyframe in self.state.keyframes:
            if keyframe.id == keyframe_id:
                found = True
                keyframes.append(replace(keyframe, parameters=parameters, edited=True))
            else:
                keyframes.append(keyframe)
        if not found:
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


def skip_colour_confirmation_text() -> str:
    """Return confirmation text for intentionally skipping colour restoration."""
    return "This will close the GUI and progress the pipeline without colour correction. Are you sure?"


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
        f"{keyframe.list_index}. {keyframe.camera_group} | dataset {keyframe.global_position} | "
        f"camera {keyframe.camera_position}\n"
        f"path: {keyframe.relative_path.as_posix()}\n"
        f"{keyframe_saved_values_text(keyframe)}"
    )


@dataclass(frozen=True)
class ParameterControlSpec:
    """GUI slider bounds for one colour parameter."""

    minimum: float
    maximum: float
    step: float


PARAMETER_CONTROL_SPECS: dict[str, ParameterControlSpec] = {
    "gray_world": ParameterControlSpec(0.0, 1.0, 0.001),
    "warmth": ParameterControlSpec(-4.0, 4.0, 0.001),
    "tint": ParameterControlSpec(-4.0, 4.0, 0.001),
    "saturation": ParameterControlSpec(0.0, 3.0, 0.001),
    "blue_reduction": ParameterControlSpec(0.0, 1.0, 0.001),
    "brightness": ParameterControlSpec(-1.0, 1.0, 0.001),
    "contrast": ParameterControlSpec(-1.0, 1.0, 0.001),
    "shadows": ParameterControlSpec(0.0, 1.0, 0.001),
    "blacks": ParameterControlSpec(0.0, 1.0, 0.001),
    "highlights": ParameterControlSpec(0.0, 1.0, 0.001),
    "dehaze_strength": ParameterControlSpec(0.0, 1.0, 0.001),
    "dehaze_omega": ParameterControlSpec(0.1, 1.0, 0.001),
}


def keyframe_row_style(*, edited: bool, selected: bool) -> str:
    """Return stylesheet for a keyframe row."""
    background = "#bfe8c3" if edited else "#ffffff"
    if selected:
        background = "#8fd99b" if edited else "#e8f0ff"
    return (
        f"QWidget {{ background: {background}; border: 1px solid #9aa0a6; }}"
        "QWidget:hover { border: 1px solid #3b73d9; }"
    )


def launch_colour_gui(
    *,
    state: ColourRestorationState,
    run_dir: Path,
    start_sfm_immediately: bool = True,
    auto_close_ms: int | None = None,
    screenshot_path: Path | None = None,
    initial_size: tuple[int, int] | None = None,
    profile_output: Path | None = None,
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
        QCheckBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QProgressDialog,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QSlider,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )

    SLIDER_SCALE = 1000

    class ColourWindow(QMainWindow):
        """Thin Qt widget layer over `ColourGuiController`."""

        def __init__(self, controller: ColourGuiController):
            super().__init__()
            self.controller = controller
            self.sequence = build_image_sequence(controller.state.source_raw_root)
            self.current_index = 0
            self.current_keyframe_id: str | None = None
            self.parameter_sliders: dict[str, QSlider] = {}
            self.parameter_text_inputs: dict[str, QLineEdit] = {}
            self.raw_preview = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
            self.corrected_preview = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
            self.keyframe_list = QListWidget()
            self.keyframe_index_input = QSpinBox()
            self.image_index_input = QSpinBox()
            self.mode_input = QCheckBox("Edit separately by camera")
            self.count_input = QSpinBox()
            self.status_label = QLabel()
            self.previous_button = QPushButton("<")
            self.next_button = QPushButton(">")
            self._closing_after_action = False
            self.setWindowTitle("3DReefs Colour Restoration")
            self.resize(1280, 820)
            self.setMinimumSize(980, 680)
            self._build_ui()
            self.controller.set_active(True)
            if not self.controller.state.keyframes:
                self.controller.rebuild()
            self._refresh_keyframes()
            initial_keyframe = self._initial_keyframe()
            self._select_keyframe(initial_keyframe.id if initial_keyframe else None)

        def _build_ui(self) -> None:
            central = QWidget()
            outer = QVBoxLayout(central)

            content_splitter = QSplitter()
            content_splitter.addWidget(self._build_controls_panel())
            content_splitter.addWidget(self._build_preview_panel())
            content_splitter.setStretchFactor(0, 0)
            content_splitter.setStretchFactor(1, 1)
            content_splitter.setSizes([380, 1100])
            outer.addWidget(content_splitter, 4)

            self.keyframe_list.setMinimumHeight(170)
            self.keyframe_list.setAlternatingRowColors(False)
            self.keyframe_list.itemClicked.connect(self._select_keyframe_item)
            outer.addWidget(self.keyframe_list, 1)
            self.setCentralWidget(central)

        def _build_controls_panel(self) -> QWidget:
            panel = QWidget()
            panel.setMaximumWidth(430)
            panel.setMinimumWidth(340)
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(8, 8, 8, 8)

            keyframe_controls = QGridLayout()
            self.count_input.setRange(1, max(1, len(self.sequence.items)))
            self.count_input.setValue(self.controller.state.keyframe_count)
            rebuild_button = QPushButton("Apply")
            rebuild_button.clicked.connect(self._rebuild_keyframes)
            self.mode_input.setChecked(self.controller.state.mode == "per_camera")
            self.mode_input.clicked.connect(self._rebuild_keyframes)
            keyframe_controls.addWidget(QLabel("Keyframes"), 0, 0)
            keyframe_controls.addWidget(self.count_input, 0, 1)
            keyframe_controls.addWidget(rebuild_button, 0, 2)
            keyframe_controls.addWidget(self.mode_input, 1, 0, 1, 3)
            layout.addLayout(keyframe_controls)

            form_widget = QWidget()
            form = QGridLayout(form_widget)
            form.setColumnStretch(1, 1)
            form.setContentsMargins(0, 8, 0, 8)
            form.setHorizontalSpacing(8)
            form.setVerticalSpacing(6)
            for field, default in ColourParameterSet().as_dict().items():
                row = form.rowCount()
                spec = PARAMETER_CONTROL_SPECS[field]
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(self._slider_value(spec.minimum), self._slider_value(spec.maximum))
                slider.setSingleStep(max(1, self._slider_value(spec.step)))
                slider.setPageStep(max(1, self._slider_value(spec.step * 10)))
                slider.setTracking(True)
                slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                slider.setValue(self._slider_value(default))
                text_input = QLineEdit(f"{float(default):.4f}")
                text_input.setFixedWidth(76)
                apply_button = QPushButton("Apply")
                apply_button.setFixedWidth(58)
                slider.valueChanged.connect(lambda value, name=field: self._slider_changed(name, value))
                text_input.returnPressed.connect(lambda name=field: self._typed_parameter_applied(name))
                apply_button.clicked.connect(lambda _checked=False, name=field: self._typed_parameter_applied(name))
                self.parameter_sliders[field] = slider
                self.parameter_text_inputs[field] = text_input
                form.addWidget(QLabel(field), row, 0)
                form.addWidget(slider, row, 1)
                form.addWidget(text_input, row, 2)
                form.addWidget(apply_button, row, 3)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(form_widget)
            layout.addWidget(scroll, 1)

            actions = QGridLayout()
            save_button = QPushButton("Save edit")
            delete_button = QPushButton("Delete keyframe")
            save_button.clicked.connect(self._save_edit)
            delete_button.clicked.connect(self._delete_keyframe)
            for position, button in enumerate([save_button, delete_button]):
                actions.addWidget(button, position // 2, position % 2)
            layout.addLayout(actions)

            navigation = QGridLayout()
            self.keyframe_index_input.setRange(1, max(1, len(self.controller.state.keyframes)))
            jump_button = QPushButton("Jump to keyframe")
            jump_button.clicked.connect(lambda: self._select_keyframe_by_list_index(self.keyframe_index_input.value()))
            self.previous_button.clicked.connect(self._previous_keyframe)
            self.next_button.clicked.connect(self._next_keyframe)
            navigation.addWidget(QLabel("Keyframe index"), 0, 0)
            navigation.addWidget(self.keyframe_index_input, 0, 1)
            navigation.addWidget(jump_button, 0, 2)
            navigation.addWidget(self.previous_button, 1, 1)
            navigation.addWidget(self.next_button, 1, 2)
            layout.addLayout(navigation)
            return panel

        def _build_preview_panel(self) -> QWidget:
            panel = QWidget()
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(8, 8, 8, 8)
            previews = QHBoxLayout()
            previews.setSpacing(8)
            for label, preview in [("Raw", self.raw_preview), ("Corrected preview", self.corrected_preview)]:
                box = QGroupBox(label)
                box_layout = QVBoxLayout(box)
                preview.setMinimumSize(360, 360)
                preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
                preview.setFrameShape(QFrame.Shape.NoFrame)
                preview.setStyleSheet("background: #202020; color: white;")
                box_layout.addWidget(preview, 1)
                previews.addWidget(box, 1)
            layout.addLayout(previews, 1)
            image_jump = QHBoxLayout()
            self.image_index_input.setRange(1, max(1, len(self.sequence.items)))
            image_jump_button = QPushButton("Preview image")
            image_jump_button.clicked.connect(lambda: self._show_image(self.image_index_input.value() - 1, load_parameters=False))
            skip_button = QPushButton("Skip and close")
            apply_button = QPushButton("Apply colour correction to full dataset")
            skip_button.clicked.connect(self._confirm_skip_colour)
            apply_button.clicked.connect(self._apply)
            image_jump.addWidget(QLabel("Dataset image"))
            image_jump.addWidget(self.image_index_input)
            image_jump.addWidget(image_jump_button)
            image_jump.addStretch(1)
            image_jump.addWidget(skip_button)
            image_jump.addWidget(apply_button)
            layout.addLayout(image_jump)
            layout.addWidget(self.status_label)
            return panel

        def _current_item(self):
            return self.sequence.items[self.current_index]

        def _current_parameters(self) -> ColourParameterSet:
            values = {field: self._parameter_value(field) for field in self.parameter_sliders}
            return ColourParameterSet(**values)

        def _initial_keyframe(self) -> Keyframe | None:
            if not self.controller.state.keyframes:
                return None
            current_id = self.controller.state.current_keyframe_id
            for keyframe in self.controller.state.keyframes:
                if keyframe.id == current_id:
                    return keyframe
            return self.controller.state.keyframes[0]

        def _slider_value(self, value: float) -> int:
            return int(round(value * SLIDER_SCALE))

        def _parameter_value(self, field: str) -> float:
            return self.parameter_sliders[field].value() / SLIDER_SCALE

        def _slider_changed(self, field: str, value: int) -> None:
            self.parameter_text_inputs[field].setText(f"{value / SLIDER_SCALE:.4f}")
            self._refresh_corrected_preview()

        def _typed_parameter_applied(self, field: str) -> None:
            text_input = self.parameter_text_inputs[field]
            try:
                value = float(text_input.text())
            except ValueError:
                QMessageBox.warning(self, "Invalid value", f"{field} must be numeric.")
                text_input.setText(f"{self._parameter_value(field):.4f}")
                return
            spec = PARAMETER_CONTROL_SPECS[field]
            value = min(spec.maximum, max(spec.minimum, value))
            self._set_parameter(field, value, refresh=True)

        def _set_parameter(self, field: str, value: float, *, refresh: bool) -> None:
            slider = self.parameter_sliders[field]
            slider.blockSignals(True)
            slider.setValue(self._slider_value(value))
            slider.blockSignals(False)
            self.parameter_text_inputs[field].setText(f"{value:.4f}")
            if refresh:
                self._refresh_corrected_preview()

        def _set_parameters(self, parameters: ColourParameterSet) -> None:
            for field, value in parameters.as_dict().items():
                self._set_parameter(field, float(value), refresh=False)
            self._refresh_corrected_preview()

        def _refresh_keyframes(self) -> None:
            was_blocked = self.keyframe_list.blockSignals(True)
            self.keyframe_list.clear()
            self.keyframe_index_input.setRange(1, max(1, len(self.controller.state.keyframes)))
            for keyframe in self.controller.state.keyframes:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, keyframe.id)
                self.keyframe_list.addItem(item)
                row = self._build_keyframe_row(keyframe)
                item.setSizeHint(row.sizeHint())
                self.keyframe_list.setItemWidget(item, row)
                if keyframe.id == self.current_keyframe_id:
                    self.keyframe_list.setCurrentItem(item)
            self.keyframe_list.blockSignals(was_blocked)

        def _build_keyframe_row(self, keyframe):
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(4, 4, 4, 4)
            row.setStyleSheet(keyframe_row_style(edited=keyframe.edited, selected=keyframe.id == self.current_keyframe_id))
            thumbnail = QLabel()
            thumbnail.setFixedSize(72, 54)
            thumbnail.setStyleSheet("background: #222; color: white;")
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
            layout.addWidget(summary, 1)
            layout.addWidget(delete_button)
            layout.addWidget(thumbnail)
            return row

        def _show_image(self, index: int, *, load_parameters: bool = True) -> None:
            self.current_index = index
            self.image_index_input.blockSignals(True)
            self.image_index_input.setValue(index + 1)
            self.image_index_input.blockSignals(False)
            item = self._current_item()
            raw_path = self.controller.state.source_raw_root / item.relative_path
            pixmap = QPixmap(str(raw_path))
            if pixmap.isNull():
                self.raw_preview.setText(f"Cannot load {item.relative_path.as_posix()}")
            else:
                self._set_preview_pixmap(self.raw_preview, pixmap)
            self.status_label.setText(
                f"{item.relative_path.as_posix()} | global {item.global_index + 1}/{len(self.sequence.items)} | "
                f"{item.camera_group} {item.camera_index + 1}"
            )
            if load_parameters:
                keyframe = self._selected_keyframe()
                self._set_parameters(keyframe.parameters if keyframe and keyframe.parameters else ColourParameterSet())
            else:
                self._refresh_corrected_preview()

        def _set_preview_pixmap(self, label: QLabel, pixmap: QPixmap) -> None:
            label.setPixmap(
                pixmap.scaled(
                    label.contentsRect().size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        def _selected_keyframe(self) -> Keyframe | None:
            for keyframe in self.controller.state.keyframes:
                if keyframe.id == self.current_keyframe_id:
                    return keyframe
            return None

        def _select_keyframe_by_list_index(self, list_index: int) -> None:
            for keyframe in self.controller.state.keyframes:
                if keyframe.list_index == list_index:
                    self._select_keyframe(keyframe.id)
                    return

        def _select_keyframe(self, keyframe_id: str | None) -> None:
            if keyframe_id is None:
                return
            target = self._keyframe_by_id(keyframe_id)
            if target is None:
                return
            if keyframe_id != self.current_keyframe_id:
                self._save_current_keyframe_edit(refresh=False)
                target = self._keyframe_by_id(keyframe_id)
                if target is None:
                    return
            self.current_keyframe_id = target.id
            self.keyframe_index_input.blockSignals(True)
            self.keyframe_index_input.setValue(target.list_index)
            self.keyframe_index_input.blockSignals(False)
            self.controller.state = replace(self.controller.state, current_keyframe_id=target.id)
            save_state(self.controller.state_path, self.controller.state)
            self._show_image(target.global_position - 1)
            self._refresh_keyframes()
            self._update_navigation_buttons()

        def _keyframe_by_id(self, keyframe_id: str) -> Keyframe | None:
            for keyframe in self.controller.state.keyframes:
                if keyframe.id == keyframe_id:
                    return keyframe
            return None

        def _current_keyframe_position(self) -> int:
            keyframes = self.controller.state.keyframes
            for index, keyframe in enumerate(keyframes):
                if keyframe.id == self.current_keyframe_id:
                    return index
            return 0

        def _previous_keyframe(self) -> None:
            position = max(0, self._current_keyframe_position() - 1)
            self._select_keyframe(self.controller.state.keyframes[position].id)

        def _next_keyframe(self) -> None:
            position = min(len(self.controller.state.keyframes) - 1, self._current_keyframe_position() + 1)
            self._select_keyframe(self.controller.state.keyframes[position].id)

        def _update_navigation_buttons(self) -> None:
            if not self.controller.state.keyframes:
                self.previous_button.setEnabled(False)
                self.next_button.setEnabled(False)
                return
            position = self._current_keyframe_position()
            self.previous_button.setEnabled(position > 0)
            self.next_button.setEnabled(position < len(self.controller.state.keyframes) - 1)
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
                self._set_preview_pixmap(self.corrected_preview, pixmap)
            except Exception as exc:
                self.corrected_preview.setText(f"Preview failed: {exc}")

        def _save_edit(self) -> None:
            keyframe = self._selected_keyframe()
            if keyframe is None:
                QMessageBox.warning(self, "No keyframe selected", "Select a keyframe before saving an edit.")
                return
            self._save_current_keyframe_edit(keyframe, refresh=True)

        def _save_current_keyframe_edit(self, keyframe: Keyframe | None = None, *, refresh: bool = False) -> None:
            keyframe = keyframe or self._selected_keyframe()
            if keyframe is None:
                return
            self.controller.save_edit(keyframe.id, self._current_parameters())
            self.current_keyframe_id = keyframe.id
            if refresh:
                self._refresh_keyframes()

        def _delete_keyframe(self) -> None:
            keyframe = self._selected_keyframe()
            if keyframe is None:
                return
            self._delete_keyframe_by_id(keyframe.id)

        def _delete_keyframe_by_id(self, keyframe_id: str) -> None:
            if QMessageBox.question(self, "Remove keyframe?", "Remove keyframe?") == QMessageBox.StandardButton.Yes:
                self.controller.delete_keyframe(keyframe_id, confirmed=True)
                self.current_keyframe_id = self.controller.state.keyframes[0].id if self.controller.state.keyframes else None
                self._refresh_keyframes()
                self._select_keyframe(self.current_keyframe_id)

        def _rebuild_keyframes(self) -> None:
            mode = "per_camera" if self.mode_input.isChecked() else "global"
            self.controller.rebuild(keyframe_count=self.count_input.value(), mode=mode)
            self.sequence = build_image_sequence(self.controller.state.source_raw_root)
            self._refresh_keyframes()
            initial_keyframe = self._initial_keyframe()
            self._select_keyframe(initial_keyframe.id if initial_keyframe else None)

        def _select_keyframe_item(self, item: QListWidgetItem) -> None:
            self._select_keyframe(item.data(Qt.ItemDataRole.UserRole))

        def _apply(self) -> None:
            self._save_current_keyframe_edit(refresh=False)
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
            if profile_output is not None:
                try:
                    save_profile(
                        profile_output,
                        build_profile(
                            raw_images=self.controller.state.source_raw_root,
                            mode=self.controller.state.mode,
                            keyframes=self.controller.state.keyframes,
                        ),
                    )
                except Exception as exc:
                    QMessageBox.critical(self, "Profile save failed", str(exc))
                    return
                self.controller._persist(
                    self.controller.state.with_status(ColourStatus.COMPLETE, active_session=False)
                )
                QMessageBox.information(self, "Colour profile saved", str(profile_output))
                self._closing_after_action = True
                self.close()
                return
            progress = QProgressDialog("Applying colour restoration...", "Cancel", 0, len(self.sequence.items), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)

            def _progress(index: int, total: int, relative_path: Path) -> None:
                progress.setMaximum(total)
                progress.setValue(index)
                progress.setLabelText(f"{index} / {total} images\n{relative_path.as_posix()}")
                QApplication.processEvents()

            try:
                self.controller.state = apply_state_corrections(
                    state=self.controller.state,
                    run_dir=self.controller.run_dir,
                    overwrite_existing=True,
                    progress=_progress,
                )
            except Exception as exc:
                QMessageBox.critical(self, "Apply failed", str(exc))
                return
            progress.setValue(len(self.sequence.items))
            QMessageBox.information(
                self,
                "Colour restoration complete",
                completion_message(start_sfm_immediately=start_sfm_immediately),
            )
            self._closing_after_action = True
            self.close()

        def _confirm_skip_colour(self) -> None:
            if (
                QMessageBox.question(self, "Skip colour restoration?", skip_colour_confirmation_text())
                != QMessageBox.StandardButton.Yes
            ):
                return
            self._close_with_choice("skip")

        def _close_with_choice(self, choice: str) -> None:
            self.controller.close(choice)
            self._closing_after_action = True
            self.close()

        def closeEvent(self, event) -> None:  # noqa: N802 - Qt override.
            if self._closing_after_action or self.controller.state.status in {
                ColourStatus.COMPLETE,
                ColourStatus.SKIPPED,
                ColourStatus.CANCELLED,
            }:
                if self.controller.state.active_session:
                    self.controller.set_active(False)
                event.accept()
                return
            message = QMessageBox(self)
            message.setWindowTitle("Colour restoration incomplete")
            message.setText("Colour restoration is incomplete, are you sure you want to exit?")
            cancel_job = message.addButton(close_choices()[0], QMessageBox.ButtonRole.DestructiveRole)
            skip_colour = message.addButton(close_choices()[1], QMessageBox.ButtonRole.AcceptRole)
            continue_editing = message.addButton(close_choices()[2], QMessageBox.ButtonRole.RejectRole)
            message.exec()
            clicked = message.clickedButton()
            if clicked == continue_editing:
                event.ignore()
                return
            if clicked == skip_colour:
                self.controller.close("skip")
            elif clicked == cancel_job:
                self.controller.close("cancel")
            if self.controller.state.active_session:
                self.controller.set_active(False)
            event.accept()

        def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override.
            super().resizeEvent(event)
            QTimer.singleShot(0, lambda: self._show_image(self.current_index, load_parameters=False))

    app = QApplication.instance() or QApplication([])
    window = ColourWindow(ColourGuiController(state=state, run_dir=run_dir))
    if initial_size is not None:
        window.resize(*initial_size)
    window.show()
    if screenshot_path is not None:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        QTimer.singleShot(100, lambda: window.grab().save(str(screenshot_path)))
    if auto_close_ms is not None:
        QTimer.singleShot(auto_close_ms, lambda: (setattr(window, "_closing_after_action", True), window.close()))
    return int(app.exec())


def completion_message(*, start_sfm_immediately: bool) -> str:
    """Return completion text for the GUI after apply."""
    if start_sfm_immediately:
        return "Colour restoration is complete. SfM may already be running; splatting can continue once handoff checks pass."
    return "Colour restoration is complete. SfM can start from the saved run state."
