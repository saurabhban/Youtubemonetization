"""
Animation Engine — generates animated educational video clips using matplotlib.
Produces MP4 clips (1920×1080, 30fps) that can be used as full-scene visuals.

Supported animation types:
  bullet_list       — bullet points reveal one by one
  bar_chart         — horizontal bars grow from left
  stat_card         — giant number counts up
  comparison_table  — side-by-side table with row highlights
"""
import os
import logging
import subprocess
import tempfile
import shutil

logger = logging.getLogger(__name__)

# ── Colours (CloudSignalHQ brand) ───────────────────────────────────────────
BG          = "#0a0e1e"   # Deep navy
ACCENT      = "#0078ff"   # Electric blue
ACCENT2     = "#50c8ff"   # Sky blue
GOLD        = "#ffcc00"
WHITE       = "#ffffff"
LIGHT_GRAY  = "#a0aabf"
DARK_PANEL  = "#111827"
GREEN       = "#22c55e"
RED         = "#ef4444"

FIG_W, FIG_H = 19.2, 10.8   # inches at 100 dpi → 1920×1080
FPS          = 30


def _setup_matplotlib():
    """Import matplotlib with non-interactive Agg backend."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    plt.rcParams.update({
        "figure.facecolor":  BG,
        "axes.facecolor":    BG,
        "text.color":        WHITE,
        "axes.labelcolor":   WHITE,
        "xtick.color":       LIGHT_GRAY,
        "ytick.color":       LIGHT_GRAY,
        "axes.edgecolor":    "#2a3550",
        "grid.color":        "#1e2a45",
        "font.family":       "DejaVu Sans",
        "font.size":         14,
        "savefig.facecolor": BG,
    })
    return plt


def _fig_to_mp4(fig_fn, n_frames: int, output_path: str, fps: int = FPS) -> bool:
    """
    Render a matplotlib figure to MP4 using FFmpeg pipe.
    fig_fn(frame_idx) must update fig and return it.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io

    tmp_dir = tempfile.mkdtemp()
    try:
        frame_paths = []
        for i in range(n_frames):
            fig = fig_fn(i)
            frame_path = os.path.join(tmp_dir, f"frame_{i:05d}.png")
            fig.savefig(frame_path, dpi=100, facecolor=BG, bbox_inches="tight",
                        pad_inches=0)
            plt.close(fig)
            frame_paths.append(frame_path)

        # FFmpeg concat frames → MP4
        list_path = os.path.join(tmp_dir, "frames.txt")
        with open(list_path, "w") as f:
            for p in frame_paths:
                f.write(f"file '{p}'\n")
                f.write(f"duration {1.0/fps:.4f}\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                   "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0a0e1e,"
                   f"fps={fps}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-map", "0:v", "-map", "1:a",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
            "-shortest",
            output_path,
        ]
        # Simpler two-pass approach
        silent_path = output_path + "_silent.mp4"
        cmd_v = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-vf", f"scale=1920:1080:force_original_aspect_ratio=decrease,"
                   f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0a0e1e,"
                   f"fps={fps}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            silent_path,
        ]
        r = subprocess.run(cmd_v, capture_output=True, text=True)
        if r.returncode != 0:
            logger.error(f"Animation render failed:\n{r.stderr[-600:]}")
            return False

        # Add silent audio
        cmd_a = [
            "ffmpeg", "-y",
            "-i", silent_path,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
            "-t", str(n_frames / fps),
            output_path,
        ]
        r2 = subprocess.run(cmd_a, capture_output=True, text=True)
        if r2.returncode != 0:
            logger.error(f"Audio add failed:\n{r2.stderr[-400:]}")
            return False

        logger.info(f"Animation rendered: {os.path.basename(output_path)} ({n_frames} frames)")
        return True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        silent = output_path + "_silent.mp4"
        if os.path.exists(silent):
            os.remove(silent)


# ── Bullet List Animation ───────────────────────────────────────────────────

