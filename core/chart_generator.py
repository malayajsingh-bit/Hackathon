import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from utils.config import CHART_COLORS, FONT_FAMILY


class ChartGenerator:
    def __init__(self, output_dir: str = "temp"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.size"] = 14

    def generate(self, chart_spec: dict, filename: str) -> str:
        chart_type = chart_spec.get("type", "bar")
        output_path = os.path.join(self.output_dir, filename)

        method = {
            "bar": self._bar_chart,
            "horizontal_bar": self._horizontal_bar,
            "line": self._line_chart,
            "pie": self._pie_chart,
        }.get(chart_type, self._bar_chart)

        method(chart_spec, output_path)
        return output_path

    def _bar_chart(self, spec: dict, path: str):
        fig, ax = plt.subplots(figsize=(10, 6))
        data = spec["data"]
        labels = data["labels"]

        for i, dataset in enumerate(data["datasets"]):
            values = dataset["values"]
            color = CHART_COLORS[i % len(CHART_COLORS)]
            x_positions = range(len(labels))

            if len(data["datasets"]) > 1:
                width = 0.8 / len(data["datasets"])
                offset = (i - len(data["datasets"]) / 2 + 0.5) * width
                positions = [x + offset for x in x_positions]
            else:
                width = 0.6
                positions = list(x_positions)

            bars = ax.bar(positions, values, width=width, color=color,
                          edgecolor="none", label=dataset.get("label", ""))

            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + max(values) * 0.02,
                        self._format_number(val), ha="center", va="bottom",
                        fontweight="bold", fontsize=12)

        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=12)
        if len(data["datasets"]) > 1:
            ax.legend(fontsize=11)
        self._style_chart(ax, spec.get("title", ""))
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()

    def _horizontal_bar(self, spec: dict, path: str):
        fig, ax = plt.subplots(figsize=(10, 6))
        data = spec["data"]
        labels = data["labels"]
        values = data["datasets"][0]["values"]
        color = CHART_COLORS[0]

        bars = ax.barh(labels, values, color=color, edgecolor="none", height=0.6)
        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + max(values) * 0.02, bar.get_y() + bar.get_height() / 2.,
                    self._format_number(val), ha="left", va="center",
                    fontweight="bold", fontsize=12)

        self._style_chart(ax, spec.get("title", ""))
        ax.invert_yaxis()
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()

    def _line_chart(self, spec: dict, path: str):
        fig, ax = plt.subplots(figsize=(10, 6))
        data = spec["data"]
        labels = data["labels"]

        for i, dataset in enumerate(data["datasets"]):
            values = dataset["values"]
            color = CHART_COLORS[i % len(CHART_COLORS)]
            ax.plot(labels, values, marker="o", color=color, linewidth=2.5,
                    markersize=8, label=dataset.get("label", ""))
            for j, val in enumerate(values):
                ax.text(j, val + max(values) * 0.03, self._format_number(val),
                        ha="center", fontsize=11, fontweight="bold")

        if len(data["datasets"]) > 1:
            ax.legend(fontsize=11)
        self._style_chart(ax, spec.get("title", ""))
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()

    def _pie_chart(self, spec: dict, path: str):
        fig, ax = plt.subplots(figsize=(8, 8))
        data = spec["data"]
        labels = data["labels"]
        values = data["datasets"][0]["values"]
        colors = CHART_COLORS[:len(labels)]

        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct="%1.1f%%", colors=colors,
            startangle=90, textprops={"fontsize": 13})

        for autotext in autotexts:
            autotext.set_fontweight("bold")
            autotext.set_color("white")

        ax.set_title(spec.get("title", ""), fontsize=18, fontweight="bold",
                     color="#1E3A5F", pad=20)
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()

    def _style_chart(self, ax, title: str):
        ax.set_title(title, fontsize=18, fontweight="bold", color="#1E3A5F", pad=20)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_alpha(0.3)
        ax.spines["bottom"].set_alpha(0.3)
        ax.tick_params(colors="#6B7280")
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(
            lambda x, p: self._format_number(x)))

    def _format_number(self, val):
        if not isinstance(val, (int, float)):
            return str(val)
        abs_val = abs(val)
        if abs_val >= 10000000:
            return f"₹{val / 10000000:.1f}Cr"
        elif abs_val >= 100000:
            return f"₹{val / 100000:.1f}L"
        elif abs_val >= 1000:
            return f"{val / 1000:.1f}K"
        return f"{val:,.0f}" if val == int(val) else f"{val:,.1f}"
