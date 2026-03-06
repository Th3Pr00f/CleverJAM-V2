#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# CleverJAM - Modified by Medhat
# ✅ Matches original GUI: all 6 sliders + FFT + Max/Min Hold + Average
# ✅ Device Selection Dialog at startup
# ✅ Integrated Auto-Jam panel (clever.py logic built-in)
#
# ⚠️  WARNING: Jamming is illegal. For lab/research use only. ⚠️

import sys
import os
import json
import subprocess
import signal
import threading
import time

import osmosdr
from gnuradio import gr, analog
from gnuradio import qtgui
from gnuradio.fft import window
from PyQt5 import Qt, QtCore, QtWidgets, QtGui
import sip


# ─────────────────────────────────────────────
#  Device Detection
# ─────────────────────────────────────────────

def detect_devices():
    devices = []

    try:
        result = subprocess.run(["hackrf_info"], capture_output=True, text=True, timeout=3)
        if "HackRF" in result.stdout:
            import re
            serial = re.search(r'Serial number: (\S+)', result.stdout)
            fw     = re.search(r'Firmware Version: (\S+)', result.stdout)
            devices.append({
                "label": f"HackRF One  [FW: {fw.group(1) if fw else '?'}]  Serial: {serial.group(1) if serial else 'unknown'}",
                "args": "hackrf=0", "type": "hackrf"
            })
    except Exception:
        pass

    try:
        result = subprocess.run(["rtl_test", "-t"], capture_output=True, text=True, timeout=3)
        if "Found" in result.stderr or "R828D" in result.stderr:
            devices.append({
                "label": "⚠️  RTL-SDR  (RX ONLY — cannot transmit!)",
                "args": "rtl=0", "type": "rtlsdr", "rx_only": True
            })
    except Exception:
        pass

    try:
        result = subprocess.run(["LimeUtil", "--find"], capture_output=True, text=True, timeout=3)
        if "LimeSDR" in result.stdout:
            devices.append({"label": "LimeSDR", "args": "soapy=0,driver=lime", "type": "lime"})
    except Exception:
        pass

    try:
        result = subprocess.run(["bladeRF-cli", "-p"], capture_output=True, text=True, timeout=3)
        if "bladerf" in result.stdout.lower():
            devices.append({"label": "BladeRF", "args": "bladerf=0", "type": "bladerf"})
    except Exception:
        pass

    devices.append({"label": "Manual — enter custom args", "args": "__manual__", "type": "manual"})
    return devices


# ─────────────────────────────────────────────
#  Device Selection Dialog
# ─────────────────────────────────────────────

