# -*- coding: utf-8 -*-
"""配置 matplotlib 默认字体为 Noto Sans CJK SC（沙箱镜像构建脚本）。

sandbox.Dockerfile 构建时执行本脚本（随后删除），流程：
  1. 向 matplotlib 全局 matplotlibrc 追加中文字体配置（幂等）
  2. 清除字体缓存，让下次启动重建字体清单（含新装的 Noto 字体）
  3. 强制重扫字体并校验 Noto Sans CJK SC 可用（找不到即报错退出）
  4. 用 Agg 后端渲染含中文标题的测试图，确认无缺字告警

仅用于 Linux 容器（python:3.12-slim + fonts-noto-cjk）。
"""
import importlib.util
import pathlib
import shutil
import sys

_FONT_NAME = "Noto Sans CJK SC"
_CONFIG_LINES = """\n# --- 中文字体配置（sandbox 镜像构建时注入） ---
font.family: sans-serif
font.sans-serif: Noto Sans CJK SC, DejaVu Sans
axes.unicode_minus: False
"""


def _matplotlibrc_path() -> pathlib.Path:
    """定位 matplotlib 全局 matplotlibrc。

    用 importlib 而非 import matplotlib 定位，保证配置写入发生在
    matplotlib 首次加载（初始化 rcParams）之前。
    """
    spec = importlib.util.find_spec("matplotlib")
    if spec is None or spec.origin is None:
        raise RuntimeError("未找到 matplotlib，请确认镜像构建步骤已安装")
    return pathlib.Path(spec.origin).parent / "mpl-data" / "matplotlibrc"


def _append_config(rc_path: pathlib.Path) -> None:
    """向 matplotlibrc 追加中文字体配置（幂等：已包含则跳过）。"""
    text = rc_path.read_text(encoding="utf-8")
    if "font.sans-serif: Noto Sans CJK SC" in text:
        print(f"matplotlibrc 已包含中文字体配置，跳过: {rc_path}")
        return
    rc_path.write_text(text + _CONFIG_LINES, encoding="utf-8")
    print(f"已写入中文字体配置: {rc_path}")


def _clear_font_cache() -> None:
    """删除 matplotlib 字体缓存，让下次启动重建（否则新装字体不被感知）。"""
    import matplotlib

    cache_dir = matplotlib.get_cachedir()
    shutil.rmtree(cache_dir, ignore_errors=True)
    print(f"已清除字体缓存: {cache_dir}")


def _verify_font() -> None:
    """重扫系统字体，确认 Noto Sans CJK SC 可用（找不到则报错退出）。"""
    import matplotlib.font_manager as fm

    fm.fontManager = fm.FontManager()  # 不走缓存，强制重扫
    names = {f.name for f in fm.fontManager.ttflist}
    if _FONT_NAME not in names:
        raise RuntimeError(
            f"未找到字体 {_FONT_NAME}，请确认已安装 fonts-noto-cjk。"
            f"可用字体样例: {', '.join(sorted(names)[:20])}"
        )
    print(f"字体校验通过: {_FONT_NAME}")


def _render_test_figure() -> None:
    """渲染含中文标题的测试图，确认无缺字告警（豆腐块）。"""
    import warnings

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig, ax = plt.subplots()
        ax.set_title("中文标题渲染测试")
        out = pathlib.Path("/tmp") / "_matplotlib_chinese_test.png"
        fig.savefig(out)
        plt.close(fig)
    missing = [w for w in caught if "missing from font" in str(w.message)]
    if missing:
        raise RuntimeError(f"测试图存在缺字告警: {missing}")
    out.unlink(missing_ok=True)
    print("测试图渲染通过（无缺字告警）")


def main() -> int:
    _append_config(_matplotlibrc_path())
    _clear_font_cache()
    _verify_font()
    _render_test_figure()
    print("✓ matplotlib 中文字体配置完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
