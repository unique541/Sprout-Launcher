"""QML 列表模型。"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, QThread, Qt, Signal


class DictListModel(QAbstractListModel):
    """通用字典列表模型：roles 为字段名列表。

    后台线程调用 set_items 时通过信号排队到模型所属线程执行，
    避免跨线程 beginResetModel 导致 QML 视图不刷新。
    """

    _itemsReady = Signal(object)

    def __init__(self, roles: list[str], parent=None) -> None:
        super().__init__(parent)
        self._roles = roles
        self._items: list[dict[str, Any]] = []
        self._role_ids = {Qt.UserRole + 1 + i: name for i, name in enumerate(roles)}
        self._itemsReady.connect(self._apply_items)

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {rid: name.encode() for rid, name in self._role_ids.items()}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        name = self._role_ids.get(role)
        if name is None:
            return None
        return self._items[index.row()].get(name)

    def _apply_items(self, items) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def set_items(self, items: list[dict[str, Any]]) -> None:
        payload = list(items)
        if QThread.currentThread() is self.thread():
            self._apply_items(payload)
        else:
            self._itemsReady.emit(payload)

    def patch_row(self, row: int, values: dict[str, Any]) -> None:
        if 0 <= row < len(self._items):
            self._items[row].update(values)
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, list(self._role_ids.keys()))

    def find_row(self, key: str, value: Any) -> int:
        for i, item in enumerate(self._items):
            if item.get(key) == value:
                return i
        return -1

    def item(self, row: int) -> dict[str, Any]:
        if 0 <= row < len(self._items):
            return self._items[row]
        return {}
