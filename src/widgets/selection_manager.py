from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QColor, QPainterPath

class SelectionManager:
    def __init__(self, scene):
        self.scene = scene
        self.selections = []
        self.temp_rect = None
        self.start_point = None
        self.active = False
        
        # 1. 定义填充颜色 (之前遗漏的部分)
        self.add_color = QColor(137, 180, 250, 80)
        self.remove_color = QColor(243, 139, 168, 80)
        
        # 2. 定义画笔样式
        self.add_pen = QPen(QColor(137, 180, 250), 1)
        self.add_pen.setCosmetic(True)
        
        self.dash_pen_add = QPen(QColor(137, 180, 250), 1, Qt.DashLine)
        self.dash_pen_add.setCosmetic(True)
        
        self.dash_pen_remove = QPen(QColor(243, 139, 168), 1, Qt.DashLine)
        self.dash_pen_remove.setCosmetic(True)

    def set_active(self, active):
        self.active = active

    def _snap_to_pixel(self, pos):
        return QPointF(round(pos.x()), round(pos.y()))

    def handle_press(self, scene_pos, modifiers):
        if not self.active: return
        self.start_point = self._snap_to_pixel(scene_pos)
        
        self.temp_rect = QGraphicsRectItem()
        self.temp_rect.setZValue(11)
        
        if modifiers & Qt.KeyboardModifier.AltModifier:
            self.temp_rect.setPen(self.dash_pen_remove)
            self.temp_rect.setBrush(self.remove_color)
            self.temp_rect.setData(0, "remove")
        else:
            self.temp_rect.setPen(self.dash_pen_add)
            self.temp_rect.setBrush(self.add_color)
            self.temp_rect.setData(0, "add")
            
        self.scene.addItem(self.temp_rect)

    def handle_move(self, scene_pos):
        if not self.active or not self.temp_rect: return
        snapped_pos = self._snap_to_pixel(scene_pos)
        rect = QRectF(self.start_point, snapped_pos).normalized()
        self.temp_rect.setRect(rect)

    def handle_release(self, scene_pos, modifiers):
        if not self.active or not self.temp_rect: return
        
        new_rect = self.temp_rect.rect()
        mode = self.temp_rect.data(0)
        self.scene.removeItem(self.temp_rect)

        if new_rect.width() > 2 and new_rect.height() > 2:
            new_path = QPainterPath()
            new_path.addRect(new_rect)
            valid_items = self._get_valid_selections()
            intersected = [s for s in valid_items if s.collidesWithItem(self.temp_rect)]

            if mode == "remove":
                for item in intersected:
                    old_path = self._get_item_path(item)
                    result_path = old_path.subtracted(new_path)
                    if result_path.isEmpty():
                        self._remove_item(item)
                    else:
                        self._update_item_shape(item, result_path)

            elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                if intersected:
                    base_item = intersected[0]
                    combined_path = self._get_item_path(base_item)
                    combined_path = combined_path.united(new_path)
                    for i in range(1, len(intersected)):
                        combined_path = combined_path.united(self._get_item_path(intersected[i]))
                        self._remove_item(intersected[i])
                    self._update_item_shape(base_item, combined_path)
                else:
                    self._create_new_rect(new_rect)
            else:
                self._create_new_rect(new_rect)

        self.temp_rect = None

    def _get_valid_selections(self):
        valid = []
        for item in self.selections:
            try:
                _ = item.scene() 
                valid.append(item)
            except RuntimeError:
                continue
        self.selections = valid
        return self.selections

    def _get_item_path(self, item):
        if isinstance(item, QGraphicsRectItem):
            path = QPainterPath()
            path.addRect(item.rect())
            return path
        return item.path()

    def _update_item_shape(self, item, path):
        if isinstance(item, QGraphicsRectItem):
            new_item = QGraphicsPathItem(path)
            new_item.setPen(self.add_pen)
            new_item.setBrush(self.add_color)
            new_item.setZValue(10)
            idx = self.selections.index(item)
            self.selections[idx] = new_item
            self.scene.removeItem(item)
            self.scene.addItem(new_item)
        else:
            item.setPath(path)

    def _create_new_rect(self, rect):
        item = QGraphicsRectItem(rect)
        item.setPen(self.add_pen)
        item.setBrush(self.add_color)
        item.setZValue(10)
        self.scene.addItem(item)
        self.selections.append(item)

    def _remove_item(self, item):
        if item in self.selections:
            self.selections.remove(item)
            self.scene.removeItem(item)

    def handle_double_click(self, scene_pos):
        if not self.active: return
        valid_items = self._get_valid_selections()
        items = self.scene.items(scene_pos)
        clicked = [i for i in items if i in valid_items]
        if clicked:
            self._remove_item(clicked[0])
        else:
            self.clear_selections()

    def clear_selections(self):
        for item in self.selections:
            try: self.scene.removeItem(item)
            except: pass
        self.selections.clear()