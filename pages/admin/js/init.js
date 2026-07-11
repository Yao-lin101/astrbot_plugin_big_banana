// ===== 初始化事件监听和首次加载 =====
// 依赖 common.js 和 config.js，需要最后加载。

document.addEventListener('DOMContentLoaded', function () {
  // 全局 Esc：关闭页面中已打开的弹窗。
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var overlay = document.getElementById('ccConfirmModal');
      if (overlay) overlay.classList.remove('show');
    }
  });

  // 首次加载配置数据和可用提供商。
  loadData();
});
