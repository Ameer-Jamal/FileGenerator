"""Main application window for the File Generator."""

from __future__ import annotations

from pathlib import Path
from shutil import disk_usage
from typing import Iterable

try:
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import (
        QComboBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QToolButton,
        QDoubleSpinBox,
        QProgressBar,
        QPlainTextEdit,
        QSizePolicy,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("PyQt6 must be installed to run the GUI components.") from exc

from file_generator.services.generation_service import (
    FileGenerationRequest,
    GenerationService,
    create_default_service,
)
from file_generator.ui.workers import GenerationWorker
from file_generator.utils.rows import DefaultRowContentGenerator
from file_generator.utils.size_helpers import MIB, SizeConstraint, SizeValue


class MainWindow(QMainWindow):
    """PyQt6 main window responsible for coordinating user interactions."""

    # pylint: disable=too-many-instance-attributes,too-few-public-methods

    FILE_TYPES: tuple[tuple[str, str], ...] = (
        ("xlsx", "Excel Workbook (*.xlsx)"),
        ("xlsm", "Excel Macro-Enabled Workbook (*.xlsm)"),
        ("csv", "Comma-separated (*.csv)"),
        ("tsv", "Tab-delimited (*.tsv)"),
        ("txt", "Tab-delimited (*.txt)"),
    )

    def __init__(self, service: GenerationService | None = None) -> None:
        super().__init__()
        self.setWindowTitle("File Generator")
        self.resize(720, 540)

        self._service = service or create_default_service()
        self._settings = QSettings("FileGenerator", "GeneratorApp")
        self._worker: GenerationWorker | None = None
        self._cancel_flag = False

        self._setup_ui()
        self._connect_signals()
        self._register_setting_listeners()
        self._load_settings()

    def _setup_ui(self) -> None:  # pylint: disable=too-many-statements
        container = QWidget(self)
        layout = QFormLayout()
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        container.setLayout(layout)

        # Destination picker
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.browse_button = QPushButton("Browse…")
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_button)
        layout.addRow(QLabel("Output Path"), path_layout)

        # File type selector
        self.file_type_combo = QComboBox()
        for extension, description in self.FILE_TYPES:
            self.file_type_combo.addItem(description, extension)
        layout.addRow(QLabel("File Type"), self.file_type_combo)

        # Target size controls
        size_layout = QHBoxLayout()
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0.1, 100_000.0)
        self.size_spin.setValue(1024.0)
        self.size_spin.setDecimals(1)
        self.size_spin.setSuffix(" ")
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["MB", "GB"])
        size_layout.addWidget(self.size_spin)
        size_layout.addWidget(self.unit_combo)
        layout.addRow(QLabel("Target Size"), size_layout)

        # Header row input
        self.headers_input = QPlainTextEdit()
        self.headers_input.setPlaceholderText(
            "Comma-separated headers, e.g. CustomerId, AccountNumber, CreatedAt"
        )
        self.headers_input.setFixedHeight(70)
        self.headers_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addRow(QLabel("Header Row"), self.headers_input)

        # Filler text
        self.filler_input = QLineEdit("SampleValue")
        self.filler_input.setPlaceholderText("Prefix used to populate each generated cell value")
        self.filler_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.filler_help_button = QToolButton()
        self.filler_help_button.setText("?")
        self.filler_help_button.setAutoRaise(True)
        self.filler_help_button.setToolTip(
            "What is a filler token? Click to learn how row values are composed."
        )
        self.filler_help_button.clicked.connect(self._show_filler_help)

        filler_layout = QHBoxLayout()
        filler_layout.addWidget(self.filler_input)
        filler_layout.addWidget(self.filler_help_button)
        filler_layout.setStretch(0, 1)

        layout.addRow(QLabel("Filler Token"), filler_layout)

        # Estimates display
        self.estimate_label = QLabel("Estimates will appear once target size is set.")
        self.estimate_label.setWordWrap(True)
        layout.addRow(QLabel("Planning"), self.estimate_label)

        # Progress area
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addRow(QLabel("Progress"), self.progress_bar)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log_output.setFixedHeight(180)
        layout.addRow(QLabel("Activity Log"), self.log_output)

        # Action buttons
        button_layout = QHBoxLayout()
        self.generate_button = QPushButton("Generate")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.generate_button)
        button_layout.addWidget(self.cancel_button)
        layout.addRow(button_layout)

        self._input_widgets = [
            self.path_edit,
            self.browse_button,
            self.file_type_combo,
            self.size_spin,
            self.unit_combo,
            self.headers_input,
            self.filler_input,
            self.filler_help_button,
        ]

        self.setCentralWidget(container)

    def _connect_signals(self) -> None:
        self.browse_button.clicked.connect(self._browse_for_path)
        self.generate_button.clicked.connect(self._on_generate_clicked)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.file_type_combo.currentIndexChanged.connect(self._on_file_type_changed)

    def _on_file_type_changed(self) -> None:
        """Ensure the destination path matches the selected extension."""
        path_str = self.path_edit.text().strip()
        if not path_str:
            return
        current_path = Path(path_str)
        selected_extension = self.file_type_combo.currentData()
        if selected_extension is None:
            return
        suffix = f".{selected_extension}"
        if current_path.suffix.lower() != suffix:
            new_path = current_path.with_suffix(suffix)
            self.path_edit.setText(str(new_path))
        self._on_parameters_changed()

    def _browse_for_path(self) -> None:
        selected_extension = self.file_type_combo.currentData()
        filters = ";;".join(description for _, description in self.FILE_TYPES)
        suggested_path = self.path_edit.text().strip()
        if not suggested_path:
            suggested_path = str(Path.home() / f"generated_file.{selected_extension or 'xlsx'}")

        filename, _selected_filter = QFileDialog.getSaveFileName(
            self,
            caption="Select Output File",
            directory=suggested_path,
            filter=filters,
        )
        if filename:
            self.path_edit.setText(filename)
            self._on_parameters_changed()

    def _on_generate_clicked(self) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(
                self,
                "Generation in progress",
                "A generation job is already running.",
            )
            return

        self._cancel_flag = False
        try:
            request = self._build_request()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return

        self.log_output.clear()
        self._append_log("Starting generation...")
        self._set_running_state(True)

        self._worker = GenerationWorker(self._service, request, parent=self)
        self._worker.progress.connect(self._handle_progress)
        self._worker.finished_successfully.connect(self._handle_success)
        self._worker.cancelled.connect(self._handle_cancelled)
        self._worker.errored.connect(self._handle_error)
        self._worker.start()
        self._save_settings()

    def _on_cancel_clicked(self) -> None:
        if self._worker and self._worker.isRunning():
            self._append_log("Cancelling generation…")
            self._cancel_flag = True
            self._worker.request_cancel()
            self.cancel_button.setEnabled(False)

    def _build_request(self) -> FileGenerationRequest:
        path_str = self.path_edit.text().strip()
        if not path_str:
            raise ValueError("Please choose a destination file path.")

        destination = Path(path_str)
        selected_extension = self.file_type_combo.currentData()
        if selected_extension and destination.suffix.lower() != f".{selected_extension}":
            destination = destination.with_suffix(f".{selected_extension}")
            self.path_edit.setText(str(destination))

        headers_text = self.headers_input.toPlainText().strip()
        if not headers_text:
            raise ValueError("Provide at least one header value.")
        raw_headers = [segment.strip() for segment in self._split_header_input(headers_text)]
        headers = tuple(filter(None, raw_headers))
        if not headers:
            raise ValueError("Header values cannot be empty.")

        size_value = SizeValue(amount=self.size_spin.value(), unit=self.unit_combo.currentText())
        target_bytes = size_value.to_bytes()
        if target_bytes <= 0:
            raise ValueError("Target size must be greater than zero.")

        tolerance = max(int(target_bytes * 0.02), 5 * MIB)
        required_bytes = target_bytes + tolerance
        self._ensure_disk_space(destination, required_bytes)
        size_constraint = SizeConstraint(target_bytes=target_bytes, tolerance_bytes=tolerance)

        filler = self.filler_input.text().strip() or "SampleValue"
        row_generator = DefaultRowContentGenerator(filler_text=filler)

        return FileGenerationRequest(
            destination=destination,
            file_type=str(selected_extension or destination.suffix.lstrip(".")),
            headers=headers,
            row_generator=row_generator,
            size_constraint=size_constraint,
            cancel_requested=lambda: self._cancel_flag,
        )

    def _split_header_input(self, text: str) -> Iterable[str]:
        normalized = text.replace("\n", ",").replace("\t", ",")
        return normalized.split(",")

    def _set_running_state(self, running: bool) -> None:
        for widget in self._input_widgets:
            widget.setEnabled(not running)
        self.generate_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.progress_bar.setValue(0)
        if running:
            self.progress_bar.setRange(0, 0)  # Indeterminate until we receive progress
        else:
            self.progress_bar.setRange(0, 100)

    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _handle_progress(self, message: str, percent: float) -> None:
        self._append_log(message)
        if percent >= 0:
            if self.progress_bar.maximum() != 100:
                self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(min(percent, 100.0)))
        else:
            if self.progress_bar.maximum() != 0:
                self.progress_bar.setRange(0, 0)

    def _handle_success(self) -> None:
        self._append_log("Generation complete.")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._set_running_state(False)
        self._cancel_flag = False
        QMessageBox.information(self, "Success", "File generation completed successfully.")

    def _handle_cancelled(self) -> None:
        self._append_log("Generation cancelled.")
        self._set_running_state(False)
        self._cancel_flag = False
        QMessageBox.information(self, "Cancelled", "Generation was cancelled.")

    def _handle_error(self, message: str) -> None:
        self._append_log(f"Error: {message}")
        self._set_running_state(False)
        self._cancel_flag = False
        QMessageBox.critical(self, "Error", f"Failed to generate file:\n{message}")

    def _show_filler_help(self) -> None:
        """Explain how the filler token shapes generated cell values."""
        message_lines = [
            "Each generated cell combines the filler token, the column name, and a hashed suffix.",
            "",
            "For token 'LoadTest' and column 'CustomerId' you'll see values like",
            "`LoadTest-CustomerId-a1b2...`. Adjust the token to label or group your test data.",
        ]
        QMessageBox.information(self, "Filler Token", "\n".join(message_lines))

    def _on_parameters_changed(self, *_: object) -> None:
        """Persist inputs and update estimates when any parameter changes."""
        self._save_settings()
        self._update_estimates()

    def _register_setting_listeners(self) -> None:
        """Persist user inputs as they change so they survive app restarts."""
        self.path_edit.textChanged.connect(self._on_parameters_changed)
        self.headers_input.textChanged.connect(self._on_parameters_changed)
        self.filler_input.textChanged.connect(self._on_parameters_changed)
        self.size_spin.valueChanged.connect(self._on_parameters_changed)
        self.unit_combo.currentIndexChanged.connect(self._on_parameters_changed)

    def _load_settings(self) -> None:
        """Restore the last-used configuration from persistent storage."""
        self.path_edit.setText(self._settings.value("output_path", "", str))

        stored_type = self._settings.value("file_type", "", str)
        type_index = self.file_type_combo.findData(stored_type)
        if type_index >= 0:
            self.file_type_combo.setCurrentIndex(type_index)

        stored_size = self._settings.value("target_size", None, float)
        if stored_size is not None and stored_size > 0:
            self.size_spin.setValue(stored_size)

        stored_unit = self._settings.value("size_unit", "", str)
        unit_index = self.unit_combo.findText(stored_unit) if stored_unit else -1
        if unit_index >= 0:
            self.unit_combo.setCurrentIndex(unit_index)

        self.headers_input.setPlainText(self._settings.value("headers", "", str))
        self.filler_input.setText(self._settings.value("filler_token", "SampleValue", str))
        self._update_estimates()

    def _save_settings(self, *_: object) -> None:
        """Persist the current form values."""
        self._settings.setValue("output_path", self.path_edit.text().strip())
        self._settings.setValue("file_type", self.file_type_combo.currentData())
        self._settings.setValue("target_size", float(self.size_spin.value()))
        self._settings.setValue("size_unit", self.unit_combo.currentText())
        self._settings.setValue("headers", self.headers_input.toPlainText().strip())
        self._settings.setValue("filler_token", self.filler_input.text().strip())
        self._settings.sync()

    def _ensure_disk_space(self, destination: Path, required_bytes: int) -> None:
        """Raise an error if the target location lacks sufficient disk space."""
        parent = destination.parent if destination.parent.exists() else Path.home()
        try:
            usage = disk_usage(parent)
        except FileNotFoundError as exc:
            raise ValueError(f"Unable to read disk usage for {parent}") from exc

        if required_bytes > usage.free:
            needed = self._format_bytes(required_bytes)
            free = self._format_bytes(usage.free)
            raise ValueError(
                f"Not enough free space on {parent}. Needed: {needed}; available: {free}."
            )

    def _update_estimates(self) -> None:
        """Refresh the planning label with disk space and duration estimates."""
        try:
            size_value = SizeValue(
                amount=self.size_spin.value(),
                unit=self.unit_combo.currentText(),
            )
            target_bytes = size_value.to_bytes()
        except ValueError:
            self.estimate_label.setText("Enter a valid size and unit to compute estimates.")
            return

        if target_bytes <= 0:
            self.estimate_label.setText("Increase the target size to view estimates.")
            return

        destination = Path(self.path_edit.text().strip() or Path.home())
        parent = destination.parent if destination.parent.exists() else Path.home()

        try:
            usage = disk_usage(parent)
            free_bytes = usage.free
        except FileNotFoundError:
            free_bytes = 0

        size_human = self._format_bytes(target_bytes)
        free_human = self._format_bytes(free_bytes)
        duration_seconds = self._estimate_duration_seconds(target_bytes)
        duration_text = self._format_duration(duration_seconds)

        status_parts = [f"Required: {size_human}"]
        if free_bytes:
            status_parts.append(f"Free: {free_human}")
            if target_bytes > free_bytes:
                status_parts.append("Insufficient disk space")
        else:
            status_parts.append("Free space unavailable")

        status_parts.append(f"Time est.: {duration_text}")
        self.estimate_label.setText(" | ".join(status_parts))

    def _estimate_duration_seconds(self, target_bytes: int) -> float:
        """Estimate generation time based on file type heuristics."""
        file_type = (self.file_type_combo.currentData() or "tsv").lower()
        if file_type in {"csv", "tsv", "txt"}:
            throughput = 180 * 1024 * 1024  # ~180 MiB/s for buffered TSV writes
        else:
            throughput = 65 * 1024 * 1024  # ~65 MiB/s for OpenPyXL write-only streaming
        return target_bytes / throughput if throughput > 0 else 0.0

    @staticmethod
    def _format_bytes(value: int) -> str:
        """Render bytes in a human-friendly unit."""
        thresholds = [
            (1024 ** 3, "GB"),
            (1024 ** 2, "MB"),
            (1024, "KB"),
        ]
        for factor, suffix in thresholds:
            if value >= factor:
                return f"{value / factor:.2f} {suffix}"
        return f"{value} B"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Convert seconds into a short, readable duration."""
        if seconds < 1:
            return "<1s"
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API  # pylint: disable=invalid-name
        """Ensure background jobs stop before the window shuts down."""
        if self._worker and self._worker.isRunning():
            self._cancel_flag = True
            self._worker.request_cancel()
            self._worker.wait(1500)
        self._save_settings()
        super().closeEvent(event)
