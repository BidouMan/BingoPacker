# btn_pick模式移动选区图像处理逻辑分析

## 核心机制

### 1. 分层编辑机制

btn_pick模式使用了分层编辑机制，主要包括：

- **悬浮图层**：创建`pix_overlay`作为选区的子项，在移动过程中只更新overlay，不直接修改底图
- **背景遮罩**：使用`_update_background_mask`方法实时更新背景遮罩，确保底图上的空洞位置正确

关键代码：
```python
# _prepare_moving_pixels 方法 - 将选区内的像素抠出来
crop_pix = bg_item.pixmap().copy(local_rect)
self._permanently_erase_pixels(bg_item, local_rect)

# 创建贴层
overlay = ClippedPixmapItem(crop_pix)
overlay.is_clone = True
overlay.setParentItem(target_item)
target_item.pix_overlay = overlay
```

### 2. 数据同步机制

在`_merge_back_to_bg`方法中，使用`frame_index`参数确保更新正确的帧：

```python
# 确定要更新的帧索引
idx = (
    frame_index
    if frame_index is not None
    else editor.frame_list.currentRow()
)

# 更新对应帧的数据
if editor.current_bundle and 0 <= idx < len(editor.current_bundle.frames):
    editor.current_bundle.frames[idx].pixmap = new_bg_pix
```

### 3. 帧切换时的保存逻辑

在`switch_frame_preview`方法中，在切换帧前保存当前帧的修改：

```python
# 在显示新帧前，先保存当前帧的修改
if self.preview_item and self.current_bundle and self.current_frame_index >= 0:
    # 首先，检查是否有移动的选区需要合并
    if hasattr(self, "selection_manager") and self.selection_manager.selections:
        # 直接使用当前帧索引合并选区
        self.selection_manager.clear_selections(
            frame_index=self.current_frame_index
        )
    
    # 然后保存当前帧的最终状态
    current_pixmap = self.preview_item.pixmap()
    if 0 <= self.current_frame_index < len(self.current_bundle.frames):
        self.current_bundle.frames[self.current_frame_index].pixmap = current_pixmap
```

## 问题根源分析

当前变换工具和裁切工具存在的问题：

1. **更新了错误的帧**：使用`last_index`或其他变量，而不是当前选中的帧索引
2. **更新了original_pixmap**：这会影响到所有帧的显示
3. **缺少分层编辑**：没有使用悬浮图层机制，直接修改底图
4. **数据同步不完整**：没有同时更新`current_frames`和`current_bundle.frames`

## 解决方案

### 1. 使用正确的帧索引

所有数据更新操作都应该使用`self.frame_list.currentRow()`获取当前帧索引，而不是`last_index`。

### 2. 移除original_pixmap更新

`original_pixmap`应该只在初始化时设置，不应该在编辑过程中更新。

### 3. 实现分层编辑机制

参考btn_pick模式，使用悬浮图层机制处理变换操作。

### 4. 完整的数据同步

确保同时更新`current_frames`和`current_bundle.frames`中的对应帧。

### 5. 帧切换时的保存逻辑

在切换帧前，确保保存当前帧的修改，使用`current_frame_index`参数。

## 关键修复点

1. **_confirm_transform**：使用`self.frame_list.currentRow()`获取当前帧索引，移除`original_pixmap`更新
2. **_cleanup_current_tool**：使用`self.frame_list.currentRow()`获取当前帧索引，移除`original_pixmap`更新
3. **apply_crop**：使用`self.frame_list.currentRow()`获取当前帧索引，移除`original_pixmap`更新
4. **switch_frame_preview**：确保在切换帧前保存当前帧的修改

## 总结

btn_pick模式的成功在于：
- 使用分层编辑机制，避免直接修改底图
- 使用正确的帧索引进行数据同步
- 在帧切换时保存当前帧的修改
- 完整更新所有相关数据结构

这些机制确保了修改B帧后不会污染A帧的数据。