class DeviceSelectDialog(QtWidgets.QDialog):
    def __init__(self, devices):
        super().__init__()
        self.devices = devices
        self.selected_args  = None
        self.selected_label = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("CleverJAM — Select SDR Device")
        self.setMinimumWidth(540)
        self.setStyleSheet("""
            QDialog        { background:#1a1a2e; color:#eaeaea; font-family:'Courier New',monospace; }
            QLabel#title   { color:#e94560; font-size:18px; font-weight:bold; padding:8px 0; }
            QLabel#sub     { color:#a0a0b0; font-size:11px; padding-bottom:10px; }
            QLabel#warn    { color:#ffcc00; font-size:11px; background:#2a2a1a;
                             padding:6px; border:1px solid #ffcc00; border-radius:4px; }
            QListWidget    { background:#16213e; color:#eaeaea; border:1px solid #0f3460;
                             border-radius:6px; padding:4px; font-size:13px; }
            QListWidget::item:selected { background:#e94560; color:white; }
            QListWidget::item:hover    { background:#0f3460; }
            QLineEdit      { background:#16213e; color:#00ff88; border:1px solid #0f3460;
                             border-radius:4px; padding:5px; }
            QPushButton#go { background:#e94560; color:white; font-weight:bold; font-size:14px;
                             border-radius:6px; padding:10px; border:none; }
            QPushButton#go:hover { background:#c73652; }
            QPushButton#cx { background:#2a2a3e; color:#a0a0b0; font-size:12px;
                             border-radius:6px; padding:8px; border:1px solid #3a3a5e; }
            QPushButton#cx:hover { background:#3a3a5e; }
        """)

        ly = QtWidgets.QVBoxLayout(self)
        ly.setSpacing(10); ly.setContentsMargins(20,20,20,20)

        t = QtWidgets.QLabel("🐇 CleverJAM"); t.setObjectName("title")
        t.setAlignment(QtCore.Qt.AlignCenter); ly.addWidget(t)

        s = QtWidgets.QLabel("Smart SDR Jammer with Frequency Hopping"); s.setObjectName("sub")
        s.setAlignment(QtCore.Qt.AlignCenter); ly.addWidget(s)

        w = QtWidgets.QLabel("⚠️  ILLEGAL on live frequencies — Lab / research use only.")
        w.setObjectName("warn"); w.setAlignment(QtCore.Qt.AlignCenter); ly.addWidget(w)

        lbl = QtWidgets.QLabel("Select SDR Device:")
        lbl.setStyleSheet("color:#a0c4ff; font-weight:bold; margin-top:8px;")
        ly.addWidget(lbl)

        self.lw = QtWidgets.QListWidget()
        tx_found = False
        for i, d in enumerate(self.devices):
            item = QtWidgets.QListWidgetItem(d["label"])
            if d.get("rx_only"):
                item.setForeground(Qt.QColor("#ff6666"))
            elif d["type"] != "manual":
                item.setForeground(Qt.QColor("#00ff88"))
                if not tx_found:
                    self.lw.setCurrentRow(i); tx_found = True
            self.lw.addItem(item)
        if not tx_found:
            self.lw.setCurrentRow(0)
        self.lw.currentRowChanged.connect(self._changed)
        ly.addWidget(self.lw)

        self.manual_lbl = QtWidgets.QLabel("Custom osmosdr args:")
        self.manual_lbl.setStyleSheet("color:#a0c4ff;"); self.manual_lbl.hide(); ly.addWidget(self.manual_lbl)
        self.manual_in  = QtWidgets.QLineEdit()
        self.manual_in.setPlaceholderText("e.g.  hackrf=0   or   soapy=0,driver=lime")
        self.manual_in.hide(); ly.addWidget(self.manual_in)

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("color:#a0a0b0; font-size:11px;")
        self.status.setAlignment(QtCore.Qt.AlignCenter); ly.addWidget(self.status)
        self._changed(self.lw.currentRow())

        bl = QtWidgets.QHBoxLayout()
        cx = QtWidgets.QPushButton("Cancel"); cx.setObjectName("cx"); cx.clicked.connect(self.reject)
        go = QtWidgets.QPushButton("🚀  Launch Jammer"); go.setObjectName("go"); go.clicked.connect(self._go)
        bl.addWidget(cx); bl.addWidget(go); ly.addLayout(bl)

    def _changed(self, idx):
        if idx < 0 or idx >= len(self.devices): return
        d = self.devices[idx]
        manual = d["type"] == "manual"
        self.manual_lbl.setVisible(manual); self.manual_in.setVisible(manual)
        if d.get("rx_only"):
            self.status.setText("⚠️  RTL-SDR cannot transmit!"); self.status.setStyleSheet("color:#ff6666;font-size:11px;")
        elif manual:
            self.status.setText("Enter osmosdr device string manually."); self.status.setStyleSheet("color:#ffcc00;font-size:11px;")
        else:
            self.status.setText(f'✅  TX-capable → args: "{d["args"]}"'); self.status.setStyleSheet("color:#00ff88;font-size:11px;")

    def _go(self):
        idx = self.lw.currentRow()
        if idx < 0: return
        d = self.devices[idx]
        if d["type"] == "manual":
            args = self.manual_in.text().strip()
            if not args:
                QtWidgets.QMessageBox.warning(self, "Missing Input", "Please enter osmosdr args."); return
            self.selected_args = args; self.selected_label = f"Manual: {args}"
        else:
            if d.get("rx_only"):
                r = QtWidgets.QMessageBox.warning(self, "RX Only",
                    "RTL-SDR cannot transmit!\nContinue anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if r != QtWidgets.QMessageBox.Yes: return
            self.selected_args = d["args"]; self.selected_label = d["label"]
        self.accept()


# ─────────────────────────────────────────────
#  Auto-Jam Worker Thread (clever.py logic)
# ─────────────────────────────────────────────

class AutoJamWorker(QtCore.QThread):
    jump_signal   = QtCore.pyqtSignal(str, float, float)   # name, freq, bw
    status_signal = QtCore.pyqtSignal(str)

    def __init__(self, targets, jump_delay):
        super().__init__()
        self.targets    = targets      # list of {"name":..,"freq":..,"bw":..}
        self.jump_delay = jump_delay
        self._stop      = False

    def stop(self):
        self._stop = True

    def run(self):
        idx = 0
        while not self._stop:
            t = self.targets[idx % len(self.targets)]
            self.jump_signal.emit(t["name"], t["freq"], t["bw"])
            self.status_signal.emit(
                f'|JUMP| --- Jamming {t["name"]} frequency at {t["freq"]} with {t["bw"]/1e6:.0f} MHz bandwidth'
            )
            time.sleep(self.jump_delay)
            idx += 1


# ─────────────────────────────────────────────
#  Main Jammer Flowgraph
# ─────────────────────────────────────────────

class CleverJAM(gr.top_block, Qt.QWidget):
    def __init__(self, device_args="hackrf=0"):
        gr.top_block.__init__(self, "Jammer Gen")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Jammer Gen")
        self.device_args = device_args
        self._auto_worker = None

        # ── Variables ──
        self.samp_rate = 20000000
        self.rf_gain   = 47
        self.if_gain   = 40
        self.bb_gain   = 20
        self.freq      = 446000000
        self.bandwidth = 20000000

        # ── Top-level layout — Splitter so everything fits without scrolling ──
        self._main_layout = Qt.QVBoxLayout()
        self._main_layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout.setSpacing(2)
        self.setLayout(self._main_layout)

        # Splitter: top = sliders+FFT, bottom = Auto-Jam panel
        self._splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self._main_layout.addWidget(self._splitter)

        # Top widget (sliders + FFT)
        self.top_widget = Qt.QWidget()
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_layout.setContentsMargins(2, 2, 2, 2)
        self.top_layout.setSpacing(2)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)
        self._splitter.addWidget(self.top_widget)

        # Bottom widget placeholder — filled by _build_autojam_panel()
        self._bottom_widget = Qt.QWidget()
        self._bottom_layout = Qt.QVBoxLayout(self._bottom_widget)
        self._bottom_layout.setContentsMargins(2, 2, 2, 2)
        self._splitter.addWidget(self._bottom_widget)

        # ── Sliders (original order) ──
        self._samp_rate_range = qtgui.Range(1000000, 20000000, 100000, self.samp_rate, 200)
        self._samp_rate_win   = qtgui.RangeWidget(self._samp_rate_range, self.set_samp_rate, "Sample rate", "slider", float)
        self.top_grid_layout.addWidget(self._samp_rate_win, 0, 0, 1, 4)

        self._rf_gain_range = qtgui.Range(0, 47, 1, self.rf_gain, 200)
        self._rf_gain_win   = qtgui.RangeWidget(self._rf_gain_range, self.set_rf_gain, "RF gain", "slider", float)
        self.top_grid_layout.addWidget(self._rf_gain_win, 1, 0, 1, 4)

        self._if_gain_range = qtgui.Range(0, 47, 1, self.if_gain, 200)
        self._if_gain_win   = qtgui.RangeWidget(self._if_gain_range, self.set_if_gain, "IF gain", "slider", float)
        self.top_grid_layout.addWidget(self._if_gain_win, 2, 0, 1, 4)

        self._freq_range = qtgui.Range(70000000, 6000000000, 1000000, self.freq, 200)
        self._freq_win   = qtgui.RangeWidget(self._freq_range, self.set_freq, "Freq", "counter_slider", float)
        self.top_grid_layout.addWidget(self._freq_win, 3, 0, 1, 4)

        self._bb_gain_range = qtgui.Range(0, 62, 2, self.bb_gain, 200)
        self._bb_gain_win   = qtgui.RangeWidget(self._bb_gain_range, self.set_bb_gain, "BB gain", "slider", float)
        self.top_grid_layout.addWidget(self._bb_gain_win, 4, 0, 1, 4)

        self._bandwidth_range = qtgui.Range(1000000, 20000000, 100000, self.bandwidth, 200)
        self._bandwidth_win   = qtgui.RangeWidget(self._bandwidth_range, self.set_bandwidth, "Bandwidth", "slider", float)
        self.top_grid_layout.addWidget(self._bandwidth_win, 5, 0, 1, 4)

        # ── Frequency Display — with control panel (Max Hold / Min Hold / Average) ──
        self.qtgui_freq_sink = qtgui.freq_sink_c(
            1024,
            window.WIN_BLACKMAN_hARRIS,
            self.freq,
            self.samp_rate,
            "Frequency Display",
            1
        )
        self.qtgui_freq_sink.set_update_time(0.10)
        self.qtgui_freq_sink.set_y_axis(-140, 10)
        self.qtgui_freq_sink.set_y_label("Relative Gain", "dB")
        self.qtgui_freq_sink.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink.enable_autoscale(False)
        self.qtgui_freq_sink.enable_grid(False)
        self.qtgui_freq_sink.set_fft_average(1.0)
        self.qtgui_freq_sink.enable_axis_labels(True)
        self.qtgui_freq_sink.enable_control_panel(True)   # ← Max Hold / Min Hold / Average
        self.qtgui_freq_sink.set_line_label(0, "Data 0")
        self.qtgui_freq_sink.set_line_width(0, 1)
        self.qtgui_freq_sink.set_line_color(0, "blue")
        self.qtgui_freq_sink.set_line_alpha(0, 1.0)

        # GNURadio 3.10+ uses qwidget(), older versions use pyqwidget()
        try:
            self._fft_win = sip.wrapinstance(self.qtgui_freq_sink.qwidget(), Qt.QWidget)
        except AttributeError:
            self._fft_win = sip.wrapinstance(self.qtgui_freq_sink.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._fft_win, 6, 0, 4, 4)

        # ── Auto-Jam Panel ──
        self._build_autojam_panel()

        # ── GNURadio blocks ──
        self.noise_source = analog.noise_source_c(analog.GR_GAUSSIAN, 1.0, 0)

        self.osmosdr_sink = osmosdr.sink(args=f"numchan=1 {device_args}")
        self.osmosdr_sink.set_sample_rate(self.samp_rate)
        self.osmosdr_sink.set_center_freq(self.freq, 0)
        self.osmosdr_sink.set_freq_corr(0, 0)
        self.osmosdr_sink.set_gain(self.rf_gain, 0)
        self.osmosdr_sink.set_if_gain(self.if_gain, 0)
        self.osmosdr_sink.set_bb_gain(self.bb_gain, 0)
        self.osmosdr_sink.set_antenna("", 0)
        self.osmosdr_sink.set_bandwidth(self.bandwidth, 0)

        self.connect((self.noise_source, 0), (self.osmosdr_sink, 0))
        self.connect((self.noise_source, 0), (self.qtgui_freq_sink, 0))

        # Set splitter ratio: FFT gets 70%, Auto-Jam gets 30%
        QtCore.QTimer.singleShot(100, lambda: self._splitter.setSizes([700, 300]))

    # ── Auto-Jam UI Panel ─────────────────────

    def _build_autojam_panel(self):
        SS = """
            QGroupBox { font-weight:bold; color:#e94560; border:1px solid #e94560;
                        border-radius:6px; margin-top:8px; padding-top:6px; }
            QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; }
            QLabel    { color:#cccccc; font-size:12px; }
            QTableWidget { background:#0d0d1a; color:#eaeaea; gridline-color:#2a2a4a;
                           font-family:'Courier New',monospace; font-size:12px;
                           selection-background-color:#e94560; border:1px solid #333; }
            QTableWidget::item { padding:4px; }
            QHeaderView::section { background:#16213e; color:#a0c4ff; font-weight:bold;
                                   padding:5px; border:1px solid #2a2a4a; }
            QTextEdit { background:#0d0d1a; color:#00ff88; font-family:'Courier New',monospace;
                        font-size:11px; border:1px solid #333; }
            QPushButton { background:#2a2a3e; color:#eaeaea; border:1px solid #444;
                          border-radius:4px; padding:5px 12px; font-size:12px; }
            QPushButton:hover { background:#3a3a5e; }
            QPushButton#add   { background:#1a6b3a; color:white; font-weight:bold; }
            QPushButton#add:hover  { background:#27ae60; }
            QPushButton#del   { background:#6b1a1a; color:white; font-weight:bold; }
            QPushButton#del:hover  { background:#c0392b; }
            QPushButton#save  { background:#1a4a6b; color:white; font-weight:bold; }
            QPushButton#save:hover { background:#2980b9; }
            QPushButton#load  { background:#4a3a1a; color:white; font-weight:bold; }
            QPushButton#load:hover { background:#d68910; }
            QPushButton#start { background:#27ae60; color:white; font-weight:bold; font-size:13px; }
            QPushButton#start:hover { background:#1e8449; }
            QPushButton#stop  { background:#c0392b; color:white; font-weight:bold; font-size:13px; }
            QPushButton#stop:hover  { background:#922b21; }
            QDoubleSpinBox { background:#16213e; color:#eaeaea; border:1px solid #444; padding:4px; }
            QLineEdit { background:#16213e; color:#00ff88; border:1px solid #444;
                        border-radius:3px; padding:4px; font-family:'Courier New',monospace; }
        """
        box = QtWidgets.QGroupBox("🐇 Auto-Jam — Frequency Target Editor")
        box.setStyleSheet(SS)
        outer = QtWidgets.QVBoxLayout(box)
        outer.setSpacing(6)
        outer.setContentsMargins(8, 8, 8, 8)

        # ── File row ──
        file_row = QtWidgets.QHBoxLayout()
        file_row.addWidget(QtWidgets.QLabel("JSON file:"))
        self._json_path = QtWidgets.QLineEdit()
        self._json_path.setPlaceholderText("path/to/jam.json")
        default_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jam.json")
        self._json_path.setText(default_json)
        file_row.addWidget(self._json_path, 1)
        browse_btn = QtWidgets.QPushButton("📂 Browse"); browse_btn.setObjectName("load")
        browse_btn.clicked.connect(self._browse_json); file_row.addWidget(browse_btn)
        load_btn = QtWidgets.QPushButton("⬇ Load"); load_btn.setObjectName("load")
        load_btn.setToolTip("Load JSON into table"); load_btn.clicked.connect(self._load_json_to_table)
        file_row.addWidget(load_btn)
        save_btn = QtWidgets.QPushButton("💾 Save JSON"); save_btn.setObjectName("save")
        save_btn.setToolTip("Save table → JSON"); save_btn.clicked.connect(self._save_json_from_table)
        file_row.addWidget(save_btn)
        outer.addLayout(file_row)

        # ── Table + side buttons ──
        table_row = QtWidgets.QHBoxLayout()
        self._target_table = QtWidgets.QTableWidget(0, 3)
        self._target_table.setHorizontalHeaderLabels(["Name", "Frequency (Hz)", "Bandwidth"])
        hdr = self._target_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self._target_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._target_table.setAlternatingRowColors(True)
        self._target_table.setMinimumHeight(120)
        self._target_table.verticalHeader().setDefaultSectionSize(26)
        table_row.addWidget(self._target_table, 1)

        side = QtWidgets.QVBoxLayout(); side.setSpacing(4)
        add_btn = QtWidgets.QPushButton("➕ Add Row"); add_btn.setObjectName("add")
        add_btn.clicked.connect(lambda: self._add_row()); side.addWidget(add_btn)
        dup_btn = QtWidgets.QPushButton("📋 Duplicate")
        dup_btn.clicked.connect(self._dup_row); side.addWidget(dup_btn)
        del_btn = QtWidgets.QPushButton("🗑 Delete Row"); del_btn.setObjectName("del")
        del_btn.clicked.connect(self._del_row); side.addWidget(del_btn)
        side.addStretch()
        clr_btn = QtWidgets.QPushButton("🧹 Clear All"); clr_btn.setObjectName("del")
        clr_btn.clicked.connect(self._clear_table); side.addWidget(clr_btn)
        table_row.addLayout(side)
        outer.addLayout(table_row)

        # ── Control row ──
        ctrl_row = QtWidgets.QHBoxLayout()
        ctrl_row.addWidget(QtWidgets.QLabel("Jump delay (sec):"))
        self._jump_delay = QtWidgets.QDoubleSpinBox()
        self._jump_delay.setMinimum(0.1); self._jump_delay.setMaximum(3600)
        self._jump_delay.setValue(1.0); self._jump_delay.setSingleStep(0.5)
        self._jump_delay.setFixedWidth(100); ctrl_row.addWidget(self._jump_delay)
        ctrl_row.addStretch()
        self._start_btn = QtWidgets.QPushButton("▶  Start Auto-Jam"); self._start_btn.setObjectName("start")
        self._start_btn.clicked.connect(self._start_autojam); ctrl_row.addWidget(self._start_btn)
        self._stop_btn = QtWidgets.QPushButton("■  Stop"); self._stop_btn.setObjectName("stop")
        self._stop_btn.setEnabled(False); self._stop_btn.clicked.connect(self._stop_autojam)
        ctrl_row.addWidget(self._stop_btn)
        outer.addLayout(ctrl_row)

        # ── Log ──
        self._log = QtWidgets.QTextEdit(); self._log.setReadOnly(True); self._log.setFixedHeight(60)
        outer.addWidget(self._log)
        self._bottom_layout.addWidget(box)

        # Auto-load if exists
        if os.path.exists(default_json):
            self._load_json_to_table()

    # ── Table helpers ──

    def _add_row(self, name="NewTarget", freq="446000000", bw="20MHz"):
        r = self._target_table.rowCount()
        self._target_table.insertRow(r)
        self._target_table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(name)))
        self._target_table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(freq)))
        self._target_table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(bw)))
        self._target_table.scrollToBottom()
        self._target_table.editItem(self._target_table.item(r, 0))

    def _dup_row(self):
        rows = sorted(set(i.row() for i in self._target_table.selectedItems()))
        for r in rows:
            n  = (self._target_table.item(r,0) or QtWidgets.QTableWidgetItem("")).text()
            fr = (self._target_table.item(r,1) or QtWidgets.QTableWidgetItem("")).text()
            bw = (self._target_table.item(r,2) or QtWidgets.QTableWidgetItem("")).text()
            self._add_row(n+"_copy", fr, bw)

    def _del_row(self):
        for r in sorted(set(i.row() for i in self._target_table.selectedItems()), reverse=True):
            self._target_table.removeRow(r)

    def _clear_table(self):
        if QtWidgets.QMessageBox.question(self,"Clear All","Remove all targets?",
            QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No)==QtWidgets.QMessageBox.Yes:
            self._target_table.setRowCount(0)

    def _browse_json(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self,"Open jam.json","","JSON Files (*.json);;All Files (*)")
        if path:
            self._json_path.setText(path); self._load_json_to_table()

    def _load_json_to_table(self):
        path = self._json_path.text().strip()
        if not path or not os.path.exists(path): return
        try:
            with open(path) as f: raw = json.load(f)
            self._target_table.setRowCount(0)
            for name, vals in raw.items():
                r = self._target_table.rowCount(); self._target_table.insertRow(r)
                self._target_table.setItem(r,0,QtWidgets.QTableWidgetItem(name))
                self._target_table.setItem(r,1,QtWidgets.QTableWidgetItem(str(vals.get("Freq",""))))
                self._target_table.setItem(r,2,QtWidgets.QTableWidgetItem(str(vals.get("Bandwidth","20MHz"))))
            self._log.append(f"✅ Loaded {self._target_table.rowCount()} targets from {os.path.basename(path)}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self,"Load Error",f"Failed:\n{e}")

    def _save_json_from_table(self):
        path = self._json_path.text().strip()
        if not path:
            path,_ = QtWidgets.QFileDialog.getSaveFileName(self,"Save jam.json","jam.json","JSON Files (*.json)")
            if not path: return
            self._json_path.setText(path)
        try:
            data = {}
            for r in range(self._target_table.rowCount()):
                name = (self._target_table.item(r,0) or QtWidgets.QTableWidgetItem("")).text().strip() or f"Target{r+1}"
                freq = (self._target_table.item(r,1) or QtWidgets.QTableWidgetItem("0")).text().strip()
                bw   = (self._target_table.item(r,2) or QtWidgets.QTableWidgetItem("20MHz")).text().strip()
                data[name] = {"Freq": float(freq), "Bandwidth": bw}
            with open(path,"w") as f: json.dump(data, f, indent=4)
            self._log.append(f"💾 Saved {len(data)} targets → {os.path.basename(path)}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self,"Save Error",f"Failed:\n{e}")

    def _table_to_targets(self):
        targets = []
        for r in range(self._target_table.rowCount()):
            name  = (self._target_table.item(r,0) or QtWidgets.QTableWidgetItem("")).text().strip()
            freq_s= (self._target_table.item(r,1) or QtWidgets.QTableWidgetItem("0")).text().strip()
            bw_s  = (self._target_table.item(r,2) or QtWidgets.QTableWidgetItem("20MHz")).text().strip()
            try: freq = float(freq_s)
            except ValueError: continue
            bw_n = bw_s.upper().replace("MHZ","e6").replace("KHZ","e3")
            try: bw = float(bw_n)
            except ValueError: bw = 20e6
            targets.append({"name": name or f"Target{r+1}", "freq": freq, "bw": bw})
        return targets

    def _load_json(self, path):
        with open(path) as f: raw = json.load(f)
        targets = []
        for name, vals in raw.items():
            bw_s = str(vals.get("Bandwidth","20MHz")).upper().replace("MHZ","e6").replace("KHZ","e3")
            try: bw = float(bw_s)
            except ValueError: bw = 20e6
            targets.append({"name":name,"freq":float(vals["Freq"]),"bw":bw})
        return targets


    def _start_autojam(self):
        targets = self._table_to_targets()
        if not targets:
            QtWidgets.QMessageBox.warning(self, "No Targets",
                "Add at least one frequency target in the table first.")
            return
        self._log.clear()
        self._log.append(f"Starting Auto-Jam with {len(targets)} target(s), delay={self._jump_delay.value()}s")
        for t in targets:
            self._log.append(f"  → {t['name']}  {t['freq']/1e6:.3f} MHz  BW:{t['bw']/1e6:.0f} MHz")
        self._log.append("─" * 50)
        self._auto_worker = AutoJamWorker(targets, self._jump_delay.value())
        self._auto_worker.jump_signal.connect(self._on_jump)
        self._auto_worker.status_signal.connect(self._on_status)
        self._auto_worker.start()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _stop_autojam(self):
        if self._auto_worker:
            self._auto_worker.stop()
            self._auto_worker.wait()
            self._auto_worker = None
        self._log.append("■ Auto-Jam stopped.")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _on_jump(self, name, freq, bw):
        self.set_freq(freq)
        self.set_bandwidth(int(bw))

    def _on_status(self, msg):
        self._log.append(msg)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    # ── GNURadio Setters ──────────────────────

    def set_samp_rate(self, v):
        self.samp_rate = v
        self.osmosdr_sink.set_sample_rate(v)
        self.qtgui_freq_sink.set_frequency_range(self.freq, v)

    def set_rf_gain(self, v):
        self.rf_gain = v
        self.osmosdr_sink.set_gain(v, 0)

    def set_if_gain(self, v):
        self.if_gain = v
        self.osmosdr_sink.set_if_gain(v, 0)

    def set_bb_gain(self, v):
        self.bb_gain = v
        self.osmosdr_sink.set_bb_gain(v, 0)

    def set_freq(self, v):
        self.freq = v
        self.osmosdr_sink.set_center_freq(v, 0)
        self.qtgui_freq_sink.set_frequency_range(v, self.samp_rate)

    def set_bandwidth(self, v):
        self.bandwidth = v
        self.osmosdr_sink.set_bandwidth(v, 0)

    def closeEvent(self, event):
        if self._auto_worker:
            self._auto_worker.stop()
            self._auto_worker.wait()
        event.accept()


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────

def main():
    app = Qt.QApplication(sys.argv)
    app.setStyle("Fusion")

    print("🐇 CleverJAM — Detecting SDR devices...")
    devices = detect_devices()

    if not devices:
        QtWidgets.QMessageBox.critical(None, "No Devices Found",
            "No SDR devices detected!\nConnect HackRF, LimeSDR, or BladeRF.")
        sys.exit(1)

    print(f"   Found {len(devices)} option(s):")
    for d in devices:
        print(f"   → {d['label']}")

    dialog = DeviceSelectDialog(devices)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        print("Cancelled."); sys.exit(0)

    device_args = dialog.selected_args
    print(f"\n✅ Selected: {dialog.selected_label}")
    print(f"   Args: {device_args}")
    print("   Starting GNURadio flowgraph...\n")

    tb = CleverJAM(device_args=device_args)
    tb.start()
    tb.showMaximized()   # ← auto-fit: fills screen, no scrolling needed

    def sig_handler(sig=None, frame=None):
        Qt.QApplication.quit()

    signal.signal(signal.SIGINT,  sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    app.exec_()
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