def render_bullet_list(items: list, title: str, duration_sec: float,
                       output_path: str) -> bool:
    """
    Animated bullet list — each item fades in one by one.
    Items reveal at equal intervals across the duration.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    n_items     = len(items)
    n_frames    = int(duration_sec * FPS)
    reveal_step = n_frames / max(n_items, 1)   # frames per bullet reveal

    # Accent gradient bar heights for the left marker
    BULLET_COLORS = [ACCENT, ACCENT2, GOLD, GREEN, WHITE, ACCENT, ACCENT2, GOLD]

    def make_frame(fi):
        fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        # Top gradient bar
        for x in range(1920):
            t = x / 1920
            r = 0.0 + t * 0.3
            g = 0.47 + t * (0.78 - 0.47)
            b = 1.0
            ax.axvline(x=x/1920, ymin=0.97, ymax=1.0,
                       color=(r, g, b), linewidth=2, alpha=0.8)

        # Title
        ax.text(0.5, 0.88, title, ha="center", va="center",
                fontsize=38, fontweight="bold", color=WHITE,
                transform=ax.transAxes)

        # Underline
        ax.plot([0.15, 0.85], [0.83, 0.83], color=ACCENT, linewidth=3,
                transform=ax.transAxes)

        # Bullets
        n_visible = min(n_items, int(fi / reveal_step) + 1)
        y_start = 0.72
        y_step  = min(0.13, 0.65 / max(n_items, 1))

        for i in range(n_visible):
            y = y_start - i * y_step
            alpha = 1.0

            # Is this the newest item? Fade it in
            frames_since_reveal = fi - i * reveal_step
            if frames_since_reveal < FPS * 0.4:  # 0.4s fade
                alpha = frames_since_reveal / (FPS * 0.4)

            bcolor = BULLET_COLORS[i % len(BULLET_COLORS)]

            # Bullet dot
            ax.add_patch(mpatches.Circle((0.07, y), 0.012,
                                          color=bcolor, alpha=alpha,
                                          transform=ax.transAxes))

            # Horizontal line (connecting bar → text)
            ax.plot([0.085, 0.10], [y, y], color=bcolor,
                    linewidth=2, alpha=alpha * 0.6, transform=ax.transAxes)

            # Text
            ax.text(0.11, y, items[i], ha="left", va="center",
                    fontsize=26, color=WHITE, alpha=alpha,
                    transform=ax.transAxes)

        # Channel name bottom right
        ax.text(0.97, 0.03, "☁ CloudSignalHQ", ha="right", va="bottom",
                fontsize=18, color=ACCENT2, alpha=0.7, transform=ax.transAxes)

        return fig

    return _fig_to_mp4(make_frame, n_frames, output_path)


# ── Bar Chart Animation ─────────────────────────────────────────────────────

def render_bar_chart(labels: list, values: list, title: str, unit: str,
                     duration_sec: float, output_path: str) -> bool:
    """Horizontal bar chart — bars grow from left over the first half of duration."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    n_frames   = int(duration_sec * FPS)
    grow_frames = int(n_frames * 0.55)   # bars fully grown by 55% of duration
    max_val    = max(values) if values else 1
    n          = len(labels)
    bar_colors = [ACCENT, ACCENT2, GOLD, GREEN, "#ff6b35", WHITE]

    def make_frame(fi):
        progress = min(1.0, fi / max(grow_frames, 1))
        # Ease-out: progress^0.5
        eased = progress ** 0.5

        fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)

        widths  = [v * eased for v in values]
        y_pos   = list(range(n - 1, -1, -1))
        colors  = [bar_colors[i % len(bar_colors)] for i in range(n)]
        bar_h   = max(0.35, 0.65 / max(n, 1))

        bars = ax.barh(y_pos, widths, color=colors, height=bar_h,
                       edgecolor="none", alpha=0.9)

        # Value labels on bars
        for i, (bar, val) in enumerate(zip(bars, values)):
            x = bar.get_width()
            display = f"{val} {unit}" if unit else str(val)
            ax.text(x + max_val * 0.01, y_pos[i], display,
                    va="center", fontsize=22, color=WHITE, fontweight="bold")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=24, color=WHITE)
        ax.set_xlim(0, max_val * 1.25)
        ax.set_xticks([])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_color("#2a3550")
        ax.grid(axis="x", color="#1e2a45", linewidth=0.5)

        ax.set_title(title, fontsize=34, color=WHITE, fontweight="bold",
                     pad=28, loc="left")

        # Channel watermark
        fig.text(0.97, 0.02, "☁ CloudSignalHQ", ha="right", fontsize=16,
                 color=ACCENT2, alpha=0.6)

        plt.tight_layout(rect=[0.02, 0.04, 0.98, 0.96])
        return fig

    return _fig_to_mp4(make_frame, n_frames, output_path)


