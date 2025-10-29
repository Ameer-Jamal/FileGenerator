"""Main application window for the File Generator."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

try:
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
        QDoubleSpinBox,
        QProgressBar,
        QPlainTextEdit,
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
        ("tsv", "Tab-delimited (*.tsv)"),
    )

    def __init__(self, service: GenerationService | None = None) -> None:
        super().__init__()
        self.setWindowTitle("File Generator")
        self.resize(720, 540)

        self._service = service or create_default_service()
        self._worker: GenerationWorker | None = None
        self._cancel_flag = False

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        container = QWidget(self)
        layout = QFormLayout()
        container.setLayout(layout)

        # Destination picker
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
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
        layout.addRow(QLabel("Header Row"), self.headers_input)

        # Filler text
        self.filler_input = QLineEdit("SampleValue")
        layout.addRow(QLabel("Filler Token"), self.filler_input)

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
        self.progress_bar.setValue(0 if not running else 0)
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

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API  # pylint: disable=invalid-name
        """Ensure background jobs stop before the window shuts down."""
        if self._worker and self._worker.isRunning():
            self._cancel_flag = True
            self._worker.request_cancel()
            self._worker.wait(1500)
        super().closeEvent(event)
