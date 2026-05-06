from __future__ import annotations

import sys
import threading
from datetime import datetime
from pathlib import Path

from h5bot.automation import DependencyError, GameWindow, Win32Automation
from h5bot.config import AppConfig, FlowStep, TaskBranch, TaskPlan, load_config, resolve_templates_dir, save_config
from h5bot.flow import FlowRunner
from h5bot.importer import export_panda_templates
from h5bot.paths import app_root, writable_path
from h5bot.recognition import recognize_step
from h5bot.roi import auto_roi_from_match, format_roi, parse_roi
from h5bot.template_probe import probe_step_templates_in_window


try:
    from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
    from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap
    from PyQt5.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QMenu,
        QPushButton,
        QSplitter,
        QSpinBox,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise DependencyError("缺少 PyQt5，请先在 32 位 Python 中运行: py -3.14-32 -m pip install -r requirements.txt") from exc


ROOT = app_root()
CONFIG_PATH = writable_path("config", "app_config.json")
TEMPLATE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg"}


class CropDialog(QDialog):
    def __init__(self, image, cv2_module, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("裁剪模板")
        self.cv2 = cv2_module
        self.image = image
        self.start: QPoint | None = None
        self.end: QPoint | None = None
        self.pixmap = QPixmap.fromImage(self._to_qimage(image))
        self.setMinimumSize(min(self.pixmap.width(), 1100), min(self.pixmap.height(), 760))

    def selected_rect(self) -> tuple[int, int, int, int] | None:
        if self.start is None or self.end is None:
            return None
        sx = self.pixmap.width() / max(1, self.width())
        sy = self.pixmap.height() / max(1, self.height())
        return int(self.start.x() * sx), int(self.start.y() * sy), int(self.end.x() * sx), int(self.end.y() * sy)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)
        if self.start and self.end:
            painter.setPen(Qt.red)
            painter.drawRect(QRect(self.start, self.end))

    def mousePressEvent(self, event) -> None:
        self.start = _event_pos(event)
        self.end = self.start
        self.update()

    def mouseMoveEvent(self, event) -> None:
        self.end = _event_pos(event)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        self.end = _event_pos(event)
        self.accept()

    def _to_qimage(self, image) -> QImage:
        rgb = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        return QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()


