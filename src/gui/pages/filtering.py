"""Filtering options page with presets and sliders."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.core.config import FILTER_PRESETS
from src.gui.logo import LogoManager


class FilteringPage(QWidget):
    next_clicked = Signal()
    back_clicked = Signal()

    def __init__(self, logo_manager: LogoManager, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        layout.addLayout(_create_page_header(logo_manager, "Filtering Options"))
        layout.addSpacing(20)

        preset_group = QGroupBox("Filter Presets")
        preset_layout = QHBoxLayout(preset_group)
        preset_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(FILTER_PRESETS.keys())
        self.preset_combo.setCurrentText("Moderate")
        self.preset_combo.currentTextChanged.connect(self._apply_filter_preset)
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()
        layout.addWidget(preset_group)

        filters_group = QGroupBox("Individual Filters")
        filters_layout = QGridLayout(filters_group)

        filters_layout.addWidget(QLabel("Min Dorado Q:"), 0, 0)
        self.min_dorado_q_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_dorado_q_slider.setRange(0, 20)
        self.min_dorado_q_slider.setValue(10)
        self.min_dorado_q_slider.valueChanged.connect(self._update_filter_labels)
        filters_layout.addWidget(self.min_dorado_q_slider, 0, 1)
        self.min_dorado_q_label = QLabel("10")
        filters_layout.addWidget(self.min_dorado_q_label, 0, 2)

        filters_layout.addWidget(QLabel("Min Mean Q:"), 1, 0)
        self.min_mean_q_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_mean_q_slider.setRange(0, 20)
        self.min_mean_q_slider.setValue(10)
        self.min_mean_q_slider.valueChanged.connect(self._update_filter_labels)
        filters_layout.addWidget(self.min_mean_q_slider, 1, 1)
        self.min_mean_q_label = QLabel("10")
        filters_layout.addWidget(self.min_mean_q_label, 1, 2)

        filters_layout.addWidget(QLabel("Min Length:"), 2, 0)
        self.min_len_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_len_slider.setRange(0, 1000)
        self.min_len_slider.setValue(200)
        self.min_len_slider.setSingleStep(50)
        self.min_len_slider.valueChanged.connect(self._update_filter_labels)
        filters_layout.addWidget(self.min_len_slider, 2, 1)
        self.min_len_label = QLabel("200")
        filters_layout.addWidget(self.min_len_label, 2, 2)

        filters_layout.addWidget(QLabel("Min Accuracy:"), 3, 0)
        self.min_acc_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_acc_slider.setRange(0, 100)
        self.min_acc_slider.setValue(85)
        self.min_acc_slider.valueChanged.connect(self._update_filter_labels)
        filters_layout.addWidget(self.min_acc_slider, 3, 1)
        self.min_acc_label = QLabel("0.85")
        filters_layout.addWidget(self.min_acc_label, 3, 2)

        layout.addWidget(filters_group)
        layout.addStretch()

        nav_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.back_clicked.emit)
        nav_layout.addWidget(back_btn)
        nav_layout.addStretch()

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self.next_clicked.emit)
        nav_layout.addWidget(next_btn)

        layout.addLayout(nav_layout)

    def _apply_filter_preset(self, preset_name: str):
        if preset_name == "Custom":
            return
        preset = FILTER_PRESETS[preset_name]
        self.min_dorado_q_slider.setValue(int(preset["min_dorado_q"]))
        self.min_mean_q_slider.setValue(int(preset["min_mean_q"]))
        self.min_len_slider.setValue(preset["min_len"])
        self.min_acc_slider.setValue(int(preset["min_acc"] * 100))

    def _update_filter_labels(self):
        self.min_dorado_q_label.setText(str(self.min_dorado_q_slider.value()))
        self.min_mean_q_label.setText(str(self.min_mean_q_slider.value()))
        self.min_len_label.setText(str(self.min_len_slider.value()))
        self.min_acc_label.setText(f"{self.min_acc_slider.value() / 100:.2f}")
        self.preset_combo.setCurrentText("Custom")

    def get_min_dorado_q(self) -> int:
        return self.min_dorado_q_slider.value()

    def get_min_mean_q(self) -> int:
        return self.min_mean_q_slider.value()

    def get_min_len(self) -> int:
        return self.min_len_slider.value()

    def get_min_acc(self) -> float:
        return self.min_acc_slider.value() / 100


def _create_page_header(logo_manager: LogoManager, title: str) -> QHBoxLayout:
    header = QHBoxLayout()
    mastrspy = logo_manager.create_logo_label("mastrspy", 40)
    header.addWidget(mastrspy)

    title_label = QLabel(title)
    title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
    header.addWidget(title_label)

    header.addStretch()

    malslabs = logo_manager.create_logo_label("malslabs", 40)
    header.addWidget(malslabs)

    return header
