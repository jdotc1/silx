"""Trace the failing Windows interaction without running the full CI suite."""
import json
import pathlib
import platform
import os
import tempfile
import sys

import numpy
import pytest
from silx.gui import qt
from silx.gui.plot.test import test_scattermasktoolswidget as tests


def trace(label, **values):
    print('MASK_TRACE ' + json.dumps(dict(label=label, **values), default=str), flush=True)


original_drag = tests.TestScatterMaskToolsWidget._drag


def traced_drag(self):
    handle = self.plot.getWidgetHandle()
    scatter = self.plot.getActiveScatter()
    center = (handle.width() // 2, handle.height() // 2)
    offset = min(handle.width(), handle.height()) // 10
    end = (center[0] + offset, center[1] + offset)
    start_data = self.plot.pixelToData(*center)
    end_data = self.plot.pixelToData(*end)
    count = None
    if scatter is not None and start_data is not None and end_data is not None:
        x, y = scatter.getXData(), scatter.getYData()
        count = int(numpy.count_nonzero((x >= min(start_data[0], end_data[0])) & (x <= max(start_data[0], end_data[0])) & (y >= min(start_data[1], end_data[1])) & (y <= max(start_data[1], end_data[1]))))
    trace('before_drag', handle_size=(handle.width(), handle.height()), plot_bounds=self.plot.getPlotBoundsInPixels(), center=center, end=end, start_data=start_data, end_data=end_data, points_in_rectangle=count, active_scatter=None if scatter is None else scatter.getName(), enabled=self.maskWidget.isEnabled(), visible=self.maskWidget.isVisible(), mode=self.plot.getInteractiveMode(), window_active=self.plot.isActiveWindow())
    self.plot.sigPlotSignal.connect(lambda event: trace('plot_event', event=event) if event.get('event') in ('drawingProgress', 'drawingFinished', 'mousePressed', 'mouseReleased') else None)
    self.maskWidget.sigMaskChanged.connect(lambda: trace('mask_changed'))
    class Events(qt.QObject):
        def eventFilter(self, watched, event):
            if event.type() in (qt.QEvent.MouseMove, qt.QEvent.MouseButtonPress, qt.QEvent.MouseButtonRelease):
                trace('mouse_event', type=int(event.type()), pos=(event.pos().x(), event.pos().y()), buttons=int(event.buttons()))
            return False
    observer = Events()
    handle.installEventFilter(observer)
    try:
        return original_drag(self)
    finally:
        handle.removeEventFilter(observer)
        trace('after_drag', nonzero_mask=int(numpy.count_nonzero(self.maskWidget.getSelectionMask())))


tests.TestScatterMaskToolsWidget._drag = traced_drag
trace('environment', platform=platform.platform(), python=sys.version, binding=qt.BINDING, qt=qt.qVersion(), pyqt=qt.PYQT_VERSION_STR, numpy=numpy.__version__)
path = pathlib.Path(tests.__file__).resolve()
original_directory = os.getcwd()
with tempfile.TemporaryDirectory(prefix='silx-mask-trace-') as directory:
    try:
        os.chdir(directory)
        result = pytest.main([str(path) + '::TestScatterMaskToolsWidget::testSigMaskChangedEmitted', '--rootdir=' + str(path.parents[3]), '--qt-binding=PyQt5', '-s', '-v'])
    finally:
        os.chdir(original_directory)
sys.exit(result)