# ── Stat Card Animation ─────────────────────────────────────────────────────

def render_stat_card(stats: list, duration_sec: float, output_path: str) -> bool:
    """
    Animated stat counter(s) — numbers count up from 0.
    stats = [{"label": "...", "value": "2,40,000", "context": "..."}]
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import re

    n_frames    = int(duration_sec * FPS)
    count_frames = int(n_frames * 0.50)   # count up in first 50%

    def _parse_num(s: str):
        """Extract numeric part from value string like '2,40,000' or '₹18 LPA'."""
        digits = re.sub(r"[^0-9]", "", s)
        return int(digits) if digits else 0

    parsed = [{"raw": s, "num": _parse_num(s.get("value", "0")), **s} for s in stats]
    n_stats = len(stats)

    def make_frame(fi):
        progress = min(1.0, fi / max(count_frames, 1)) ** 0.5  # ease-out
        fig, axes = plt.subplots(1, n_stats, figsize=(FIG_W, FIG_H))
        if n_stats == 1:
            axes = [axes]
        fig.patch.set_facecolor(BG)

        for ax, stat in zip(axes, parsed):
            ax.set_facecolor(BG)
            ax.axis("off")

            current_num = int(stat["num"] * progress)
            # Format with commas (Indian style if large)
            if stat["num"] > 99999:
                display = f"{current_num:,}"
            else:
                # Reconstruct the original format
                ratio = current_num / max(stat["num"], 1)
                display = stat.get("value", str(current_num))
                if ratio < 1.0:
                    display = str(current_num)

            # Big number
            ax.text(0.5, 0.58, display, ha="center", va="center",
                    fontsize=78, fontweight="bold", color=ACCENT2,
                    transform=ax.transAxes)

            # Glowing underline
            ax.plot([0.1, 0.9], [0.42, 0.42], color=ACCENT,
                    linewidth=5, alpha=0.9, transform=ax.transAxes)

            # Label above
            ax.text(0.5, 0.75, stat.get("label", ""), ha="center", va="center",
                    fontsize=26, color=WHITE, fontweight="bold",
                    transform=ax.transAxes, wrap=True)

            # Context below
            ax.text(0.5, 0.28, stat.get("context", ""), ha="center", va="center",
                    fontsize=19, color=LIGHT_GRAY, style="italic",
                    transform=ax.transAxes)

        fig.text(0.5, 0.05, "☁ CloudSignalHQ", ha="center", fontsize=18,
                 color=ACCENT2, alpha=0.7)
        plt.tight_layout(rect=[0, 0.08, 1, 0.95])
        return fig

    return _fig_to_mp4(make_frame, n_frames, output_path)


# ── Comparison Table Animation ──────────────────────────────────────────────

def render_comparison_table(title: str, headers: list, rows: list,
                             duration_sec: float, output_path: str) -> bool:
    """
    Animated comparison table — rows highlight one by one.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    n_frames    = int(duration_sec * FPS)
    n_rows      = len(rows)
    reveal_step = n_frames / max(n_rows + 1, 1)
    n_cols      = len(headers)

    COL_COLORS = [ACCENT, ACCENT2, GOLD, GREEN]

    def make_frame(fi):
        fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        n_visible_rows = min(n_rows, int(fi / reveal_step))

        # Title
        ax.text(0.5, 0.91, title, ha="center", va="center",
                fontsize=36, fontweight="bold", color=WHITE,
                transform=ax.transAxes)
        ax.plot([0.08, 0.92], [0.85, 0.85], color=ACCENT, linewidth=3,
                transform=ax.transAxes)

        # Table dimensions
        table_left  = 0.06
        table_right = 0.94
        col_w = (table_right - table_left) / max(n_cols, 1)
        row_h = min(0.09, 0.65 / max(n_rows + 1, 1))
        start_y = 0.81

        # Header row
        for ci, header in enumerate(headers):
            x = table_left + ci * col_w + col_w / 2
            y = start_y - row_h / 2
            hcolor = COL_COLORS[ci % len(COL_COLORS)] if ci > 0 else WHITE
            # Cell background
            rect = mpatches.FancyBboxPatch(
                (table_left + ci * col_w + 0.005, start_y - row_h + 0.005),
                col_w - 0.01, row_h - 0.005,
                boxstyle="round,pad=0.01",
                facecolor="#1a2240", edgecolor=ACCENT, linewidth=1.5,
                transform=ax.transAxes, zorder=2,
            )
            ax.add_patch(rect)
            ax.text(x, y, header, ha="center", va="center",
                    fontsize=22, fontweight="bold", color=hcolor,
                    transform=ax.transAxes, zorder=3)

        # Data rows
        for ri in range(n_visible_rows):
            y_top = start_y - (ri + 1) * row_h
            is_new = ri == n_visible_rows - 1
            alpha  = min(1.0, (fi - ri * reveal_step) / (FPS * 0.3)) if is_new else 1.0
            row_bg = "#0f1a30" if ri % 2 == 0 else "#131e38"

            for ci, cell in enumerate(rows[ri]):
                x = table_left + ci * col_w + col_w / 2
                y = y_top - row_h / 2
                ccolor = COL_COLORS[ci % len(COL_COLORS)] if ci > 0 else LIGHT_GRAY

                rect = mpatches.FancyBboxPatch(
                    (table_left + ci * col_w + 0.005, y_top + 0.005),
                    col_w - 0.01, row_h - 0.008,
                    boxstyle="round,pad=0.01",
                    facecolor=row_bg,
                    edgecolor=ACCENT if is_new else "#1e2a45",
                    linewidth=2.0 if is_new else 0.8,
                    alpha=alpha,
                    transform=ax.transAxes, zorder=2,
                )
                ax.add_patch(rect)
                ax.text(x, y, str(cell), ha="center", va="center",
                        fontsize=20, color=WHITE if ci == 0 else ccolor,
                        alpha=alpha, transform=ax.transAxes, zorder=3)

        fig.text(0.97, 0.02, "☁ CloudSignalHQ", ha="right", fontsize=16,
                 color=ACCENT2, alpha=0.6)
        return fig

    return _fig_to_mp4(make_frame, n_frames, output_path)


