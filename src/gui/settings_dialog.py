# -*- coding: utf-8 -*-
"""
设置对话框
用于配置应用程序的各种参数
"""

from loguru import logger
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.config_manager import ConfigManager, ErrorHandling, HashAlgorithm


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(500, 600)

        # 主布局
        layout = QVBoxLayout(self)

        # 创建选项卡
        self.tab_widget = QTabWidget()

        # 哈希算法选项卡
        self.create_hash_tab()

        # 检测设置选项卡
        self.create_detection_tab()

        # 应用程序设置选项卡
        self.create_app_tab()

        # 高级设置选项卡
        self.create_advanced_tab()

        layout.addWidget(self.tab_widget)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        button_box.accepted.connect(self.accept_settings)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply_settings)

        layout.addWidget(button_box)

    def create_hash_tab(self):
        """创建哈希算法设置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 算法选择组
        algo_group = QGroupBox("图片哈希算法")
        algo_layout = QFormLayout(algo_group)

        self.hash_algorithm_combo = QComboBox()
        for algo in HashAlgorithm:
            self.hash_algorithm_combo.addItem(
                self._get_algorithm_display_name(algo), algo.value
            )

        algo_layout.addRow("算法类型:", self.hash_algorithm_combo)

        # 算法说明
        algo_info = QTextEdit()
        algo_info.setMaximumHeight(100)
        algo_info.setReadOnly(True)
        algo_info.setText(
            "• Average Hash: 平均哈希，速度快，适合检测明显的重复\n"
            "• Perceptual Hash: 感知哈希，平衡速度和准确性，推荐使用\n"
            "• Difference Hash: 差异哈希，对旋转敏感\n"
            "• Wavelet Hash: 小波哈希，最准确但速度较慢"
        )
        algo_layout.addRow("说明:", algo_info)

        layout.addWidget(algo_group)

        # 相似度阈值组
        threshold_group = QGroupBox("相似度阈值")
        threshold_layout = QFormLayout(threshold_group)

        self.threshold_spinboxes = {}
        for algo in HashAlgorithm:
            spinbox = QSpinBox()
            spinbox.setRange(0, 20)
            spinbox.setSuffix(" (越小越严格)")
            self.threshold_spinboxes[algo] = spinbox
            threshold_layout.addRow(
                f"{self._get_algorithm_display_name(algo)}:", spinbox
            )

        layout.addWidget(threshold_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "哈希算法")

    def create_detection_tab(self):
        """创建检测设置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 重复检测组
        detection_group = QGroupBox("重复检测设置")
        detection_layout = QFormLayout(detection_group)

        self.min_similar_images_spinbox = QSpinBox()
        self.min_similar_images_spinbox.setRange(1, 100)
        self.min_similar_images_spinbox.setSuffix(" 张")
        detection_layout.addRow("最小相似图片数量:", self.min_similar_images_spinbox)

        layout.addWidget(detection_group)

        # 图片过滤组
        filter_group = QGroupBox("图片过滤设置")
        filter_layout = QFormLayout(filter_group)

        self.min_width_spinbox = QSpinBox()
        self.min_width_spinbox.setRange(1, 2147483647)
        self.min_width_spinbox.setSuffix(" 像素")
        filter_layout.addRow("最小图片宽度:", self.min_width_spinbox)
        self.min_width_spinbox.setDisabled(True)

        self.min_height_spinbox = QSpinBox()
        self.min_height_spinbox.setRange(1, 2147483647)
        self.min_height_spinbox.setSuffix(" 像素")
        filter_layout.addRow("最小图片高度:", self.min_height_spinbox)
        self.min_height_spinbox.setDisabled(True)

        # 漫画图片数量范围
        self.min_image_count_spinbox = QSpinBox()
        self.min_image_count_spinbox.setRange(1, 2147483647)
        self.min_image_count_spinbox.setSuffix(" 张")
        filter_layout.addRow("漫画最小图片数量:", self.min_image_count_spinbox)

        self.max_image_count_spinbox = QSpinBox()
        self.max_image_count_spinbox.setRange(0, 2147483647)
        self.max_image_count_spinbox.setSuffix(" 张 (0表示无限制)")
        filter_layout.addRow("漫画最大图片数量:", self.max_image_count_spinbox)

        layout.addWidget(filter_group)

        # 支持格式组
        format_group = QGroupBox("支持的文件格式")
        format_layout = QVBoxLayout(format_group)

        format_info = QLabel(
            "压缩包格式: ZIP, RAR, CBR, CBZ\n图片格式: JPG, PNG, GIF, BMP, WEBP"
        )
        format_info.setWordWrap(True)
        format_layout.addWidget(format_info)

        layout.addWidget(format_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "检测设置")

    def create_app_tab(self):
        """创建应用程序设置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 外部程序组
        external_group = QGroupBox("外部程序")
        external_layout = QFormLayout(external_group)

        # 漫画查看器
        viewer_layout = QHBoxLayout()
        self.comic_viewer_edit = QLineEdit()
        self.comic_viewer_edit.setPlaceholderText("留空使用系统默认程序")

        viewer_browse_btn = QPushButton("浏览...")
        viewer_browse_btn.clicked.connect(self.browse_comic_viewer)

        viewer_layout.addWidget(self.comic_viewer_edit)
        viewer_layout.addWidget(viewer_browse_btn)

        external_layout.addRow("漫画查看器路径:", viewer_layout)

        # 漫画查看器参数
        args_layout = QHBoxLayout()
        self.comic_viewer_args_edit = QLineEdit()
        self.comic_viewer_args_edit.setPlaceholderText("可选参数，支持占位符")

        # 帮助按钮
        help_btn = QPushButton("?")
        help_btn.setFixedSize(25, 25)
        help_btn.setToolTip("点击查看占位符说明")
        help_btn.clicked.connect(self.show_args_help)

        args_layout.addWidget(self.comic_viewer_args_edit)
        args_layout.addWidget(help_btn)
        external_layout.addRow("漫画查看器参数:", args_layout)

        layout.addWidget(external_group)

        # 错误处理组
        error_group = QGroupBox("错误处理")
        error_layout = QFormLayout(error_group)

        self.error_handling_combo = QComboBox()
        for handling in ErrorHandling:
            self.error_handling_combo.addItem(
                self._get_error_handling_display_name(handling), handling.value
            )
        self.error_handling_combo.setDisabled(True)

        error_layout.addRow("遇到错误时:", self.error_handling_combo)

        layout.addWidget(error_group)

        # 界面设置组
        ui_group = QGroupBox("界面设置")
        ui_layout = QFormLayout(ui_group)

        self.window_width_spinbox = QSpinBox()
        self.window_width_spinbox.setRange(800, 2560)
        self.window_width_spinbox.setSuffix(" 像素")
        ui_layout.addRow("窗口宽度:", self.window_width_spinbox)

        self.window_height_spinbox = QSpinBox()
        self.window_height_spinbox.setRange(600, 1440)
        self.window_height_spinbox.setSuffix(" 像素")
        ui_layout.addRow("窗口高度:", self.window_height_spinbox)

        self.preview_width_spinbox = QSpinBox()
        self.preview_width_spinbox.setRange(100, 500)
        self.preview_width_spinbox.setSuffix(" 像素")
        ui_layout.addRow("预览图宽度:", self.preview_width_spinbox)

        self.preview_height_spinbox = QSpinBox()
        self.preview_height_spinbox.setRange(100, 500)
        self.preview_height_spinbox.setSuffix(" 像素")
        ui_layout.addRow("预览图高度:", self.preview_height_spinbox)

        layout.addWidget(ui_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "应用程序")

    def create_advanced_tab(self):
        """创建高级设置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 性能设置组
        performance_group = QGroupBox("性能设置")
        performance_layout = QFormLayout(performance_group)

        self.max_workers_spinbox = QSpinBox()
        self.max_workers_spinbox.setRange(1, 16)
        self.max_workers_spinbox.setSuffix(" 个线程")
        performance_layout.addRow("最大工作线程数:", self.max_workers_spinbox)

        layout.addWidget(performance_group)

        # 缓存设置组
        cache_group = QGroupBox("缓存设置")
        cache_layout = QFormLayout(cache_group)

        self.enable_cache_checkbox = QCheckBox("启用结果缓存")
        cache_layout.addRow(self.enable_cache_checkbox)

        # 缓存目录
        cache_dir_layout = QHBoxLayout()
        self.cache_dir_edit = QLineEdit()

        cache_dir_browse_btn = QPushButton("浏览...")
        cache_dir_browse_btn.clicked.connect(self.browse_cache_dir)

        cache_dir_layout.addWidget(self.cache_dir_edit)
        cache_dir_layout.addWidget(cache_dir_browse_btn)

        cache_layout.addRow("缓存目录:", cache_dir_layout)

        layout.addWidget(cache_group)

        # 黑名单设置组
        blacklist_group = QGroupBox("黑名单设置")
        blacklist_layout = QFormLayout(blacklist_group)

        # 黑名单文件
        blacklist_folder_layout = QHBoxLayout()
        self.blacklist_folder_edit = QLineEdit()

        blacklist_folder_browse_btn = QPushButton("浏览...")
        blacklist_folder_browse_btn.clicked.connect(self.browse_blacklist_file)

        blacklist_folder_layout.addWidget(self.blacklist_folder_edit)
        blacklist_folder_layout.addWidget(blacklist_folder_browse_btn)

        blacklist_layout.addRow("黑名单文件夹:", blacklist_folder_layout)

        layout.addWidget(blacklist_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "高级设置")

    def load_settings(self):
        """加载当前设置"""
        # 哈希算法
        current_algo = self.config.get_hash_algorithm()
        index = self.hash_algorithm_combo.findData(current_algo.value)
        if index >= 0:
            self.hash_algorithm_combo.setCurrentIndex(index)

        # 相似度阈值
        for algo, spinbox in self.threshold_spinboxes.items():
            threshold = self.config.get_similarity_threshold(algo)
            spinbox.setValue(threshold)

        # 检测设置
        self.min_similar_images_spinbox.setValue(self.config.get_min_similar_images())

        min_width, min_height = self.config.get_min_image_resolution()
        self.min_width_spinbox.setValue(min_width)
        self.min_height_spinbox.setValue(min_height)

        min_image_count, max_image_count = self.config.get_comic_image_count_range()
        self.min_image_count_spinbox.setValue(min_image_count)
        self.max_image_count_spinbox.setValue(
            max_image_count if max_image_count is not None else 0
        )

        # 应用程序设置
        self.comic_viewer_edit.setText(self.config.get_comic_viewer_path())
        self.comic_viewer_args_edit.setText(self.config.get_comic_viewer_args())

        current_error_handling = self.config.get_error_handling()
        index = self.error_handling_combo.findData(current_error_handling.value)
        if index >= 0:
            self.error_handling_combo.setCurrentIndex(index)

        # 界面设置
        window_width, window_height = self.config.get_window_geometry()
        self.window_width_spinbox.setValue(window_width)
        self.window_height_spinbox.setValue(window_height)

        preview_width, preview_height = self.config.get_preview_size()
        self.preview_width_spinbox.setValue(preview_width)
        self.preview_height_spinbox.setValue(preview_height)

        # 高级设置
        self.max_workers_spinbox.setValue(self.config.get_max_workers())
        self.enable_cache_checkbox.setChecked(self.config.is_cache_enabled())
        self.cache_dir_edit.setText(self.config.get_cache_dir())
        self.blacklist_folder_edit.setText(self.config.get_blacklist_folder())

    def apply_settings(self):
        """应用设置"""
        try:
            # 哈希算法
            algo_value = self.hash_algorithm_combo.currentData()
            self.config.set("hash_algorithm", algo_value)

            # 相似度阈值
            for algo, spinbox in self.threshold_spinboxes.items():
                self.config.set(f"similarity_thresholds.{algo.value}", spinbox.value())

            # 检测设置
            self.config.set(
                "min_similar_images", self.min_similar_images_spinbox.value()
            )
            self.config.set(
                "min_image_resolution.width", self.min_width_spinbox.value()
            )
            self.config.set(
                "min_image_resolution.height", self.min_height_spinbox.value()
            )

            # 漫画图片数量范围
            min_count = self.min_image_count_spinbox.value()
            max_count = self.max_image_count_spinbox.value()
            self.config.set("comic_image_count_range.min", min_count)
            self.config.set(
                "comic_image_count_range.max", max_count if max_count != 0 else None
            )

            # 应用程序设置
            self.config.set("comic_viewer_path", self.comic_viewer_edit.text())
            self.config.set("comic_viewer_args", self.comic_viewer_args_edit.text())

            error_handling_value = self.error_handling_combo.currentData()
            self.config.set("error_handling", error_handling_value)

            # 界面设置
            self.config.set("window_geometry.width", self.window_width_spinbox.value())
            self.config.set(
                "window_geometry.height", self.window_height_spinbox.value()
            )
            self.config.set("preview_size.width", self.preview_width_spinbox.value())
            self.config.set("preview_size.height", self.preview_height_spinbox.value())

            # 高级设置
            self.config.set("max_workers", self.max_workers_spinbox.value())
            self.config.set("enable_cache", self.enable_cache_checkbox.isChecked())
            self.config.set("cache_dir", self.cache_dir_edit.text())
            self.config.set("blacklist_file", self.blacklist_folder_edit.text())

            # 保存配置
            self.config.save_config()

            logger.info("设置已保存")

        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存设置失败: {e}")

    def accept_settings(self):
        """接受并应用设置"""
        self.apply_settings()
        self.accept()

    def browse_comic_viewer(self):
        """浏览漫画查看器"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择漫画查看器", "", "可执行文件 (*.exe);;所有文件 (*.*)"
        )

        if file_path:
            file_path = file_path.replace("/", "\\")
            self.comic_viewer_edit.setText(file_path)

    def browse_cache_dir(self):
        """浏览缓存目录"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择缓存目录", self.cache_dir_edit.text()
        )

        if directory:
            directory = directory.replace("/", "\\")
            self.cache_dir_edit.setText(directory)

    def browse_blacklist_file(self):
        """浏览黑名单文件夹"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择黑名单文件夹", self.blacklist_folder_edit.text()
        )

        if directory:
            directory = directory.replace("/", "\\")
            self.blacklist_folder_edit.setText(directory)

    def _get_algorithm_display_name(self, algorithm: HashAlgorithm) -> str:
        """获取算法显示名称"""
        names = {
            HashAlgorithm.AVERAGE: "平均哈希 (Average Hash)",
            HashAlgorithm.PERCEPTUAL: "感知哈希 (Perceptual Hash)",
            HashAlgorithm.DIFFERENCE: "差异哈希 (Difference Hash)",
            HashAlgorithm.WAVELET: "小波哈希 (Wavelet Hash)",
        }
        return names.get(algorithm, algorithm.value)

    def _get_error_handling_display_name(self, handling: ErrorHandling) -> str:
        """获取错误处理方式显示名称"""
        names = {
            ErrorHandling.ASK: "询问",
            ErrorHandling.SKIP: "跳过",
            ErrorHandling.ABORT: "中止扫描",
        }
        return names.get(handling, handling.value)

    def show_args_help(self):
        """显示参数帮助信息"""
        QMessageBox.information(
            self,
            "参数占位符说明",
            "支持的占位符:\n\n"
            "{page} - 页数（从1开始）\n"
            "{page_index} - 页数（从0开始）\n"
            "{file} - 文件路径，需要用引号括起来\n\n"
            "示例:\n"
            '• 跳转到第N页: "-p {page}"\n'
            '• 使用索引: "-page {page_index}"\n'
            '• 组合使用: "-p {page} "{file}""',
        )