class RoiSelectionDialog(QDialog):
    def __init__(self, image, cv2_module, initial_roi: list[int] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("选择 ROI 区域")
        self.cv2 = cv2_module
        self.image = image
        self.start: QPoint | None = None
        self.end: QPoint | None = None
        self.pixmap = QPixmap.fromImage(self._to_qimage(image))
        self.setMinimumSize(min(self.pixmap.width(), 1100), min(self.pixmap.height() + 48, 820))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = RoiCanvas(self.pixmap, initial_roi)
        layout.addWidget(self.canvas, 1)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(10, 8, 10, 8)
        buttons.addStretch(1)
        self.ok_button = QPushButton("确认")
        self.ok_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("取消")
        buttons.addWidget(self.ok_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def selected_roi(self) -> list[int] | None:
        return self.canvas.selected_roi()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def _to_qimage(self, image) -> QImage:
        rgb = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        return QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()


class RoiCanvas(QWidget):
    def __init__(self, pixmap: QPixmap, initial_roi: list[int] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.pixmap = pixmap
        self.start: QPoint | None = None
        self.end: QPoint | None = None
        self.initial_roi = [int(part) for part in initial_roi] if initial_roi and len(initial_roi) == 4 else None
        self.setCursor(Qt.CrossCursor)
        self.setMinimumSize(min(self.pixmap.width(), 1100), min(self.pixmap.height(), 760))

    def selected_roi(self) -> list[int] | None:
        if self.start is None or self.end is None:
            return self.initial_roi
        sx = self.pixmap.width() / max(1, self.width())
        sy = self.pixmap.height() / max(1, self.height())
        x1 = int(self.start.x() * sx)
        y1 = int(self.start.y() * sy)
        x2 = int(self.end.x() * sx)
        y2 = int(self.end.y() * sy)
        left, right = sorted((max(0, x1), max(0, x2)))
        top, bottom = sorted((max(0, y1), max(0, y2)))
        right = min(right, self.pixmap.width())
        bottom = min(bottom, self.pixmap.height())
        if right <= left or bottom <= top:
            return None
        return [left, top, right, bottom]

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)
        roi = self.selected_roi()
        if not roi:
            return
        sx = self.width() / max(1, self.pixmap.width())
        sy = self.height() / max(1, self.pixmap.height())
        rect = QRect(
            int(roi[0] * sx),
            int(roi[1] * sy),
            int((roi[2] - roi[0]) * sx),
            int((roi[3] - roi[1]) * sy),
        )
        painter.fillRect(rect, QColor(0, 150, 136, 45))
        painter.setPen(QColor(0, 150, 136))
        painter.drawRect(rect)

    def mousePressEvent(self, event) -> None:
        self.initial_roi = None
        self.start = _event_pos(event)
        self.end = self.start
        self.update()

    def mouseMoveEvent(self, event) -> None:
        self.end = _event_pos(event)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        self.end = _event_pos(event)
        self.update()


class WindowPickerButton(QPushButton):
    window_picked = pyqtSignal(QPoint)

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.default_text = text
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("拖到游戏窗口后松开绑定")
        self.setMinimumWidth(54)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        self.setDown(True)
        self.setText("◎")
        self.setCursor(Qt.CrossCursor)
        self.grabMouse()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return
        self.releaseMouse()
        self.setDown(False)
        self.setText(self.default_text)
        self.setCursor(Qt.OpenHandCursor)
        self.window_picked.emit(_event_global_pos(event))


class StepTemplateDialog(QDialog):
    def __init__(self, step_name: str, templates: list[str], parent: "MainWindow") -> None:
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle(f"模板组 - {step_name or '未命名步骤'}")
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        title = QLabel(step_name or "未命名步骤")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        self.template_list = QListWidget()
        self.template_list.setSelectionMode(QListWidget.ExtendedSelection)
        for template in templates:
            self.template_list.addItem(template)
        layout.addWidget(self.template_list, 1)

        actions = QHBoxLayout()
        self.add_file_button = QPushButton("添加图片")
        self.capture_button = QPushButton("截图添加")
        self.remove_button = QPushButton("移除选中")
        self.remove_button.setObjectName("dangerButton")
        actions.addWidget(self.add_file_button)
        actions.addWidget(self.capture_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.ok_button = QPushButton("确定")
        self.ok_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("取消")
        footer.addWidget(self.ok_button)
        footer.addWidget(self.cancel_button)
        layout.addLayout(footer)

        self.add_file_button.clicked.connect(self.add_files)
        self.capture_button.clicked.connect(self.capture_template)
        self.remove_button.clicked.connect(self.remove_selected)
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def templates(self) -> list[str]:
        return [self.template_list.item(index).text().strip() for index in range(self.template_list.count()) if self.template_list.item(index).text().strip()]

    def add_files(self) -> None:
        files, _filter = QFileDialog.getOpenFileNames(
            self,
            "选择模板图片",
            str(resolve_templates_dir(self.main_window.config)),
            "Images (*.bmp *.png *.jpg *.jpeg);;All Files (*)",
        )
        for filename in files:
            self._add_template_path(Path(filename))

    def capture_template(self) -> None:
        self.main_window.capture_template(add_to_list=self)

    def remove_selected(self) -> None:
        for item in self.template_list.selectedItems():
            self.template_list.takeItem(self.template_list.row(item))

    def add_template(self, template: str) -> None:
        if template and template not in self.templates():
            self.template_list.addItem(template)

    def _add_template_path(self, path: Path) -> None:
        templates_dir = resolve_templates_dir(self.main_window.config)
        try:
            template = str(path.resolve().relative_to(templates_dir.resolve()))
        except ValueError:
            template = str(path)
        self.add_template(template)


class ClearOnDoubleClickTextEdit(QTextEdit):
    def mouseDoubleClickEvent(self, event) -> None:
        self.clear()
        event.accept()


def _event_pos(event) -> QPoint:
    if hasattr(event, "position"):
        return event.position().toPoint()
    return event.pos()


def _event_global_pos(event) -> QPoint:
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()


class MainWindow(QMainWindow):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    window_started_signal = pyqtSignal(int)
    window_finished_signal = pyqtSignal(int, bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("全自动辅助助手")
        self.resize(1320, 820)
        self.config = load_config(CONFIG_PATH)
        self.backend: Win32Automation | None = None
        self.windows: list[GameWindow] = []
        self.window_task_assignments: dict[int, tuple[str, str]] = {}
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.running_hwnds: set[int] = set()
        self.exception_hwnds: set[int] = set()
        self._loading_step_detail = False
        self._build_ui()
        self._connect()
        self._load_config_to_ui()
        self._init_backend()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("全自动辅助助手")
        title.setObjectName("appTitle")
        subtitle = QLabel("斗罗大陆H5 多开后台任务控制台")
        subtitle.setObjectName("appSubtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        title_row.addLayout(title_block, 1)
        layout.addLayout(title_row)

        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(10, 6, 10, 6)
        status_layout.setSpacing(8)
        self.dm_status_label = self._status_chip("大漠: 检测中")
        self.bound_count_label = self._status_chip("已绑定: 0")
        self.running_count_label = self._status_chip("运行中: 0")
        self.exception_count_label = self._status_chip("异常: 0")
        for label in [self.dm_status_label, self.bound_count_label, self.running_count_label, self.exception_count_label]:
            status_layout.addWidget(label)
        status_layout.addStretch(1)
        layout.addWidget(status_bar)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.scan_button = QPushButton("扫描窗口")
        self.pick_window_button = WindowPickerButton("◎")
        self.pick_window_button.setObjectName("crosshairButton")
        self.save_button = QPushButton("保存配置")
        self.test_button = QPushButton("测试识别")
        self.start_button = QPushButton("开始全部")
        self.start_button.setObjectName("primaryButton")
        self.pause_button = QPushButton("暂停")
        self.stop_button = QPushButton("停止")
        self.stop_button.setObjectName("dangerButton")
        toolbar.addWidget(self._toolbar_group("窗口操作", [self.scan_button, self.pick_window_button]))
        toolbar.addWidget(self._toolbar_group("配置操作", [self.save_button, self.test_button]))
        toolbar.addWidget(self._toolbar_group("运行操作", [self.start_button, self.pause_button, self.stop_button]))
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        left_panel, left = self._panel("多开窗口")
        left_panel.setMinimumWidth(240)
        left_panel.setMaximumWidth(270)
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("窗口标题关键词，例如 斗罗大陆H5")
        self.assign_task_button = QPushButton("批量分配当前任务")
        self.remove_window_button = QPushButton("从列表移除")
        self.remove_window_button.setObjectName("dangerButton")
        self.window_list = QListWidget()
        self.window_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.window_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.window_count_label = QLabel("等待扫描")
        self.window_count_label.setObjectName("mutedLabel")
        self.current_task_label = QLabel("当前任务: 未选择")
        self.current_task_label.setObjectName("taskDescription")
        self.current_task_label.setWordWrap(True)
        left.addWidget(self.keyword_edit)
        window_buttons_1 = QHBoxLayout()
        window_buttons_1.addWidget(self.scan_button, 1)
        window_buttons_1.addWidget(self.pick_window_button)
        left.addLayout(window_buttons_1)
        left.addWidget(self.current_task_label)
        window_buttons_2 = QHBoxLayout()
        window_buttons_2.addWidget(self.assign_task_button)
        window_buttons_2.addWidget(self.remove_window_button)
        left.addLayout(window_buttons_2)
        left.addWidget(self.window_count_label)
        left.addWidget(self.window_list, 1)

        center_panel, center = self._panel("任务方案")
        plan_row = QHBoxLayout()
        self.plan_combo = QComboBox()
        self.task_combo = QComboBox()
        plan_row.addWidget(QLabel("方案"))
        plan_row.addWidget(self.plan_combo)
        plan_row.addWidget(QLabel("可选任务"))
        plan_row.addWidget(self.task_combo, 1)
        center.addLayout(plan_row)
        plan_actions = QHBoxLayout()
        self.add_plan_button = QPushButton("新增方案")
        self.rename_plan_button = QPushButton("重命名方案")
        self.delete_plan_button = QPushButton("删除方案")
        self.delete_plan_button.setObjectName("dangerButton")
        plan_actions.addWidget(self.add_plan_button)
        plan_actions.addWidget(self.rename_plan_button)
        plan_actions.addWidget(self.delete_plan_button)
        center.addLayout(plan_actions)
        task_actions = QHBoxLayout()
        self.add_task_button = QPushButton("新增任务")
        self.copy_task_button = QPushButton("复制任务")
        self.delete_task_button = QPushButton("删除任务")
        self.delete_task_button.setObjectName("dangerButton")
        task_actions.addWidget(self.add_task_button)
        task_actions.addWidget(self.copy_task_button)
        task_actions.addWidget(self.delete_task_button)
        center.addLayout(task_actions)
        self.task_description_label = QLabel()
        self.task_description_label.setObjectName("taskDescription")
        self.task_description_label.setWordWrap(True)
        center.addWidget(self.task_description_label)
        self.templates_hint_label = QLabel("模板目录: assets/templates")
        self.templates_hint_label.setObjectName("mutedLabel")
        center.addWidget(self.templates_hint_label)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.1, 1.0)
        self.threshold_spin.setSingleStep(0.01)
        self.threshold_spin.setDecimals(2)
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 20)
        self.threshold_spin.setMinimumWidth(100)
        self.retries_spin.setMinimumWidth(100)

        self.flow_path_label = QLabel("流程路径: 未选择")
        self.flow_path_label.setObjectName("flowPath")
        self.flow_path_label.setWordWrap(True)
        center.addWidget(self.flow_path_label)

        self.flow_table = QTableWidget(0, 7)
        self.flow_table.setHorizontalHeaderLabels(["启用", "步骤", "模板组", "ROI", "找到后", "找到跳转", "找不到后/跳转"])
        self.flow_table.verticalHeader().setVisible(False)
        self.flow_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.flow_table.setSelectionMode(QTableWidget.SingleSelection)
        self.flow_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.flow_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.flow_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        center.addWidget(self.flow_table, 1)
        step_actions = QHBoxLayout()
        self.add_step_button = QPushButton("新增步骤")
        self.edit_templates_button = QPushButton("编辑模板组")
        self.delete_step_button = QPushButton("删除步骤")
        self.delete_step_button.setObjectName("dangerButton")
        self.move_step_up_button = QPushButton("上移步骤")
        self.move_step_down_button = QPushButton("下移步骤")
        step_actions.addWidget(self.add_step_button)
        step_actions.addWidget(self.edit_templates_button)
        step_actions.addWidget(self.delete_step_button)
        step_actions.addWidget(self.move_step_up_button)
        step_actions.addWidget(self.move_step_down_button)
        center.addLayout(step_actions)

        right_column = QWidget()
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.setContentsMargins(0, 0, 0, 0)
        right_column_layout.setSpacing(12)

        detail_panel, right = self._panel("当前步骤详情")
        detail_grid = QGridLayout()
        detail_grid.setHorizontalSpacing(10)
        detail_grid.setVerticalSpacing(8)
        self.step_name_label = QLabel("未选择步骤")
        self.step_name_label.setObjectName("detailTitle")
        self.step_templates_label = QLabel("模板组: -")
        self.step_templates_label.setObjectName("mutedLabel")
        self.step_templates_label.setWordWrap(True)
        self.step_roi_label = QLabel("ROI: 全窗口")
        self.step_roi_label.setObjectName("mutedLabel")
        self.step_roi_label.setWordWrap(True)
        self.step_delay_spin = QDoubleSpinBox()
        self.step_delay_spin.setRange(0.0, 120.0)
        self.step_delay_spin.setSingleStep(0.1)
        self.step_delay_spin.setDecimals(2)
        self.capture_button = QPushButton("截图裁剪模板")
        self.capture_button.setObjectName("primaryButton")
        self.detail_edit_templates_button = QPushButton("编辑模板组")
        self.select_roi_button = QPushButton("选择ROI区域")
        self.auto_roi_button = QPushButton("自动生成ROI")
        self.clear_roi_button = QPushButton("清空ROI")
        self.clear_roi_button.setObjectName("dangerButton")
        detail_grid.addWidget(QLabel("点击后等待"), 0, 0)
        detail_grid.addWidget(self.step_delay_spin, 0, 1)
        detail_grid.setColumnStretch(1, 1)
        right.addWidget(self.step_name_label)
        right.addWidget(self.step_templates_label)
        right.addWidget(self.step_roi_label)
        right.addLayout(detail_grid)
        right_detail_actions = QHBoxLayout()
        right_detail_actions.addWidget(self.detail_edit_templates_button)
        right_detail_actions.addWidget(self.capture_button)
        right.addLayout(right_detail_actions)
        roi_actions = QHBoxLayout()
        roi_actions.addWidget(self.select_roi_button)
        roi_actions.addWidget(self.auto_roi_button)
        roi_actions.addWidget(self.clear_roi_button)
        right.addLayout(roi_actions)
        right.addStretch(1)

        global_panel, global_layout = self._panel("全局识别参数")
        global_grid = QGridLayout()
        global_grid.setHorizontalSpacing(10)
        global_grid.setVerticalSpacing(8)
        global_grid.addWidget(QLabel("默认识别阈值"), 0, 0)
        global_grid.addWidget(self.threshold_spin, 0, 1)
        global_grid.addWidget(QLabel("默认重试次数"), 1, 0)
        global_grid.addWidget(self.retries_spin, 1, 1)
        global_grid.setColumnStretch(1, 1)
        global_layout.addLayout(global_grid)

        log_panel, log_layout = self._panel("运行日志")
        self.status_label = QLabel("未运行")
        self.status_label.setObjectName("statusPill")
        self.clear_log_button = QPushButton("清空日志")
        self.log_box = ClearOnDoubleClickTextEdit()
        self.log_box.setReadOnly(True)
        log_header = QHBoxLayout()
        log_header.addWidget(self.status_label, 1)
        log_header.addWidget(self.clear_log_button)
        log_layout.addLayout(log_header)
        log_layout.addWidget(self.log_box, 1)
        right_column_layout.addWidget(detail_panel, 1)
        right_column_layout.addWidget(global_panel)
        right_column_layout.addWidget(log_panel, 2)

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_column)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([255, 780, 275])
        layout.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self._apply_styles()

    def _panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)
        label = QLabel(title)
        label.setObjectName("panelTitle")
        layout.addWidget(label)
        return panel, layout

    def _toolbar_group(self, title: str, buttons: list[QPushButton]) -> QFrame:
        group = QFrame()
        group.setObjectName("toolbarGroup")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(6)
        label = QLabel(title)
        label.setObjectName("toolbarLabel")
        layout.addWidget(label)
        for button in buttons:
            button.setMinimumHeight(34)
            layout.addWidget(button)
        return group

    def _status_chip(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("statusChip")
        label.setMinimumHeight(28)
        return label

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#appRoot { background: #F4FAF8; color: #134e4a; font-size: 13px; }
            QLabel#appTitle { font-size: 22px; font-weight: 700; color: #0f172a; }
            QLabel#appSubtitle, QLabel#mutedLabel { color: #52706d; }
            QFrame#statusBar, QFrame#toolbarGroup {
                background: #FFFFFF;
                border: 1px solid #C9E4DF;
                border-radius: 8px;
            }
            QLabel#statusChip {
                background: #F4FAF8;
                color: #134e4a;
                border: 1px solid #C9E4DF;
                border-radius: 6px;
                padding: 5px 10px;
                font-weight: 600;
            }
            QLabel#toolbarLabel { color: #52706d; font-weight: 700; padding-right: 4px; }
            QFrame#panel {
                background: #FFFFFF;
                border: 1px solid #C9E4DF;
                border-radius: 8px;
            }
            QLabel#panelTitle { font-size: 15px; font-weight: 700; color: #134e4a; }
            QLabel#taskDescription {
                background: #F4FAF8;
                border: 1px solid #C9E4DF;
                border-radius: 6px;
                color: #315f5a;
                padding: 7px;
            }
            QLabel#flowPath {
                background: #F4FAF8;
                border: 1px solid #C9E4DF;
                border-radius: 6px;
                color: #315f5a;
                padding: 7px;
            }
            QLabel#detailTitle { font-size: 14px; font-weight: 700; color: #134e4a; }
            QLabel#statusPill {
                background: #ecfdf5;
                color: #009688;
                border: 1px solid #C9E4DF;
                border-radius: 6px;
                padding: 7px;
                font-weight: 600;
            }
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #C9E4DF;
                border-radius: 6px;
                padding: 5px 10px;
                min-height: 24px;
                color: #134e4a;
            }
            QPushButton:hover { background: #F4FAF8; border-color: #009688; }
            QPushButton:pressed { background: #ccfbf1; }
            QPushButton#primaryButton { background: #009688; border-color: #009688; color: #ffffff; font-weight: 700; }
            QPushButton#primaryButton:hover { background: #00796B; }
            QPushButton#dangerButton { color: #E53935; border-color: #F3B8B5; background: #FFF5F5; }
            QPushButton#dangerButton:hover { background: #FDECEC; border-color: #E53935; }
            QPushButton#crosshairButton {
                font-size: 22px;
                font-weight: 700;
                padding: 4px 10px;
                min-width: 48px;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background: #FFFFFF;
                border: 1px solid #C9E4DF;
                border-radius: 6px;
                padding: 4px 8px;
                min-height: 24px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #009688;
            }
            QListWidget, QTextEdit, QTableWidget {
                background: #FFFFFF;
                border: 1px solid #C9E4DF;
                border-radius: 6px;
                selection-background-color: #ccfbf1;
                selection-color: #134e4a;
            }
            QHeaderView::section {
                background: #F4FAF8;
                border: 0;
                border-bottom: 1px solid #C9E4DF;
                padding: 6px;
                color: #315f5a;
                font-weight: 600;
            }
            QLabel#dialogTitle { font-size: 15px; font-weight: 700; color: #134e4a; }
            """
        )

    def _connect(self) -> None:
        self.scan_button.clicked.connect(self.scan_windows)
        self.pick_window_button.window_picked.connect(self.bind_window_from_point)
        self.remove_window_button.clicked.connect(self.remove_selected_window)
        self.assign_task_button.clicked.connect(self.assign_current_task_to_window)
        self.capture_button.clicked.connect(self.capture_template)
        self.detail_edit_templates_button.clicked.connect(self.edit_selected_step_templates)
        self.select_roi_button.clicked.connect(self.select_step_roi)
        self.auto_roi_button.clicked.connect(self.auto_generate_step_roi)
        self.clear_roi_button.clicked.connect(self.clear_step_roi)
        self.add_plan_button.clicked.connect(self.add_task_plan)
        self.rename_plan_button.clicked.connect(self.rename_task_plan)
        self.delete_plan_button.clicked.connect(self.delete_task_plan)
        self.add_task_button.clicked.connect(self.add_task)
        self.copy_task_button.clicked.connect(self.copy_task)
        self.delete_task_button.clicked.connect(self.delete_task)
        self.add_step_button.clicked.connect(self.add_flow_step)
        self.edit_templates_button.clicked.connect(self.edit_selected_step_templates)
        self.delete_step_button.clicked.connect(self.delete_flow_step)
        self.move_step_up_button.clicked.connect(lambda: self.move_flow_step(-1))
        self.move_step_down_button.clicked.connect(lambda: self.move_flow_step(1))
        self.save_button.clicked.connect(self.save_current_config)
        self.test_button.clicked.connect(self.probe_selected_step_template)
        self.start_button.clicked.connect(self.start_all)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.stop_button.clicked.connect(self.stop)
        self.clear_log_button.clicked.connect(self.log_box.clear)
        self.window_list.customContextMenuRequested.connect(self.show_window_context_menu)
        self.plan_combo.currentTextChanged.connect(self._plan_changed)
        self.task_combo.currentTextChanged.connect(self._task_changed)
        self.flow_table.cellDoubleClicked.connect(self._flow_cell_double_clicked)
        self.flow_table.currentCellChanged.connect(self._flow_current_cell_changed)
        self.step_delay_spin.valueChanged.connect(self._step_detail_changed)
        self.log_signal.connect(self.log)
        self.finished_signal.connect(self._worker_finished)
        self.window_started_signal.connect(self._window_started)
        self.window_finished_signal.connect(self._window_finished)

    def _init_backend(self) -> None:
        try:
            self.backend = Win32Automation()
            self.window_count_label.setText("未添加窗口")
            dm_clicker = getattr(self.backend, "dm_clicker", None)
            dm_ok = bool(dm_clicker and dm_clicker.available())
            self.dm_status_label.setText("大漠: 可用" if dm_ok else "大漠: 回退")
            self.log("窗口列表为空，请扫描窗口或拖动准星绑定窗口")
            self._refresh_window_list()
            self._refresh_status_bar()
        except DependencyError as exc:
            self.dm_status_label.setText("大漠: 不可用")
            self.log(str(exc))
            QMessageBox.warning(self, "依赖缺失", str(exc))

    def _load_config_to_ui(self) -> None:
        self.keyword_edit.setText(self.config.window_keyword)
        self.templates_hint_label.setText(f"模板目录: {resolve_templates_dir(self.config)}")
        self.threshold_spin.setValue(self.config.default_threshold)
        self.retries_spin.setValue(self.config.default_retries)
        self._populate_task_selectors()
        self._populate_flow(self.config.normalized_flow())

    def _populate_task_selectors(self) -> None:
        self.plan_combo.blockSignals(True)
        self.task_combo.blockSignals(True)
        self.plan_combo.clear()
        for plan in self.config.task_plans:
            self.plan_combo.addItem(plan.name)
        index = self.plan_combo.findText(self.config.selected_plan)
        self.plan_combo.setCurrentIndex(max(index, 0))
        self.plan_combo.blockSignals(False)
        self._refresh_task_combo()
        self.task_combo.blockSignals(False)

    def _refresh_task_combo(self) -> None:
        self.task_combo.blockSignals(True)
        self.task_combo.clear()
        plan = self._selected_plan()
        if plan:
            for task in plan.tasks:
                self.task_combo.addItem(task.name)
        index = self.task_combo.findText(self.config.selected_task)
        self.task_combo.setCurrentIndex(max(index, 0))
        self.task_combo.blockSignals(False)
        self._refresh_task_description()

    def _selected_plan(self) -> TaskPlan | None:
        name = self.plan_combo.currentText() or self.config.selected_plan
        for plan in self.config.task_plans:
            if plan.name == name:
                return plan
        return None

    def _selected_task(self) -> TaskBranch | None:
        plan = self._selected_plan()
        name = self.task_combo.currentText() or self.config.selected_task
        if not plan:
            return None
        for task in plan.tasks:
            if task.name == name:
                return task
        return None

    def _plan_changed(self, *_args) -> None:
        self.config.selected_plan = self.plan_combo.currentText()
        plan = self._selected_plan()
        self.config.selected_task = plan.tasks[0].name if plan and plan.tasks else ""
        self._refresh_task_combo()
        self._populate_flow(self.config.normalized_flow())

    def _task_changed(self, *_args) -> None:
        self.config.selected_plan = self.plan_combo.currentText()
        self.config.selected_task = self.task_combo.currentText()
        self._refresh_task_description()
        self._populate_flow(self.config.normalized_flow())

    def _refresh_task_description(self) -> None:
        task = self._selected_task()
        if task:
            self.task_description_label.setText(task.description or "该任务暂无说明")
        else:
            self.task_description_label.setText("当前方案没有可选任务")
        plan_name = self.plan_combo.currentText() or self.config.selected_plan
        task_name = self.task_combo.currentText() or self.config.selected_task
        self.current_task_label.setText(f"当前任务: {plan_name} / {task_name}")

    def _populate_flow(self, flow: list[FlowStep]) -> None:
        self._loading_step_detail = True
        self.flow_table.setRowCount(len(flow))
        for row, step in enumerate(flow):
            enabled = QCheckBox()
            enabled.setChecked(step.enabled)
            self.flow_table.setCellWidget(row, 0, enabled)
            templates = step.template_group()
            values = [
                step.name,
                _template_group_summary(templates),
                "" if step.roi is None else ",".join(str(part) for part in step.roi),
                step.on_found,
                step.found_next,
                f"{step.on_not_found}:{step.not_found_next}" if step.not_found_next else step.on_not_found,
            ]
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if column == 1:
                    self._set_step_detail_data(item, step.threshold, step.retries, step.delay_after_click)
                if column == 2:
                    item.setData(Qt.UserRole, templates)
                    item.setToolTip("|".join(templates))
                self.flow_table.setItem(row, column, item)
        self._loading_step_detail = False
        if flow:
            self.flow_table.selectRow(0)
            self._load_step_detail(0)
        else:
            self._load_step_detail(-1)
        self._refresh_flow_path_summary()
        self.flow_table.resizeColumnsToContents()

    def read_config_from_ui(self) -> AppConfig:
        flow = self._read_flow_table()
        task_plans = self._task_plans_with_current_flow(flow)
        return AppConfig(
            window_keyword=self.keyword_edit.text().strip() or "斗罗大陆H5",
            templates_dir=self.config.templates_dir,
            default_threshold=self.threshold_spin.value(),
            default_retries=self.retries_spin.value(),
            window_task_bindings=self._window_task_bindings_from_ui(),
            selected_plan=self.plan_combo.currentText() or "方案1",
            selected_task=self.task_combo.currentText() or "神界中枢刷怪",
            task_plans=task_plans,
            flow=self.config.flow,
        )

    def _read_flow_table(self) -> list[FlowStep]:
        self._sync_current_step_detail()
        flow = []
        for row in range(self.flow_table.rowCount()):
            flow.append(self._read_step_row(row))
        return flow

    def _read_step_row(self, row: int) -> FlowStep:
        enabled_widget = self.flow_table.cellWidget(row, 0)
        detail = self._step_detail_data(row)
        return FlowStep(
            name=self._cell(row, 1),
            templates=self._cell_templates(row, 2),
            roi=self._optional_roi(self._cell(row, 3)),
            threshold=detail["threshold"],
            retries=detail["retries"],
            delay_after_click=detail["delay_after_click"],
            on_found=self._cell(row, 4) or "click",
            found_next=self._cell(row, 5),
            on_not_found=self._split_action(self._cell(row, 6))[0],
            not_found_next=self._split_action(self._cell(row, 6))[1],
            enabled=enabled_widget.isChecked() if isinstance(enabled_widget, QCheckBox) else True,
        )

    def _cell_templates(self, row: int, column: int) -> list[str]:
        item = self.flow_table.item(row, column)
        if item:
            value = item.data(Qt.UserRole)
            if isinstance(value, list):
                return [str(template).strip() for template in value if str(template).strip()]
        return self._split_templates(self._cell(row, column))

    def _set_step_detail_data(self, item: QTableWidgetItem, threshold: float | None, retries: int | None, delay_after_click: float) -> None:
        item.setData(
            Qt.UserRole,
            {
                "threshold": threshold,
                "retries": retries,
                "delay_after_click": float(delay_after_click),
            },
        )

    def _step_detail_data(self, row: int) -> dict[str, float | int | None]:
        item = self.flow_table.item(row, 1)
        value = item.data(Qt.UserRole) if item else None
        if isinstance(value, dict):
            return {
                "threshold": value.get("threshold"),
                "retries": value.get("retries"),
                "delay_after_click": float(value.get("delay_after_click", self.config.default_delay_after_click)),
            }
        return {"threshold": None, "retries": None, "delay_after_click": self.config.default_delay_after_click}

    def _flow_current_cell_changed(self, current_row: int, _current_column: int, previous_row: int, _previous_column: int) -> None:
        if previous_row >= 0:
            self._sync_step_detail(previous_row)
        self._load_step_detail(current_row)

    def _load_step_detail(self, row: int) -> None:
        self._loading_step_detail = True
        try:
            if row < 0 or row >= self.flow_table.rowCount():
                self.step_name_label.setText("未选择步骤")
                self.step_templates_label.setText("模板组: -")
                self.step_roi_label.setText("ROI: 全窗口")
                self.step_delay_spin.setValue(self.config.default_delay_after_click)
                return
            detail = self._step_detail_data(row)
            templates = self._cell_templates(row, 2)
            self.step_name_label.setText(self._cell(row, 1) or f"步骤 {row + 1}")
            self.step_templates_label.setText(f"模板组: {' | '.join(templates) if templates else '-'}")
            self.step_roi_label.setText(f"ROI: {self._cell(row, 3) or '全窗口'}")
            self.step_delay_spin.setValue(float(detail["delay_after_click"]))
        finally:
            self._loading_step_detail = False

    def _step_detail_changed(self, *_args) -> None:
        if not self._loading_step_detail:
            self._sync_current_step_detail()

    def _sync_current_step_detail(self) -> None:
        self._sync_step_detail(self.flow_table.currentRow())

    def _sync_step_detail(self, row: int) -> None:
        if row < 0 or row >= self.flow_table.rowCount() or self._loading_step_detail:
            return
        item = self.flow_table.item(row, 1)
        if item is None:
            item = QTableWidgetItem("")
            self.flow_table.setItem(row, 1, item)
        detail = self._step_detail_data(row)
        self._set_step_detail_data(item, detail["threshold"], detail["retries"], self.step_delay_spin.value())

    def _task_plans_with_current_flow(self, flow: list[FlowStep]) -> list[TaskPlan]:
        selected_plan = self.plan_combo.currentText()
        selected_task = self.task_combo.currentText()
        plans = []
        for plan in self.config.task_plans:
            tasks = []
            for task in plan.tasks:
                if plan.name == selected_plan and task.name == selected_task:
                    tasks.append(TaskBranch(task.name, task.description, flow, task.enabled))
                else:
                    tasks.append(task)
            plans.append(TaskPlan(plan.name, tasks))
        return plans

    def _persist_current_flow_to_selected_task(self) -> None:
        if not hasattr(self, "flow_table") or not self.config.task_plans:
            return
        self.config = self.read_config_from_ui()

    def add_task_plan(self) -> None:
        self._persist_current_flow_to_selected_task()
        name, ok = QInputDialog.getText(self, "新增方案", "方案名称", text="新方案")
        if not ok:
            return
        plan = self.config.add_task_plan(name)
        self._populate_task_selectors()
        self._populate_flow([])
        self.log(f"已新增方案: {plan.name}")

    def rename_task_plan(self) -> None:
        self._persist_current_flow_to_selected_task()
        current = self.plan_combo.currentText()
        if not current:
            return
        name, ok = QInputDialog.getText(self, "重命名方案", "方案名称", text=current)
        if not ok:
            return
        plan = self.config.rename_task_plan(current, name)
        if plan:
            self._populate_task_selectors()
            self._populate_flow(self.config.normalized_flow())
            self.log(f"方案已重命名: {plan.name}")

    def delete_task_plan(self) -> None:
        self._persist_current_flow_to_selected_task()
        current = self.plan_combo.currentText()
        if not current:
            return
        if len(self.config.task_plans) <= 1:
            QMessageBox.information(self, "不能删除", "至少需要保留一个方案")
            return
        choice = QMessageBox.question(self, "删除方案", f"确定移除方案“{current}”吗？")
        if choice != QMessageBox.Yes:
            return
        removed = self.config.remove_task_plan(current)
        if removed:
            self._populate_task_selectors()
            self._populate_flow(self.config.normalized_flow())
            self._refresh_window_list()
            self.log(f"已删除方案: {removed.name}")

    def add_task(self) -> None:
        self._persist_current_flow_to_selected_task()
        plan_name = self.plan_combo.currentText()
        if not plan_name:
            QMessageBox.information(self, "没有方案", "请先新增一个方案")
            return
        name, ok = QInputDialog.getText(self, "新增任务", "任务名称", text="新任务")
        if not ok:
            return
        task = self.config.add_task(plan_name, name)
        self._populate_task_selectors()
        self._populate_flow(task.flow)
        self.log(f"已新增任务: {task.name}")

    def copy_task(self) -> None:
        self._persist_current_flow_to_selected_task()
        plan_name = self.plan_combo.currentText()
        task_name = self.task_combo.currentText()
        if not plan_name or not task_name:
            QMessageBox.information(self, "没有任务", "请先选择一个任务")
            return
        name, ok = QInputDialog.getText(self, "复制任务", "新任务名称", text=f"{task_name} 副本")
        if not ok:
            return
        task = self.config.copy_task(plan_name, task_name, name)
        self._populate_task_selectors()
        self._populate_flow(task.flow)
        self.log(f"已复制任务: {task.name}")

    def delete_task(self) -> None:
        self._persist_current_flow_to_selected_task()
        plan_name = self.plan_combo.currentText()
        task_name = self.task_combo.currentText()
        plan = self._selected_plan()
        if not plan_name or not task_name:
            return
        if not plan or len(plan.tasks) <= 1:
            QMessageBox.information(self, "不能删除", "每个方案至少需要保留一个任务")
            return
        choice = QMessageBox.question(self, "删除任务", f"确定移除任务“{task_name}”吗？")
        if choice != QMessageBox.Yes:
            return
        removed = self.config.remove_task(plan_name, task_name)
        if removed:
            self._populate_task_selectors()
            self._populate_flow(self.config.normalized_flow())
            self._refresh_window_list()
            self.log(f"已删除任务: {removed.name}")

    def add_flow_step(self) -> None:
        flow = self._read_flow_table()
        current = self.flow_table.currentRow()
        insert_at = current + 1 if current >= 0 else len(flow)
        flow.insert(insert_at, FlowStep(name="新步骤", on_not_found="skip"))
        self._populate_flow(flow)
        self.flow_table.selectRow(insert_at)
        self.config = self.read_config_from_ui()
        self.log("已新增步骤")

    def delete_flow_step(self) -> None:
        current = self.flow_table.currentRow()
        if current < 0:
            QMessageBox.information(self, "请选择步骤", "请先在流程表里选择一个步骤")
            return
        flow = self._read_flow_table()
        if current >= len(flow):
            return
        removed = flow.pop(current)
        self._populate_flow(flow)
        if flow:
            self.flow_table.selectRow(min(current, len(flow) - 1))
        self.config = self.read_config_from_ui()
        self.log(f"已删除步骤: {removed.name}")

    def move_flow_step(self, direction: int) -> None:
        current = self.flow_table.currentRow()
        if current < 0:
            QMessageBox.information(self, "请选择步骤", "请先在流程表里选择一个步骤")
            return
        target = current + direction
        flow = self._read_flow_table()
        if target < 0 or target >= len(flow):
            return
        flow[current], flow[target] = flow[target], flow[current]
        self._populate_flow(flow)
        self.flow_table.selectRow(target)
        self.config = self.read_config_from_ui()
        self.log("已调整步骤顺序")

    def _flow_cell_double_clicked(self, row: int, column: int) -> None:
        if column == 2:
            self.edit_step_templates(row)

    def edit_selected_step_templates(self) -> None:
        current = self.flow_table.currentRow()
        if current < 0:
            QMessageBox.information(self, "请选择步骤", "请先在流程表里选择一个步骤")
            return
        self.edit_step_templates(current)

    def edit_step_templates(self, row: int) -> None:
        if row < 0 or row >= self.flow_table.rowCount():
            return
        step_name = self._cell(row, 1)
        dialog = StepTemplateDialog(step_name, self._cell_templates(row, 2), self)
        if dialog.exec_() != QDialog.Accepted:
            return
        templates = dialog.templates()
        item = QTableWidgetItem(_template_group_summary(templates))
        item.setData(Qt.UserRole, templates)
        item.setToolTip("|".join(templates))
        self.flow_table.setItem(row, 2, item)
        if row == self.flow_table.currentRow():
            self._load_step_detail(row)
        self.config = self.read_config_from_ui()
        self.log(f"已更新步骤模板组: {step_name or row + 1}")

    def select_step_roi(self) -> None:
        if not self.backend:
            return
        hwnd = self._selected_hwnd()
        if hwnd is None:
            QMessageBox.information(self, "请选择窗口", "请先选择一个窗口")
            return
        row = self.flow_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "请选择流程步骤", "请先选择一个流程步骤")
            return
        try:
            image = self.backend.capture_window_foreground(hwnd)
        except Exception:
            QMessageBox.warning(self, "窗口截图失败", "窗口截图失败，请确认窗口未最小化")
            return
        initial_roi = self._current_row_roi(row)
        dialog = RoiSelectionDialog(image, self.backend.cv2, initial_roi, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        roi = dialog.selected_roi()
        if not roi:
            return
        self._set_step_roi(row, roi)
        self.log(f"选择ROI: hwnd {hwnd}，窗口 {self._window_title(hwnd)}，步骤 {self._cell(row, 1)}，ROI {format_roi(roi)}")

    def auto_generate_step_roi(self) -> None:
        if not self.backend:
            return
        hwnd = self._selected_hwnd()
        if hwnd is None:
            QMessageBox.information(self, "请选择窗口", "请先选择一个窗口")
            return
        row = self.flow_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "请选择流程步骤", "请先选择一个流程步骤")
            return
        templates = self._cell_templates(row, 2)
        if not templates:
            QMessageBox.information(self, "没有模板", "当前步骤没有模板，无法自动生成 ROI")
            return
        try:
            image = self.backend.capture_window(hwnd)
        except Exception:
            QMessageBox.warning(self, "窗口截图失败", "窗口截图失败，请确认窗口未最小化")
            return
        thresholds = [self.threshold_spin.value()]
        lowered = max(0.1, thresholds[0] - 0.06)
        if lowered not in thresholds:
            thresholds.append(lowered)
        step = self._read_step_row(row)
        original_threshold = step.threshold
        for threshold in thresholds:
            step.threshold = threshold
            recognition = recognize_step(self.backend, hwnd, self.config, step, mode="roi")
            if not recognition.success:
                continue
            width = recognition.width
            height = recognition.height
            if width <= 0 or height <= 0:
                continue
            left = recognition.x - width // 2
            top = recognition.y - height // 2
            roi = auto_roi_from_match(left, top, width, height, image.shape[1], image.shape[0])
            step.threshold = original_threshold
            self._set_step_roi(row, roi)
            message = f"自动生成 ROI 成功:\n模板: {recognition.template_name}\nROI: {format_roi(roi)}"
            QMessageBox.information(self, "自动生成 ROI 成功", message)
            self.log(recognition.log_message("自动生成ROI", hwnd, self._window_title(hwnd), step.name, templates))
            self.log(f"自动生成 ROI 成功: 模板 {recognition.template_name}, ROI {format_roi(roi)}")
            return
        step.threshold = original_threshold
        QMessageBox.information(
            self,
            "自动生成 ROI 失败",
            "当前步骤模板未识别成功，无法自动生成 ROI。\n请确认模板是否正确，或使用“选择ROI区域”手动框选。",
        )

    def clear_step_roi(self) -> None:
        row = self.flow_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "请选择流程步骤", "请先选择一个流程步骤")
            return
        self._set_step_roi(row, None)
        self.log("已清空当前步骤 ROI，恢复全窗口识别")

    def _current_row_roi(self, row: int) -> list[int] | None:
        try:
            return parse_roi(self._cell(row, 3))
        except ValueError:
            return None

    def _set_step_roi(self, row: int, roi: list[int] | None) -> None:
        value = format_roi(roi) if roi else ""
        self.flow_table.setItem(row, 3, QTableWidgetItem(value))
        if row == self.flow_table.currentRow():
            self._load_step_detail(row)
        self.config = self.read_config_from_ui()

    def _window_title(self, hwnd: int) -> str:
        window = next((candidate for candidate in self.windows if candidate.hwnd == hwnd), None)
        return window.title if window else ""

    def _refresh_flow_path_summary(self) -> None:
        names = [self._cell(row, 1) for row in range(self.flow_table.rowCount()) if self._cell(row, 1)]
        if not names:
            self.flow_path_label.setText("流程路径: 未配置步骤")
            return
        preview = " -> ".join(names[:8])
        if len(names) > 8:
            preview = f"{preview} -> ... 共 {len(names)} 步"
        self.flow_path_label.setText(f"流程路径: {preview}")

    def scan_windows(self) -> None:
        if not self.backend:
            return
        keyword = self.keyword_edit.text().strip() or "斗罗大陆H5"
        existing_manual = [window for window in self.windows if not self._window_matches_keyword(window, keyword)]
        scanned = self.backend.find_windows(keyword)
        known_hwnds = {window.hwnd for window in scanned}
        self.windows = scanned + [window for window in existing_manual if window.hwnd not in known_hwnds]
        self._refresh_window_list()
        scanned_count = len(scanned)
        self.log(f"扫描完成: 找到 {scanned_count} 个窗口，当前列表 {len(self.windows)} 个")

    def _window_matches_keyword(self, window: GameWindow, keyword: str) -> bool:
        return keyword.lower() in window.title.lower()

    def _refresh_window_list(self) -> None:
        self.window_list.clear()
        refreshed_assignments: dict[int, tuple[str, str]] = {}
        for window in self.windows:
            binding = self.config.window_task_bindings.get(window.title)
            if binding:
                refreshed_assignments[window.hwnd] = (binding[0], binding[1])
            elif window.hwnd in self.window_task_assignments and self._task_exists(*self.window_task_assignments[window.hwnd]):
                refreshed_assignments[window.hwnd] = self.window_task_assignments[window.hwnd]
        self.window_task_assignments = refreshed_assignments
        for window in self.windows:
            item = QListWidgetItem(self._window_label(window))
            item.setData(Qt.UserRole, window.hwnd)
            self.window_list.addItem(item)
        if not self.windows:
            item = QListWidgetItem("暂无窗口，请点击扫描窗口或拖动准星绑定窗口")
            item.setFlags(Qt.NoItemFlags)
            self.window_list.addItem(item)
            self.window_count_label.setText("未添加窗口")
        else:
            self.window_count_label.setText(f"已列出 {len(self.windows)} 个窗口")
        self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        self.bound_count_label.setText(f"已绑定: {len(self.windows)}")
        self.running_count_label.setText(f"运行中: {len(self.running_hwnds)}")
        self.exception_count_label.setText(f"异常: {len(self.exception_hwnds)}")

    def _task_exists(self, plan_name: str, task_name: str) -> bool:
        for plan in self.config.task_plans:
            if plan.name != plan_name:
                continue
            return any(task.name == task_name for task in plan.tasks)
        return False

    def remove_selected_window(self) -> None:
        items = self.window_list.selectedItems()
        if not items:
            return
        hwnds = {int(item.data(Qt.UserRole)) for item in items}
        removed_titles = [window.title for window in self.windows if window.hwnd in hwnds]
        self.windows = [window for window in self.windows if window.hwnd not in hwnds]
        for hwnd in hwnds:
            self.window_task_assignments.pop(hwnd, None)
        for title in removed_titles:
            self.config.window_task_bindings.pop(title, None)
        self._refresh_window_list()
        self.log(f"已移除 {len(hwnds)} 个窗口，不会影响真实游戏窗口")

    def show_window_context_menu(self, position) -> None:
        item = self.window_list.itemAt(position)
        if item is None:
            return
        self.window_list.setCurrentItem(item)
        menu = QMenu(self)
        assign_action = menu.addAction("批量分配当前任务")
        remove_action = menu.addAction("从列表移除")
        selected = menu.exec_(self.window_list.mapToGlobal(position))
        if selected == assign_action:
            self.assign_current_task_to_window()
        elif selected == remove_action:
            self.remove_selected_window()

    def assign_current_task_to_window(self) -> None:
        items = self.window_list.selectedItems()
        if not items:
            QMessageBox.information(self, "请选择窗口", "请先选择一个窗口")
            return
        hwnds = {int(item.data(Qt.UserRole)) for item in items}
        plan_task = (self.plan_combo.currentText(), self.task_combo.currentText())
        for hwnd in hwnds:
            self.window_task_assignments[hwnd] = plan_task
            window = next((candidate for candidate in self.windows if candidate.hwnd == hwnd), None)
            if window:
                self.config.window_task_bindings[window.title] = [plan_task[0], plan_task[1]]
        self._refresh_window_list()
        self.log(f"已为 {len(hwnds)} 个窗口分配任务: {plan_task[0]} / {plan_task[1]}")

    def add_window_manually(self) -> None:
        hwnd_text, ok = QInputDialog.getText(self, "手动添加窗口", "请输入窗口 hwnd，例如 123456")
        if not ok or not hwnd_text.strip():
            return
        try:
            hwnd = int(hwnd_text.strip(), 0)
        except ValueError:
            QMessageBox.warning(self, "hwnd 无效", "请输入数字 hwnd")
            return
        title, ok = QInputDialog.getText(self, "窗口备注", "请输入窗口标题或备注", text=f"手动窗口 {hwnd}")
        if not ok:
            return
        window = GameWindow(hwnd=hwnd, title=title.strip() or f"手动窗口 {hwnd}")
        self._add_or_update_window(window)
        self.log(f"已手动添加窗口 {hwnd}")

    def bind_window_from_point(self, point: QPoint) -> None:
        if not self.backend:
            return
        window = self.backend.window_from_point(point.x(), point.y())
        if not window:
            QMessageBox.warning(self, "绑定失败", "没有识别到有效窗口")
            return
        self._add_or_update_window(window)
        self.log(f"已通过拖拽绑定窗口 {window.hwnd}: {window.title}")

    def _add_or_update_window(self, window: GameWindow) -> None:
        for index, existing in enumerate(self.windows):
            if existing.hwnd == window.hwnd:
                self.windows[index] = window
                break
        else:
            self.windows.append(window)
        plan_task = (self.plan_combo.currentText(), self.task_combo.currentText())
        self.window_task_assignments[window.hwnd] = plan_task
        self.config.window_task_bindings[window.title] = [plan_task[0], plan_task[1]]
        self._refresh_window_list()
        self._select_window(window.hwnd)

    def _select_window(self, hwnd: int) -> None:
        self.window_list.clearSelection()
        for row in range(self.window_list.count()):
            item = self.window_list.item(row)
            if int(item.data(Qt.UserRole)) == hwnd:
                item.setSelected(True)
                self.window_list.setCurrentItem(item)
                self.window_list.scrollToItem(item)
                return

    def _window_label(self, window: GameWindow) -> str:
        plan, task = self.window_task_assignments.get(window.hwnd, (self.config.selected_plan, self.config.selected_task))
        return f"{window.hwnd} | {window.title}\n  任务: {plan} / {task}"

    def _window_task_bindings_from_ui(self) -> dict[str, list[str]]:
        bindings = dict(self.config.window_task_bindings)
        for window in self.windows:
            if window.hwnd in self.window_task_assignments:
                plan, task = self.window_task_assignments[window.hwnd]
                bindings[window.title] = [plan, task]
        return bindings

    def capture_template(self, add_to_list: StepTemplateDialog | None = None) -> None:
        if not self.backend:
            return
        hwnd = self._selected_hwnd()
        if hwnd is None:
            QMessageBox.information(self, "请选择窗口", "请先在左侧选择一个游戏窗口")
            return
        try:
            image = self.backend.capture_window_foreground(hwnd)
            dialog = CropDialog(image, self.backend.cv2, self)
            if dialog.exec_() != QDialog.Accepted:
                return
            rect = dialog.selected_rect()
            if not rect:
                return
            name, ok = QInputDialog.getText(self, "模板名称", "保存为文件名，例如 boss.png", text=self._default_capture_template_name())
            if not ok or not name.strip():
                return
            filename = _normalize_template_filename(name.strip())
            path = resolve_templates_dir(self.config) / filename
            self.backend.save_crop(image, rect, path)
            if add_to_list is not None:
                add_to_list.add_template(filename)
            self.log(f"模板已保存: {path}")
        except Exception as exc:
            QMessageBox.warning(self, "截图/裁剪失败", str(exc))
            self.log(f"截图/裁剪失败: {exc}")

    def _default_capture_template_name(self) -> str:
        row = self.flow_table.currentRow()
        if row >= 0:
            step_name = _safe_filename_stem(self._cell(row, 1))
            if step_name:
                return f"{step_name}.png"
        return "template.png"

    def save_current_config(self) -> None:
        self.config = self.read_config_from_ui()
        save_config(CONFIG_PATH, self.config)
        self.log(f"配置已保存: {CONFIG_PATH}")

    def probe_selected_step_template(self) -> None:
        if not self.backend:
            return
        hwnd = self._selected_hwnd()
        if hwnd is None:
            QMessageBox.information(self, "请选择窗口", "请先在左侧选择一个游戏窗口")
            return
        row = self.flow_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "请选择步骤", "请先在流程表里选中要测试的步骤")
            return
        try:
            step = self._read_step_row(row)
            config = self.read_config_from_ui()
            self.log(f"窗口 {hwnd}: 测试识别 {step.name}")
            result = probe_step_templates_in_window(self.backend, hwnd, config, step)
            self.log(f"窗口 {hwnd}: {result.message}")
        except Exception as exc:
            QMessageBox.warning(self, "测试识别失败", str(exc))
            self.log(f"测试识别失败: {exc}")

    def import_panda_templates(self) -> None:
        source, _filter = QFileDialog.getOpenFileName(self, "选择熊猫精灵导出脚本", "", "Text Files (*.txt);;All Files (*)")
        if not source:
            return
        try:
            output_dir = resolve_templates_dir(self.config) / "imported"
            written = export_panda_templates(Path(source), output_dir)
            self.log(f"已导入 {len(written)} 张模板到 {output_dir}")
            QMessageBox.information(self, "导入完成", f"已导入 {len(written)} 张模板")
        except Exception as exc:
            self.log(f"导入失败: {exc}")
            QMessageBox.warning(self, "导入失败", str(exc))

    def test_selected(self) -> None:
        hwnd = self._selected_hwnd()
        if hwnd is None:
            QMessageBox.information(self, "请选择窗口", "请先选择一个窗口")
            return
        self._start_worker([hwnd])

    def start_all(self) -> None:
        self._start_worker([window.hwnd for window in self.windows])

    def _start_worker(self, hwnds: list[int]) -> None:
        if not self.backend:
            return
        if self.worker and self.worker.is_alive():
            QMessageBox.information(self, "正在运行", "当前任务还在运行")
            return
        if not hwnds:
            QMessageBox.information(self, "没有窗口", "未找到可运行的游戏窗口")
            return
        self.config = self.read_config_from_ui()
        save_config(CONFIG_PATH, self.config)
        self.stop_event.clear()
        self.pause_event.clear()
        self.running_hwnds = set()
        self.exception_hwnds = set()
        self._refresh_status_bar()
        self.status_label.setText(f"运行中: {len(hwnds)} 个窗口")
        self.worker = threading.Thread(target=self._run_worker, args=(hwnds,), daemon=True)
        self.worker.start()
        self.log(f"准备并发运行 {len(hwnds)} 个窗口")

    def _run_worker(self, hwnds: list[int]) -> None:
        threads = []
        start_event = threading.Event()
        for hwnd in hwnds:
            thread = threading.Thread(target=self._run_window_worker, args=(hwnd, start_event), daemon=True)
            thread.start()
            threads.append(thread)
        self.log_signal.emit(f"并发启动 {len(threads)} 个窗口")
        start_event.set()
        for thread in threads:
            thread.join()
        self.finished_signal.emit()

    def _run_window_worker(self, hwnd: int, start_event: threading.Event) -> None:
        if self.stop_event.is_set():
            return
        plan, task = self.window_task_assignments.get(hwnd, (self.config.selected_plan, self.config.selected_task))
        try:
            backend = Win32Automation()
        except DependencyError as exc:
            self.log_signal.emit(f"窗口 {hwnd}: 后端初始化失败: {exc}")
            self.window_finished_signal.emit(hwnd, False)
            return
        runner = FlowRunner(
            backend,
            self.config.for_task(plan, task),
            self.log_signal.emit,
            should_stop=self.stop_event.is_set,
            should_pause=self.pause_event.is_set,
        )
        start_event.wait()
        self.window_started_signal.emit(hwnd)
        self.log_signal.emit(f"窗口 {hwnd}: 使用任务 {plan} / {task}")
        ok = False
        try:
            result = runner.run_window(hwnd)
            ok = result.ok
            self.log_signal.emit(f"窗口 {hwnd}: {result.message}")
        finally:
            shutdown = getattr(backend, "shutdown", None)
            if shutdown:
                shutdown()
            self.window_finished_signal.emit(hwnd, ok)

    def toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.setText("暂停")
            self.status_label.setText("运行中")
            self.log("继续运行")
        else:
            self.pause_event.set()
            self.pause_button.setText("继续")
            self.status_label.setText("已暂停")
            self.log("已暂停")

    def stop(self) -> None:
        self.stop_event.set()
        self.pause_event.clear()
        self.pause_button.setText("暂停")
        self.status_label.setText("正在停止")
        self.log("正在停止")

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{stamp}] {message}")

    def _worker_finished(self) -> None:
        self.pause_button.setText("暂停")
        self.status_label.setText("已停止" if self.stop_event.is_set() else "运行结束")
        self.running_hwnds.clear()
        self._refresh_status_bar()
        self.log("运行结束")

    def _window_started(self, hwnd: int) -> None:
        self.running_hwnds.add(hwnd)
        self._refresh_status_bar()

    def _window_finished(self, hwnd: int, ok: bool) -> None:
        self.running_hwnds.discard(hwnd)
        if not ok:
            self.exception_hwnds.add(hwnd)
        self._refresh_status_bar()

    def _selected_hwnd(self) -> int | None:
        item = self.window_list.currentItem()
        if item is None:
            return None
        hwnd = item.data(Qt.UserRole)
        return int(hwnd) if hwnd is not None else None

    def _cell(self, row: int, column: int) -> str:
        item = self.flow_table.item(row, column)
        return item.text().strip() if item else ""

    def _optional_float(self, value: str) -> float | None:
        return float(value) if value else None

    def _optional_int(self, value: str) -> int | None:
        return int(value) if value else None

    def _optional_roi(self, value: str) -> list[int] | None:
        if not value:
            return None
        parts = [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
        if len(parts) != 4:
            return None
        return [int(part) for part in parts]

    def _split_templates(self, value: str) -> list[str]:
        return [part.strip() for part in value.replace("\n", "|").split("|") if part.strip()]

    def _split_action(self, value: str) -> tuple[str, str]:
        if ":" not in value:
            return value or "fail", ""
        action, target = value.split(":", 1)
        return action.strip() or "fail", target.strip()


def _normalize_template_filename(name: str) -> str:
    path = Path(name.strip())
    if path.suffix.lower() in TEMPLATE_EXTENSIONS:
        return str(path)
    return f"{name.strip()}.png"


def _template_group_summary(templates: list[str]) -> str:
    if not templates:
        return ""
    first = templates[0]
    if len(templates) == 1:
        return first
    return f"{first} 等 {len(templates)} 张"


def _safe_filename_stem(value: str) -> str:
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if char in invalid or ord(char) < 32 else char for char in value.strip())
    return cleaned.strip(" .")


def run_app() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()