# ── Auto-router ─────────────────────────────────────────────────────────────

def render_for_scene(scene: dict, duration_sec: float, output_path: str) -> bool:
    """
    Detect scene visual_type and render the appropriate animation.
    Returns True if animation was rendered, False if scene should use footage.
    """
    visual_type = scene.get("visual_type", "footage")
    anim_data   = scene.get("animation_data") or {}
    on_screen   = scene.get("on_screen_text", "")

    if visual_type == "footage" or not visual_type:
        return False

    try:
        if visual_type == "bullet_list":
            items = anim_data.get("items", [on_screen])
            title = anim_data.get("title", scene.get("title", ""))
            if not items:
                return False
            return render_bullet_list(items, title, duration_sec, output_path)

        elif visual_type == "bar_chart":
            labels = anim_data.get("labels", [])
            values = anim_data.get("values", [])
            title  = anim_data.get("title", on_screen)
            unit   = anim_data.get("unit", "")
            if not labels or not values:
                return False
            return render_bar_chart(labels, values, title, unit, duration_sec, output_path)

        elif visual_type == "stat_card":
            stats = anim_data.get("stats", [])
            if not stats:
                # Try to build one stat from on_screen_text
                stats = [{"label": on_screen, "value": "0", "context": ""}]
            return render_stat_card(stats, duration_sec, output_path)

        elif visual_type == "comparison_table":
            title   = anim_data.get("title", on_screen)
            headers = anim_data.get("headers", [])
            rows    = anim_data.get("rows", [])
            if not headers or not rows:
                return False
            return render_comparison_table(title, headers, rows, duration_sec, output_path)

        else:
            logger.warning(f"Unknown visual_type '{visual_type}' — using footage")
            return False

    except Exception as e:
        logger.error(f"Animation render failed for scene {scene.get('id')} ({visual_type}): {e}")
        return False
