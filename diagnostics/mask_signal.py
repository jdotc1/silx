"""Trace the scatter-mask interaction in its full installed-suite context."""
import json
import pathlib
import platform
import os
import tempfile
import sys

import numpy
import pytest
from silx.gui import qt
import silx


def trace(label, **values):
    print('MASK_TRACE ' + json.dumps(dict(label=label, **values), default=str), flush=True)


original_drag = None


def traced_drag(self):
    if self._testMethodName != 'testSigMaskChangedEmitted':
        return original_drag(self)
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


class TracePlugin:
    def pytest_collection_modifyitems(self, items):
        global original_drag
        for item in items:
            if item.nodeid.endswith('test_scattermasktoolswidget.py::TestScatterMaskToolsWidget::testSigMaskChangedEmitted'):
                case = item.module.TestScatterMaskToolsWidget
                original_drag = case._drag
                case._drag = traced_drag
                trace('instrumented', nodeid=item.nodeid, preceding_tests=[entry.nodeid for entry in items[max(0, items.index(item) - 8):items.index(item)]])
                break
        else:
            raise RuntimeError('Target test missing from full-suite collection')

def main():
    trace('environment', platform=platform.platform(), python=sys.version, binding=qt.BINDING, qt=qt.qVersion(), pyqt=qt.PYQT_VERSION_STR, numpy=numpy.__version__)
    path = pathlib.Path(silx.__file__).resolve().parent
    output = pathlib.Path(__file__).resolve().parent / 'output'
    output.mkdir(exist_ok=True)
    original_directory = os.getcwd()
    with tempfile.TemporaryDirectory(prefix='silx-mask-trace-') as directory:
        try:
            os.chdir(directory)
            result = pytest.main([str(path), '--rootdir=' + str(path), '--qt-binding=PyQt5', '-s', '-vv', '--junitxml=' + str(output / 'full-suite.xml')], plugins=[TracePlugin()])
        finally:
            os.chdir(original_directory)
    return result


if __name__ == '__main__':
    sys.exit(main())
