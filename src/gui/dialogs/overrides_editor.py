"""Dialog for editing per-locus normalization cutoff overrides."""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class LociOverridesDialog(QDialog):
    def __init__(self, tsv_path: str, parent=None):
        super().__init__(parent)
        self.tsv_path = tsv_path
        self.setWindowTitle("Edit Per-Locus Norm_cutoff Overrides")
        self.setMinimumSize(600, 500)

        self._prefix_lines = []
        self._rows = []

        layout = QVBoxLayout(self)

        info = QLabel(
            "Edit per-locus overrides for Norm_cutoff thresholds.\n"
            "Column 1: Locus name (read-only)\n"
            "Column 2: Cutoff value (editable)"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Locus", "Norm_cutoff"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.table)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._load_tsv()

    def _load_tsv(self):
        if not os.path.isfile(self.tsv_path):
            QMessageBox.warning(
                self,
                "File Not Found",
                f"File does not exist:\n{self.tsv_path}",
            )
            return

        with open(self.tsv_path, "r") as f:
            lines = f.readlines()

        for line in lines:
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                self._prefix_lines.append(line)
                continue

            parts = stripped.split("\t")
            locus = parts[0] if parts else ""
            cutoff = parts[1] if len(parts) > 1 else ""
            self._rows.append((locus, cutoff))

        self.table.setRowCount(len(self._rows))
        for r, (locus, cutoff) in enumerate(self._rows):
            item_locus = QTableWidgetItem(locus)
            item_locus.setFlags(
                item_locus.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self.table.setItem(r, 0, item_locus)

            item_cutoff = QTableWidgetItem(str(cutoff))
            self.table.setItem(r, 1, item_cutoff)

    def _on_accept(self):
        updated_rows = []

        for r in range(self.table.rowCount()):
            locus_item = self.table.item(r, 0)
            cutoff_item = self.table.item(r, 1)

            locus = (locus_item.text() if locus_item else "").strip()
            cutoff = (cutoff_item.text() if cutoff_item else "").strip()

            if locus == "":
                QMessageBox.critical(
                    self,
                    "Invalid Row",
                    f"Row {r + 1} has empty locus name",
                )
                return

            try:
                float(cutoff)
            except ValueError:
                QMessageBox.critical(
                    self,
                    "Invalid Cutoff",
                    f"Row {r + 1} for locus '{locus}' has invalid "
                    f"cutoff: '{cutoff}'",
                )
                return

            updated_rows.append((locus, cutoff))

        tmp_path = self.tsv_path + ".tmp"
        with open(tmp_path, "w") as f:
            if self._prefix_lines:
                f.writelines(self._prefix_lines)
            for locus, cutoff in updated_rows:
                f.write(f"{locus}\t{cutoff}\n")

        os.replace(tmp_path, self.tsv_path)
        self.accept()
